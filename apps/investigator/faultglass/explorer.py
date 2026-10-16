import time

from .agent_models import (
    AgentRun,
    AgentSummary,
    AgentToolRequest,
    AgentToolResult,
    AgentTurn,
)
from .analysis_artifacts import AnalysisStore
from .comparison import material
from .context_artifacts import load_evidence, read_reference
from .context_errors import EvidenceIntegrity
from .errors import DeadlineExceeded
from .gemini import GeminiProvider, agent_readiness
from .investigation_models import TERMINAL
from .investigation_store import now
from .jsonio import digest, encode, loads
from .lifecycle import cleanup_deadline
from .llm_provider import ProviderFailure
from .models import read_case
from .provider_budget import CALL_SECONDS, MAX_CALLS, TOTAL_MILLISECONDS
from .public_cases import is_public

TOOLS = {
    "context": "read_investigation_context",
    "rank": "rank_supported_probes",
    "execute": "execute_ranked_probe",
    "evidence": "read_probe_evidence",
    "continue": "continue_verified_analysis",
    "classification": "read_classification_evidence",
}


def initial_run(job_id, at, readiness=None):
    readiness = readiness or agent_readiness()
    mode = readiness["agentMode"]
    diagnostic = mode == "deterministic_diagnostic"
    return AgentRun(
        investigationId=job_id,
        mode="deterministic_diagnostic" if diagnostic else "agent",
        status="degraded" if diagnostic else "pending",
        reasonCode="deterministic_diagnostic" if diagnostic else None,
        createdAt=at,
        updatedAt=at,
    )


def summary(run):
    return AgentSummary(
        **{
            key: getattr(run, key)
            for key in ("mode", "status", "reasonCode", "model", "calls")
        }
    )


def save_run(
    store, record, run, *, message="AI investigation action recorded.", outputs=()
):
    run.updatedAt = now()
    ref = AnalysisStore(store.root, record.snapshot.id, "agent").document("run", run)
    return store.commit(
        record.snapshot.id,
        "agent.degraded"
        if run.status in {"degraded", "data_excluded"}
        else "agent.action",
        message,
        update={
            "agent": summary(run).model_dump(),
            "record": {"agentRef": ref.model_dump()},
        },
        outputs=[ref, *outputs],
    )


def load_run(store, record):
    if record.agentRef is None:
        return None
    if record.agentRef.owner != record.snapshot.id + "/agent":
        raise EvidenceIntegrity()
    run = AgentRun.model_validate(loads(read_reference(store.root, record.agentRef)))
    if run.investigationId != record.snapshot.id:
        raise EvidenceIntegrity()
    return run


