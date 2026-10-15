import time
from datetime import datetime
from uuid import uuid4

from .canonicalize import case_identity
from .comparison import COMPARISON_VERSION
from .context_artifacts import load_evidence, read_reference
from .context_errors import (
    ContextError,
    ContextUnavailable,
    EvidenceIntegrity,
    IdentityConflict,
)
from .context_lock import ContextLease
from .context_models import EvidenceReference, VersionScope, evidence_id
from .context_phase import child_id, engine_identity
from .execution import run_case
from .jsonio import digest, encode, loads
from .models import RunLimits, read_case
from .planner import rank_candidates
from .planner_models import Decision, ExecutionJournal, ProbeResult, SourceSnapshot
from .planning_artifacts import PlanningStore
from .probe_graph import catalog, commit_phase, now, phase_receipt
from .probe_phase import observation_phase, selection_phase
from .probe_registry import REGISTRY_SHA256
from .probe_transforms import transform

INCOMPLETE = "A previous experiment did not finish. Inspect its evidence and recover any owned engines before starting a new comparison."
STALE = "The saved experiment no longer matches its case or definition. No engines were started."


def seed_state(repository, seed_id):
    evidence_id(seed_id)
    context = repository._inspect(seed_id)
    case, report, _, engines, manifest = load_evidence(
        repository.config.artifact_root, seed_id
    )
    scope = VersionScope(
        baseline=engine_identity(engines[0]),
        target=engine_identity(engines[1]),
        comparison_version=COMPARISON_VERSION,
    )
    return context, case, report, scope, engines, manifest


def load_plan(repository, store):
    plan = Decision.model_validate(loads(store.get("plan.json")))
    expected_selection = digest(
        {
            "seed": plan.investigation_id,
            "manifest": plan.seed_manifest_sha256,
            "registry": plan.registry_sha256,
            "planner": plan.planner_version,
        }
    )
    if (
        plan.investigation_id != store.seed_id
        or plan.selection_id != expected_selection
    ):
        raise EvidenceIntegrity()
    snapshot = SourceSnapshot.model_validate(
        loads(read_reference(store.root, plan.source_snapshot_ref))
    )
    if (
        plan.registry_sha256
        != digest([item.definition.model_dump() for item in snapshot.catalog])
        or snapshot.scope != plan.scope
    ):
        raise EvidenceIntegrity()
    documents = {
        "plan.json": encode(plan.model_dump()),
        "source-snapshot.json": read_reference(store.root, plan.source_snapshot_ref),
    }
    for candidate in plan.candidates:
        ref = candidate.transformed_case_ref
        if ref.owner != store.owner:
            raise EvidenceIntegrity()
        documents[ref.path] = read_reference(store.root, ref)
    # A durable plan with all referenced files can finish sealing after interruption.
    refs = store.seal("selection", documents)
    if store.verify("selection") != refs:
        raise EvidenceIntegrity()
    return plan, snapshot, refs


def validate_seed(repository, plan):
    context, case, report, scope, engines, manifest = seed_state(
        repository, plan.investigation_id
    )
    if (
        case_identity(case)[0] != plan.seed_case_id
        or manifest != plan.seed_manifest_sha256
        or context.fingerprint.properties["id"] != plan.fingerprint_id
        or scope != plan.scope
    ):
        raise ContextError(STALE)
    return case, report, engines


def plan_probe(repository, seed_id):
    with ContextLease():
        context, case, report, scope, engines, manifest = seed_state(
            repository, seed_id
        )
        store = PlanningStore(repository.config.artifact_root, seed_id)
        if store.optional("plan.json"):
            plan, _, refs = load_plan(repository, store)
            validate_seed(repository, plan)
            receipt = commit_phase(
                repository, selection_phase(plan, refs), "selection", plan.selection_id
            )
            result, observation = reconcile_result(repository, store, plan, report)
            observed = (
                phase_receipt(
                    repository,
                    observation,
                    "observation",
                    plan.selection_id,
                    result.child_evidence_id,
                )
                if observation
                else None
            )
            return receipt_view(
                plan,
                receipt,
                result=result,
                observation_receipt=observed,
                pending=result is not None and observed is None,
                journal=store.journal(),
            )
        entries = catalog(repository, bootstrap=True)
        history = repository.get_fingerprint_history(
            context.fingerprint.properties["id"],
            scope=scope,
            limit=100,
            exclude_id=seed_id,
            overflow_check=True,
        )
        snapshot = SourceSnapshot(
            catalog=entries,
            history=history.candidates,
            feature_ids=context.features,
            scope=scope,
            lineages=[engine.lineage for engine in engines],
        )
        snapshot_data = encode(snapshot.model_dump())
        snapshot_ref = store.put("source-snapshot.json", snapshot_data)
        documents = {"source-snapshot.json": snapshot_data}

        def save_output(definition, output):
            filename = (
                "case-" + definition.type.lower().replace("_", "-") + ".faultglass.json"
            )
            data = encode(output.model_dump())
            documents[filename] = data
            return store.put(filename, data)

        candidates, rejections = (
            rank_candidates(case, snapshot, save_output)
            if report.divergence
            else ([], [])
        )
        outcome = (
            "not_reproduced"
            if not report.divergence
            else ("selected" if candidates else "unresolved")
        )
        plan = Decision(
            selection_id=digest(
                {
                    "seed": seed_id,
                    "manifest": manifest,
                    "registry": REGISTRY_SHA256,
                    "planner": "planner-v1",
                }
            ),
            investigation_id=seed_id,
            registry_sha256=REGISTRY_SHA256,
            seed_case_id=case_identity(case)[0],
            fingerprint_id=context.fingerprint.properties["id"],
            seed_manifest_sha256=manifest,
            scope=scope,
            created_at=now(),
            novel=not any(item.source == "history" for item in candidates),
            candidates=candidates,
            rejections=rejections,
            selected_probe_id=candidates[0].probe_id if candidates else None,
            outcome=outcome,
            terminal_reason="no_applicable_probe" if outcome == "unresolved" else None,
            limits=RunLimits(),
            source_snapshot_ref=snapshot_ref,
            transformed_case_ref=candidates[0].transformed_case_ref
            if candidates
            else None,
        )
        documents["plan.json"] = encode(plan.model_dump())
        refs = store.seal("selection", documents)
        try:
            receipt = commit_phase(
                repository, selection_phase(plan, refs), "selection", plan.selection_id
            )
        except ContextUnavailable:
            return receipt_view(plan, None, pending=True)
        return receipt_view(plan, receipt)


