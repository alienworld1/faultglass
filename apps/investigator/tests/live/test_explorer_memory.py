import os
import time
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
from faultglass.investigation_models import TERMINAL, Admission, Status
from faultglass.jsonio import encode, loads
from faultglass.matrix import engines_for
from faultglass.models import read_case
from faultglass.planner import rank_candidates
from faultglass.planner_models import SourceSnapshot
from faultglass.probe_graph import catalog
from faultglass.public_cases import FLAGSHIP, RELATED
from faultglass.worker import Worker

pytestmark = pytest.mark.live


def advance(worker, record):
    for _ in range(120):
        if record.snapshot.status in TERMINAL:
            return record
        previous_calls = load_run(worker.store, record).calls
        record = worker.step(record.snapshot.id)
        run = load_run(worker.store, record)
        if run.calls > previous_calls:
            print(f"Live Explorer: {run.calls} calls, {run.status}", flush=True)
            if run.status == "degraded":
                pytest.fail(f"Live Explorer gate unmet: {run.reasonCode}")
            # Pace the opt-in proof outside the provider's strict execution deadline.
            time.sleep(20)
    pytest.fail("The live investigation exceeded its bounded action count.")


def assert_live(worker, record):
    run = load_run(worker.store, record)
    assert record.snapshot.status == Status.COMPLETE
    assert run.mode == "agent" and run.status == "completed", (
        f"Live Explorer gate unmet: {run.reasonCode}"
    )
    assert (
        run.provider == "gemini" and run.model == os.environ["FAULTGLASS_GEMINI_MODEL"]
    )
    assert run.calls <= 12 and run.elapsedMs <= 60000
    assert all(t.responseRef and t.elapsedMs <= 5000 for t in run.turns)
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
    repo = GraphRepository(
        ContextConfig(graph="faultglass__test_" + uuid4().hex, artifact_root=tmp_path)
    )
    repo.ensure_schema()
    worker = Worker(repo)
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
    frozen, _ = rank_candidates(
        read_case(encode(RELATED)),
        snapshot,
        lambda definition, output: worker.store.put(
            a.snapshot.id,
            "counterfactual-" + definition.type.lower() + ".json",
            encode(output.model_dump()),
        ),
    )
    a = advance(worker, a)
    assert_live(worker, a)
    related_model = os.environ.get("FAULTGLASS_LIVE_RELATED_MODEL")
    if related_model:
        monkeypatch.setenv("FAULTGLASS_GEMINI_MODEL", related_model)
        print(f"Related investigation model: {related_model}", flush=True)
    b, _ = worker.store.admit(
        Admission(caseFile=encode(RELATED).decode(), pairId="call-yield-c-rust"),
        str(uuid4()),
    )
    assert a.snapshot.id != b.snapshot.id and a.admissionKey != b.admissionKey
    b = advance(worker, b)
    assert_live(worker, b)
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