class Explorer:
    def __init__(self, worker):
        self.worker, self.store = worker, worker.store

    def degrade(self, record, run, reason, status="degraded"):
        run.status, run.reasonCode = status, reason
        return save_run(
            self.store,
            record,
            run,
            message="AI investigation is unavailable. Verified evidence is preserved.",
        )

    def privacy(self, record, investigation_ids):
        if not is_public(read_case(read_reference(self.store.root, record.inputRef))):
            return False
        for identity in set(investigation_ids):
            props = self.worker.repository._lookup(identity)
            if props and props.get("runtime_version"):
                source = self.store.load(identity)
                case = read_case(read_reference(self.store.root, source.inputRef))
            else:
                case = load_evidence(self.store.root, identity)[0]
            if not is_public(case):
                return False
        return True

    def request(
        self, record, run, facts, *, operation="request_tool", decision=None, origins=()
    ):
        if (
            run.turns
            and run.turns[-1].responseRef
            and not any(r.requestId == run.turns[-1].id for r in run.results)
        ):
            from .llm_provider import OPERATIONS

            turn = run.turns[-1]
            if record.snapshot.revision != turn.revision + 1:
                return self.degrade(record, run, "stale_tool_request"), None
            return record, OPERATIONS[operation].model_validate(
                loads(read_reference(self.store.root, turn.responseRef))
            )
        if not self.privacy(record, origins):
            return self.degrade(
                record, run, "private_evidence_excluded", "data_excluded"
            ), None
        if run.turns and run.turns[-1].responseRef is None:
            return self.degrade(record, run, "uncertain_provider_response"), None
        if (
            run.calls >= MAX_CALLS
            or run.elapsedMs + CALL_SECONDS * 1000 > TOTAL_MILLISECONDS
        ):
            return self.degrade(record, run, "provider_budget_exhausted"), None
        from .llm_provider import validate_citations

        try:
            provider = GeminiProvider()
        except ProviderFailure as exc:
            return self.degrade(record, run, exc.code), None
        context = {
            "operation": operation,
            "investigationId": record.snapshot.id,
            "revision": record.snapshot.revision + 1,
            "decisionId": decision,
            "allowedTool": TOOLS.get(run.stage),
            "enrichmentRequired": run.stage == "rank"
            and record.snapshot.probeSequence == 0,
            "evidenceIds": facts["evidenceIds"],
            "facts": facts,
        }
        if len(encode(context)) > 32768:
            return self.degrade(record, run, "input_limit"), None
        run.inputArtifactHashes = sorted(
            {
                record.inputRef.sha256,
                *run.inputArtifactHashes,
                *[ref.sha256 for result in run.results for ref in result.references],
                *(
                    [record.classificationRef.sha256]
                    if record.classificationRef
                    else []
                ),
            }
        )
        run.provider, run.model, run.status = "gemini", provider.model, "running"
        turn = AgentTurn(
            id=digest({"investigation": record.snapshot.id, "turn": run.calls + 1}),
            revision=context["revision"],
            operation="explain_family" if operation == "interpretation" else operation,
            inputHash=digest(context),
            reservedAt=now(),
        )
        run.turns.append(turn)
        run.calls += 1
        reserved = save_run(
            self.store,
            record,
            run,
            message="Inspecting connected investigation evidence.",
        )
        if reserved.snapshot.status in TERMINAL:
            return reserved, None
        started = time.monotonic()
        try:
            with cleanup_deadline(CALL_SECONDS):
                try:
                    result = provider.generate(operation, context)
                except DeadlineExceeded:
                    raise ProviderFailure("provider_timeout") from None
            elapsed = (time.monotonic() - started) * 1000
            if elapsed > CALL_SECONDS * 1000:
                raise ProviderFailure("provider_timeout")
            validate_citations(result, context["evidenceIds"])
            if operation == "request_tool":
                validate_tool(result, reserved, run, decision)
            storage = AnalysisStore(self.store.root, record.snapshot.id, "agent")
            response_ref = storage.document("response", result)
            turn.responseRef = response_ref
            turn.elapsedMs = elapsed
            run.elapsedMs += elapsed
            fresh = save_run(
                self.store,
                reserved,
                run,
                message=("Explorer: " + result.explanation.text)
                if operation == "request_tool"
                else "Cited AI interpretation recorded.",
                outputs=[response_ref],
            )
            return fresh, result
        except ProviderFailure as exc:
            turn.failure = exc.code
            turn.elapsedMs = min(
                CALL_SECONDS * 1000, (time.monotonic() - started) * 1000
            )
            run.elapsedMs += turn.elapsedMs
            return self.degrade(reserved, run, exc.code), None

    def result(self, record, run, request, payload, references, next_stage):
        storage = AnalysisStore(self.store.root, record.snapshot.id, "agent")
        ref = storage.put("tool-" + run.turns[-1].id + ".json", encode(payload))
        run.results.append(
            AgentToolResult(
                requestId=run.turns[-1].id,
                tool=request.tool,
                references=[ref, *references],
                resultHash=digest(payload),
            )
        )
        if request.enrichment:
            run.outputRefs.append(storage.document("fingerprint", request.enrichment))
        run.stage = next_stage
        return save_run(self.store, record, run, outputs=[ref])


def validate_tool(request, record, run, decision):
    if (
        not isinstance(request, AgentToolRequest)
        or request.investigationId != record.snapshot.id
        or request.revision != record.snapshot.revision
        or request.tool != TOOLS[run.stage]
        or request.decisionId != decision
    ):
        raise ProviderFailure("invalid_tool_request")
    required = run.stage == "rank" and record.snapshot.probeSequence == 0
    if required != (request.enrichment is not None):
        raise ProviderFailure("invalid_enrichment")