def receipt_view(
    plan, receipt, *, result=None, observation_receipt=None, pending=False, journal=None
):
    return {
        "evidence_id": plan.investigation_id,
        "decision": plan.model_dump(),
        "selection_receipt": receipt.model_dump() if receipt else None,
        "result": result.model_dump() if result else None,
        "observation_receipt": observation_receipt.model_dump()
        if observation_receipt
        else None,
        "journal": journal.model_dump() if journal else None,
        "execution_state": "evidence_complete"
        if result
        else ("incomplete" if journal else "not_started"),
        "commit_pending": pending,
        "reused": receipt.reused if receipt else False,
        "recovery_command": "python -m faultglass.probe commit --evidence-id "
        + plan.investigation_id
        if pending
        else (
            "python -m faultglass.recover --run-id " + journal.child_evidence_id
            if journal and not result
            else None
        ),
    }


def reconcile_result(repository, store, plan, seed_report):
    journal = store.journal()
    if journal is None:
        return None, None
    if journal.selection_id != plan.selection_id:
        raise EvidenceIntegrity()
    # Only a verified complete child can become an observation, including after a process interruption.
    child_id_value = journal.child_evidence_id
    try:
        case, report, refs, engines, manifest = load_evidence(
            store.root, child_id_value
        )
    except ContextError:
        if store.optional("result.json") or journal.state == "evidence_complete":
            raise
        return None, None
    if (
        encode(case.model_dump())
        != read_reference(store.root, plan.transformed_case_ref)
        or report.pairId != seed_report.pairId
        or [engine_identity(engine) for engine in engines]
        != [plan.scope.baseline, plan.scope.target]
    ):
        raise EvidenceIntegrity()
    signature = report.divergence.signature if report.divergence else None
    result = ProbeResult(
        selection_id=plan.selection_id,
        child_evidence_id=child_id_value,
        probe_id=plan.selected_probe_id,
        input_case_id=plan.seed_case_id,
        output_case_id=case_identity(case)[0],
        scope=plan.scope,
        child_manifest_sha256=manifest,
        child_artifacts=[
            EvidenceReference(**ref.model_dump(), owner=child_id_value) for ref in refs
        ],
        child_signature=signature,
        seed_signature=seed_report.divergence.signature,
        relationship="eliminated"
        if signature is None
        else (
            "preserved" if signature == seed_report.divergence.signature else "changed"
        ),
        paired_statuses={
            role: getattr(report.observations, role).status
            for role in ("baseline", "target")
        },
        paired_run_ids=[
            child_id(child_id_value, role) for role in ("baseline", "target")
        ],
        started_at=report.startedAt,
        finished_at=report.finishedAt,
        duration_ms=(
            datetime.fromisoformat(report.finishedAt)
            - datetime.fromisoformat(report.startedAt)
        ).total_seconds()
        * 1000,
    )
    result_ref = store.put("result.json", encode(result.model_dump()))
    store.seal("observation", {"result.json": encode(result.model_dump())})
    if journal.state != "evidence_complete":
        store.advance(
            ExecutionJournal(
                **{
                    **journal.model_dump(),
                    "state": "evidence_complete",
                    "started_at": journal.started_at or report.startedAt,
                    "finished_at": report.finishedAt,
                    "failure_code": None,
                }
            )
        )
    return result, observation_phase(plan, result, report, result_ref)


