import os
import time
from datetime import datetime
from uuid import uuid4

import pytest

from faultglass.analysis_models import HistoricalInfluence
from faultglass.context_artifacts import read_reference
from faultglass.context_config import ContextConfig
from faultglass.context_models import VersionScope
from faultglass.context_phase import engine_identity
from faultglass.explorer import load_run
from faultglass.fingerprint import extract_fingerprint
from faultglass.gemini import agent_readiness
from faultglass.graph_repository import GraphRepository
from faultglass.investigation_budget import verify_committed
from faultglass.investigation_models import TERMINAL, Admission, Status
from faultglass.jsonio import encode, loads
from faultglass.matrix import engines_for
from faultglass.models import read_case
from faultglass.planner import rank_candidates
from faultglass.planner_models import SourceSnapshot
from faultglass.probe_graph import catalog
from faultglass.provider_budget import CALL_SECONDS, MAX_CALLS, TOTAL_MILLISECONDS
from faultglass.public_cases import FLAGSHIP, RELATED
from faultglass.worker import Worker

pytestmark = pytest.mark.live


def advance(worker, record, *, require_live=True):
    for _ in range(120):
        if record.snapshot.status in TERMINAL:
            return record
        previous_calls = load_run(worker.store, record).calls
        record = worker.step(record.snapshot.id)
        run = load_run(worker.store, record)
        if run.calls > previous_calls:
            print(f"Live Explorer: {run.calls} calls, {run.status}", flush=True)
            if require_live and run.status == "degraded":
                pytest.fail(f"Live Explorer gate unmet: {run.reasonCode}")
            # Pace the opt-in proof outside the provider's strict execution deadline.
            time.sleep(20)
    pytest.fail("The live investigation exceeded its bounded action count.")


def assert_live(worker, record, *, model=None):
    verify_committed(worker.store, record)
    run = load_run(worker.store, record)
    assert record.snapshot.status == Status.COMPLETE
    assert run.mode == "agent" and run.status == "completed", (
        f"Live Explorer gate unmet: {run.reasonCode}"
    )
    assert run.provider == "gemini" and run.model == (
        model or os.environ["FAULTGLASS_GEMINI_MODEL"]
    )
    assert run.calls <= MAX_CALLS and run.elapsedMs <= TOTAL_MILLISECONDS
    assert all(t.responseRef and t.elapsedMs <= CALL_SECONDS * 1000 for t in run.turns)
    assert len(run.outputRefs) >= 2 and record.snapshot.conclusion.interpretationRef
    tools = [r.tool for r in run.results]
    assert tools[:3] == [
        "read_investigation_context",
        "rank_supported_probes",
        "execute_ranked_probe",
    ]
    assert tools.count("execute_ranked_probe") == 2
    assert tools.count("read_probe_evidence") == 2
    assert "read_classification_evidence" in tools
    for receipt in worker.store.history(record):
        if receipt.reservation and receipt.reservation.purpose == "probe":
            earlier = load_run(worker.store, receipt)
            authorized = [
                r for r in earlier.results if r.tool == "execute_ranked_probe"
            ]
            assert authorized
            turn = next(t for t in earlier.turns if t.id == authorized[-1].requestId)
            assert turn.responseRef and turn.revision < receipt.snapshot.revision
    return run