def context_facts(repository, record):
    context = repository.get_investigation_context(record.snapshot.id)
    history = repository.get_fingerprint_history(
        context.fingerprint.properties["id"],
        exclude_id=record.snapshot.id,
        limit=100,
        overflow_check=True,
    )
    origins = [
        e.investigation.properties["id"]
        for c in history.candidates
        for e in c.supporting_episodes
    ]
    facts = {
        "evidenceIds": [record.inputRef.sha256, context.fingerprint.properties["id"]],
        "features": context.features,
        "history": [
            {
                "probeId": c.probe_id,
                "familyId": c.family_id,
                "attempts": c.attempts,
                "successes": c.successes,
                "scope": c.version_scope.model_dump(),
                "paths": [e.properties["id"] for e in c.path_edges],
            }
            for c in history.candidates
        ],
    }
    return facts, origins


def planning_checkpoint(explorer, record, run):
    from .family_evidence import collect_probes
    from .investigation_planning import plan_next

    if run.stage in {"context", "rank"}:
        facts, origins = context_facts(explorer.worker.repository, record)
        fresh, request = explorer.request(record, run, facts, origins=origins)
        if request is None:
            return fresh
        if run.stage == "context":
            # Retrieve again only after the model-issued read request is committed.
            facts, _ = context_facts(explorer.worker.repository, fresh)
            return explorer.result(
                fresh, run, request, facts, [record.inputRef], "rank"
            )
        plan, phase = plan_next(explorer.worker.repository, fresh)
        payload = {
            "decisionId": plan.selection_id,
            "candidates": [
                {"probeId": c.probe_id, "rank": c.rank, "score": c.utility}
                for c in plan.candidates
            ],
            "evidenceIds": [r.sha256 for r in phase.artifacts],
        }
        return explorer.result(fresh, run, request, payload, phase.artifacts, "execute")
    if run.stage == "evidence":
        probes = collect_probes(explorer.store, record)
        latest = probes[-1]
        facts = {
            "evidenceIds": [latest.reportRef.sha256, latest.resultRef.sha256],
            "probe": latest.model_dump(),
        }
        fresh, request = explorer.request(record, run, facts)
        if request is None:
            return fresh
        evidence = load_evidence(explorer.store.root, latest.reportRef.owner)
        payload = {
            role: material(
                getattr(evidence[1].observations, role), evidence[0].observation
            )
            for role in ("baseline", "target")
        }
        return explorer.result(
            fresh,
            run,
            request,
            payload,
            [latest.reportRef, latest.resultRef],
            "rank" if record.snapshot.probeSequence < 2 else "continue",
        )
    if run.stage == "continue":
        probes = collect_probes(explorer.store, record)
        facts = {
            "evidenceIds": [p.resultRef.sha256 for p in probes],
            "outcomes": [p.model_dump() for p in probes],
        }
        fresh, request = explorer.request(record, run, facts)
        if request is None:
            return fresh
        return explorer.result(
            fresh,
            run,
            request,
            {"action": "continue_verified_analysis"},
            [p.resultRef for p in probes],
            "classification",
        )
    return None


def execution_authorization(explorer, record, run, plan, phase):
    facts = {
        "evidenceIds": [r.sha256 for r in phase.artifacts],
        "decisionId": plan.selection_id,
        "selectedProbeId": plan.selected_probe_id,
        "candidates": [
            {"probeId": c.probe_id, "rank": c.rank, "score": c.utility}
            for c in plan.candidates
        ],
    }
    return explorer.request(record, run, facts, decision=plan.selection_id)


def execution_attachment(store, record, run, request, plan, reservation, refs):
    run.results.append(
        AgentToolResult(
            requestId=run.turns[-1].id,
            tool=request.tool,
            references=refs,
            resultHash=digest(reservation.model_dump()),
        )
    )
    run.stage = "evidence"
    run.updatedAt = now()
    ref = AnalysisStore(store.root, record.snapshot.id, "agent").document("run", run)
    return ref