def saved_action(repository, seed_id, *, commit=False):
    with ContextLease():
        store = PlanningStore(repository.config.artifact_root, evidence_id(seed_id))
        plan, snapshot, refs = load_plan(repository, store)
        _, seed_report, _ = validate_seed(repository, plan)
        phase = selection_phase(plan, refs)
        receipt = (commit_phase if commit else phase_receipt)(
            repository, phase, "selection", plan.selection_id
        )
        result, observation = reconcile_result(repository, store, plan, seed_report)
        observed = None
        if observation:
            try:
                observed = (commit_phase if commit else phase_receipt)(
                    repository,
                    observation,
                    "observation",
                    plan.selection_id,
                    result.child_evidence_id,
                )
            except ContextUnavailable:
                return receipt_view(
                    plan, receipt, result=result, pending=True, journal=store.journal()
                )
        view = receipt_view(
            plan,
            receipt,
            result=result,
            observation_receipt=observed,
            pending=receipt is None or (result is not None and observed is None),
            journal=store.journal(),
        )
        view["source_snapshot"] = snapshot.model_dump()
        if store.optional("failure.json"):
            store.verify("failure")
            view["failure"] = loads(store.get("failure.json"))
        return view


def execute_probe(repository, seed_id):
    admitted = time.monotonic()
    with ContextLease():
        store = PlanningStore(repository.config.artifact_root, evidence_id(seed_id))
        plan, _, refs = load_plan(repository, store)
        case, seed_report, _ = validate_seed(repository, plan)
        receipt = phase_receipt(
            repository, selection_phase(plan, refs), "selection", plan.selection_id
        )
        if receipt is None:
            raise ContextError(
                "Save the selected experiment before running it. Run python -m faultglass.probe commit --evidence-id "
                + seed_id
            )
        if plan.outcome != "selected":
            return receipt_view(plan, receipt)
        result, observation = reconcile_result(repository, store, plan, seed_report)
        if result:
            return finish_observation(
                repository, store, plan, receipt, result, observation
            )
        if store.journal():
            raise ContextError(
                INCOMPLETE
                + " Run python -m faultglass.recover --run-id "
                + store.journal().child_evidence_id
            )
        try:
            current = next(
                (
                    entry
                    for entry in catalog(repository)
                    if entry.definition.id == plan.selected_probe_id
                ),
                None,
            )
        except IdentityConflict:
            raise ContextError(STALE) from None
        if current is None:
            raise ContextError(STALE)
        if not current.enabled:
            raise ContextError(
                "This experiment is no longer available. No engines were started."
            )
        output, _, reason = transform(case, current.definition)
        saved_bytes = read_reference(store.root, plan.transformed_case_ref)
        winner = plan.candidates[0]
        if (
            reason != "applicable"
            or current.definition.definition_sha256 != winner.definition_sha256
            or case_identity(output)[0] != winner.output_case_id
            or encode(output.model_dump()) != saved_bytes
        ):
            raise ContextError(STALE)
        deadline = admitted + plan.admission_seconds
        if (
            deadline - time.monotonic()
            < plan.limits.pairSeconds + 2 * plan.limits.cleanupSeconds
        ):
            return {
                **receipt_view(plan, receipt),
                "outcome": "unresolved",
                "reason": "budget_exhausted",
            }
        journal = ExecutionJournal(
            selection_id=plan.selection_id,
            child_evidence_id=str(uuid4()),
            state="reserved",
            reserved_at=now(),
        )
        store.advance(journal)
        journal = ExecutionJournal(
            **{**journal.model_dump(), "state": "started", "started_at": now()}
        )
        store.advance(journal)
        try:
            report, _, code = run_case(
                saved_bytes,
                read_case(saved_bytes),
                seed_report.pairId,
                store.root,
                plan.limits,
                reserved_id=journal.child_evidence_id,
                admission_deadline=deadline,
            )
        except BaseException:
            store.advance(
                ExecutionJournal(
                    **{
                        **journal.model_dump(),
                        "state": "incomplete",
                        "finished_at": now(),
                        "failure_code": "interrupted",
                    }
                )
            )
            raise
        if code:
            failure_data = encode(
                {
                    "selection_id": plan.selection_id,
                    "child_evidence_id": journal.child_evidence_id,
                    "report": report.model_dump(),
                    "exit_code": code,
                }
            )
            store.seal("failure", {"failure.json": failure_data})
            store.advance(
                ExecutionJournal(
                    **{
                        **journal.model_dump(),
                        "state": "incomplete",
                        "finished_at": now(),
                        "failure_code": report.failure.code,
                    }
                )
            )
            return {
                **receipt_view(plan, receipt, journal=store.journal()),
                "failure": report.model_dump(),
                "exit_code": code,
            }
        result, observation = reconcile_result(repository, store, plan, seed_report)
        if result is None:
            raise EvidenceIntegrity()
        return finish_observation(repository, store, plan, receipt, result, observation)


def finish_observation(repository, store, plan, receipt, result, observation):
    try:
        observed = commit_phase(
            repository,
            observation,
            "observation",
            plan.selection_id,
            result.child_evidence_id,
        )
    except ContextUnavailable:
        return receipt_view(
            plan, receipt, result=result, pending=True, journal=store.journal()
        )
    view = receipt_view(
        plan,
        receipt,
        result=result,
        observation_receipt=observed,
        journal=store.journal(),
    )
    view["reused"] = observed.reused
    return view