def test_live_explorer_changes_a_fresh_related_action(tmp_path, monkeypatch):
    assert agent_readiness()["agentReady"], (
        "Configure a worker-only GEMINI_API_KEY and FAULTGLASS_GEMINI_MODEL; this live gate cannot skip."
    )
    assert os.environ.get("FAULTGLASS_INVESTIGATION_MODE", "agent") == "agent"
    source_id = os.environ.get("FAULTGLASS_LIVE_SOURCE_ID")
    config = (
        ContextConfig.from_environment()
        if source_id
        else ContextConfig(
            graph="faultglass__test_" + uuid4().hex, artifact_root=tmp_path
        )
    )
    assert config.graph.startswith("faultglass__test_"), (
        "The live proof requires an isolated disposable graph."
    )
    repo = GraphRepository(config)
    tmp_path = config.artifact_root
    repo.ensure_schema()
    worker = Worker(repo)
    print(f"Live proof workspace: {config.graph} {tmp_path}", flush=True)
    if source_id:
        a = worker.store.load(source_id)
        assert read_case(read_reference(tmp_path, a.inputRef)) == read_case(
            encode(FLAGSHIP)
        )
        source_model = os.environ["FAULTGLASS_LIVE_SOURCE_MODEL"]
        assert_live(worker, a, model=source_model)
        print(f"Verified saved live source: {source_id} ({source_model})", flush=True)
    else:
        a, _ = worker.store.admit(
            Admission(caseFile=encode(FLAGSHIP).decode(), pairId="call-yield-c-rust"),
            str(uuid4()),
        )
    engines = engines_for(a.snapshot.pairId)
    from faultglass.comparison import COMPARISON_VERSION

    # Freeze the distinct case's structural ranking before any learning publication.
    snapshot = SourceSnapshot(
        catalog=catalog(repo, bootstrap=True),
        history=[],
        feature_ids=extract_fingerprint(read_case(encode(RELATED)))["feature_ids"],
        scope=VersionScope(
            baseline=engine_identity(engines[0]),
            target=engine_identity(engines[1]),
            comparison_version=COMPARISON_VERSION,
        ),
        lineages=[e.lineage for e in engines],
    )

    def counterfactual(definition, output):
        name = "counterfactual-" + definition.type.lower() + ".json"
        data = encode(output.model_dump())
        if source_id:
            path = tmp_path / a.snapshot.id / "runtime" / name
            assert path.exists() and path.read_bytes() == data
            source_run = load_run(worker.store, a)
            assert (
                path.stat().st_mtime
                < datetime.fromisoformat(source_run.turns[0].reservedAt).timestamp()
            )
        return worker.store.put(a.snapshot.id, name, data)

    frozen, _ = rank_candidates(
        read_case(encode(RELATED)),
        snapshot,
        counterfactual,
    )
    print(
        "Frozen structural ranking:",
        [
            (candidate.probe_id, candidate.rank, candidate.utility)
            for candidate in frozen
        ],
        flush=True,
    )
    if not source_id:
        a = advance(worker, a)
        assert_live(worker, a)
    print(
        f"Completed live source: {a.snapshot.id} {load_run(worker.store, a).model}",
        flush=True,
    )
    related_model = os.environ.get("FAULTGLASS_LIVE_RELATED_MODEL")
    if related_model:
        monkeypatch.setenv("FAULTGLASS_GEMINI_MODEL", related_model)
        print(f"Related investigation model: {related_model}", flush=True)
    related_id = os.environ.get("FAULTGLASS_LIVE_RELATED_ID")
    if related_id:
        assert source_id, "A saved related receipt requires its verified source."
        b = worker.store.load(related_id)
        assert b.snapshot.status == Status.COMPLETE
        assert b.snapshot.createdAt > a.snapshot.finishedAt
        assert read_case(read_reference(tmp_path, b.inputRef)) == read_case(
            encode(RELATED)
        )
    else:
        b, _ = worker.store.admit(
            Admission(caseFile=encode(RELATED).decode(), pairId="call-yield-c-rust"),
            str(uuid4()),
        )
    assert a.snapshot.id != b.snapshot.id and a.admissionKey != b.admissionKey
    require_related_agent = (
        os.environ.get("FAULTGLASS_LIVE_REQUIRE_RELATED_AGENT") == "1"
    )
    b = advance(worker, b, require_live=require_related_agent)
    verify_committed(worker.store, b)
    assert b.snapshot.status == Status.COMPLETE
    related_run = load_run(worker.store, b)
    assert related_run.mode == "agent"
    assert related_run.status in {"completed", "degraded"}
    if require_related_agent or related_run.status == "completed":
        assert_live(worker, b)
    else:
        assert related_run.reasonCode
    print(
        "Related agent outcome:",
        related_run.model,
        related_run.status,
        related_run.reasonCode,
        flush=True,
    )
    influence = HistoricalInfluence.model_validate(
        loads(read_reference(tmp_path, b.influenceRef))
    )
    assert [c.probe_id for c in frozen] == [c.probeId for c in influence.withoutHistory]
    assert influence.changed, (
        "Prior evidence did not change rank or selection; a score increase alone does not satisfy the learning gate."
    )
    assert influence.priorInvestigationIds == [a.snapshot.id]
    assert influence.withHistory[0].probeId == influence.selectedProbeId
    assert a.snapshot.conclusion.familyId == b.snapshot.conclusion.familyId
    assert b.snapshot.conclusion.state == "matched"
    assert (
        a.snapshot.reduction.currentCaseId != b.snapshot.reduction.source.sourceCaseId
    )
    from faultglass.conclusion_reads import conclusion_page

    page = conclusion_page(worker.store, b)
    assert page.classification.probes[0].probeId == influence.selectedProbeId
    assert len(page.classification.probes) == 2
    for probe in page.classification.probes:
        read_reference(tmp_path, probe.reportRef)
        read_reference(tmp_path, probe.resultRef)
    assert len(page.exports.files) == 3
    memory = page.memory
    assert memory.state == "recorded"
    assert len(memory.entries) == 2
    assert all(
        entry.before.attempts == 1 and entry.after.attempts == 2
        for entry in memory.entries
    )
    history = repo.get_fingerprint_history(b.snapshot.fingerprintId)
    assert len(history.candidates) == 2
    assert all(
        {episode.investigation.properties["id"] for episode in row.supporting_episodes}
        == {a.snapshot.id, b.snapshot.id}
        for row in history.candidates
    )
    # Preserve this disposable graph/artifact path in pytest's output for provenance inspection.
    print(
        "Live proof:",
        repo.config.graph,
        tmp_path,
        a.snapshot.id,
        b.snapshot.id,
        flush=True,
    )
    repo.close()
