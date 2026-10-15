import time
from pathlib import Path
from uuid import uuid4

import pytest

from faultglass.canonicalize import case_identity
from faultglass.context_artifacts import load_evidence, read_reference
from faultglass.context_config import ContextConfig
from faultglass.context_errors import ContextUnavailable, EvidenceIntegrity
from faultglass.execution import run_case
from faultglass.graph_repository import GraphRepository
from faultglass.investigation_models import TERMINAL, Admission, Status
from faultglass.investigation_store import InvestigationStore
from faultglass.jsonio import encode
from faultglass.models import read_case
from faultglass.reduction_candidates import case_size, smaller
from faultglass.reduction_reads import reduction_page
from faultglass.worker import Worker

pytestmark = pytest.mark.context


@pytest.fixture
def reduction_runtime(tmp_path, request):
    repo = GraphRepository(
        ContextConfig(graph="faultglass__test_" + uuid4().hex, artifact_root=tmp_path)
    )
    repo.ensure_schema()
    store = InvestigationStore(repo)
    data = (
        Path(__file__).parents[1] / "fixtures/call-yield.faultglass.json"
    ).read_text()
    if getattr(request, "param", None) == "large":
        from faultglass.jsonio import loads

        value = loads(data)
        value["query"] += " /*" + "\x01" * 12500 + "*/"
        data = encode(value).decode()
    record, _ = store.admit(
        Admission(caseFile=data, pairId="call-yield-c-rust"), str(uuid4())
    )
    try:
        yield Worker(repo), record.snapshot.id
    finally:
        repo.graph.delete()
        repo.close()


def advance(worker, job, predicate):
    for _ in range(60):
        record = worker.store.load(job)
        if predicate(record):
            return record
        assert record.snapshot.status not in TERMINAL
        worker.step(job)
    raise AssertionError("The investigation did not reach the required boundary.")


def reducing(worker, job):
    return advance(worker, job, lambda r: r.snapshot.status == Status.REDUCING)


def test_real_query_fixture_lineage_rejections_final_case_and_pages(reduction_runtime):
    worker, job = reduction_runtime
    final = advance(worker, job, lambda r: r.snapshot.status in TERMINAL)
    page = reduction_page(worker.store, final)
    summary = page.summary
    assert final.snapshot.status == Status.UNRESOLVED
    assert final.snapshot.terminalReason.code == "analysis_unavailable"
    assert (
        summary.source.sourceKind == "probe" and summary.source.sourceProbeSequence == 1
    )
    assert summary.source.stable and summary.stopReason == "candidate_limit"
    assert (
        summary.reservedCandidates == 4 and final.snapshot.budget.stabilityChecks == 1
    )
    accepted = [v for v in page.attempts if v.attempt.state == "accepted"]
    assert {v.attempt.phase for v in accepted} == {"query", "fixture"}
    assert summary.acceptedCount == len(accepted) == 2
    assert any(v.attempt.reason == "difference_eliminated" for v in page.attempts)
    for value in accepted:
        assert smaller(value.attempt.beforeSize, value.attempt.afterSize)
        assert value.attempt.observedDivergence == summary.source.referenceDivergence
        assert (
            value.observations.baseline.status == "error"
            and value.observations.target.status == "crash"
        )
    assert smaller(summary.originalSize, summary.currentSize)
    data = read_reference(worker.store.root, summary.finalCaseRef)
    case = read_case(data)
    assert (
        case_identity(case)[0] == summary.currentCaseId
        and case_size(case) == summary.currentSize
    )
    report, _, code = run_case(data, case, final.snapshot.pairId, worker.store.root)
    assert code == 0 and report.divergence == summary.source.referenceDivergence
    edges = worker.repository.graph.query(
        "MATCH ()-[r:REDUCED_TO]->() WHERE r.investigation_id=$id RETURN properties(r)",
        {"id": job},
    ).result_set
    assert {row[0]["attempt_id"] for row in edges} == {v.attempt.id for v in accepted}
    stable = worker.repository.graph.query(
        "MATCH (d:Divergence {investigation_id:$id}) WHERE d.stable=true RETURN d.stability_case_id",
        {"id": job},
    ).result_set
    assert stable == [[summary.source.sourceCaseId]]
    assert page.sourceObservations and page.stabilityObservations
    assert reduction_page(worker.store, final) == page
    for values in ((-1, None, 0), (0, "foreign", 0), (0, None, 33)):
        with pytest.raises(Exception) as error:
            reduction_page(worker.store, final, *values)
        assert error.value.status == 422
    with pytest.raises(Exception) as error:
        reduction_page(worker.store, final, case_id="a" * 64)
    assert error.value.status == 404
    assert len(encode(page.model_dump())) <= 245760
    assert worker.step(job).snapshot.revision == final.snapshot.revision


@pytest.mark.parametrize("kind", ["time", "storage"])
def test_reduction_stops_before_unreserved_work_at_limits(
    reduction_runtime, monkeypatch, kind
):
    worker, job = reduction_runtime
    reducing(worker, job)
    if kind == "time":
        worker.deadlines[job] = time.monotonic() - 1
    else:
        monkeypatch.setattr(
            "faultglass.reduction_service.owned_bytes", lambda *_: 60 * 1024 * 1024
        )
    monkeypatch.setattr(
        "faultglass.worker.run_case",
        lambda *_a, **_k: pytest.fail("No execution after a limit"),
    )
    final = worker.step(job)
    assert final.snapshot.reduction.stopReason == kind + "_limit"
    assert (
        final.snapshot.reduction.reservedCandidates == 0
        and final.snapshot.reduction.finalCaseRef
    )


def test_consideration_cap_rejects_without_provisioning(reduction_runtime, monkeypatch):
    from faultglass.investigation_planning import digest_bytes
    from faultglass.reduction_models import ReductionChange

    worker, job = reduction_runtime
    reducing(worker, job)
    advance(worker, job, lambda r: r.snapshot.reduction.source.stable)

    def duplicates(case):
        change = ReductionChange(
            setupIndex=0,
            originalTextSha256=digest_bytes(b"unchanged"),
            description="Unchanged proposal",
        )
        return [("fixture", "remove-setup-v1", encode(case.model_dump()), change)] * 33

    monkeypatch.setattr("faultglass.reduction_service.candidates", duplicates)
    monkeypatch.setattr(
        "faultglass.worker.run_case",
        lambda *_a, **_k: pytest.fail("Invalid proposals must not run"),
    )
    final = advance(worker, job, lambda r: r.snapshot.status in TERMINAL)
    assert final.snapshot.reduction.consideredCount == 32
    assert (
        final.snapshot.reduction.reservedCandidates == 0
        and final.snapshot.reduction.stopReason == "consideration_limit"
    )
    page = reduction_page(worker.store, final)
    assert len(page.attempts) == 10 and page.nextCursor == 10
    assert len(reduction_page(worker.store, final, 30).attempts) == 2


def test_cancel_during_verification_preserves_coherent_head(
    reduction_runtime, monkeypatch
):
    import faultglass.worker as module

    worker, job = reduction_runtime
    reducing(worker, job)
    active = advance(
        worker, job, lambda r: r.reservation and r.reservation.purpose == "reduction"
    )
    original = module.run_case

    def cancel_after_pair(*args, **kwargs):
        result = original(*args, **kwargs)
        worker.store.cancel(job)
        return result

    monkeypatch.setattr(module, "run_case", cancel_after_pair)
    final = worker.step(job)
    assert (
        final.snapshot.status == Status.CANCELLED and final.snapshot.cancelRequestedAt
    )
    assert final.reservation is None and final.snapshot.reduction.state == "cancelled"
    assert (
        final.snapshot.reduction.reservedCandidates == 1
        and final.snapshot.reduction.acceptedCount == 1
    )
    assert (
        final.snapshot.reduction.currentCaseId
        != active.snapshot.reduction.currentCaseId
    )
    assert reduction_page(worker.store, final).attempts[0].attempt.state == "accepted"
    assert worker.step(job) == final


def test_complete_child_reconciles_after_outage_without_second_execution(
    reduction_runtime, monkeypatch
):
    worker, job = reduction_runtime
    reducing(worker, job)
    advance(
        worker, job, lambda r: r.reservation and r.reservation.purpose == "reduction"
    )
    complete = worker.reduction.complete
    monkeypatch.setattr(
        worker.reduction,
        "complete",
        lambda *_: (_ for _ in ()).throw(ContextUnavailable()),
    )
    with pytest.raises(ContextUnavailable):
        worker.step(job)
    record = worker.store.load(job)
    assert record.reservation.state == "started"
    load_evidence(worker.store.root, record.reservation.childId)
    monkeypatch.setattr(worker.reduction, "complete", complete)
    monkeypatch.setattr(
        "faultglass.worker.run_case",
        lambda *_a, **_k: pytest.fail("A complete child must not run again"),
    )
    final = Worker(worker.repository).step(job)
    assert (
        final.snapshot.reduction.acceptedCount == 1
        and final.snapshot.budget.reservedCandidates == 1
    )
    assert (
        sum(r.event.type == "reduction.accepted" for r in worker.store.history(final))
        == 1
    )


def test_tampered_proposal_cannot_advance_head(reduction_runtime):
    worker, job = reduction_runtime
    reducing(worker, job)
    record = advance(
        worker, job, lambda r: r.reservation and r.reservation.purpose == "reduction"
    )
    ref = worker.reduction.checkpoint(record).activeAttempt.candidateRef
    (worker.store.root / ref.owner / ref.path).write_bytes(b"changed")
    with pytest.raises(EvidenceIntegrity):
        worker.step(job)
    assert (
        worker.store.load(job, verify_outputs=False).snapshot.reduction.acceptedCount
        == 0
    )


@pytest.mark.parametrize("reduction_runtime", ["large"], indirect=True)
def test_large_queries_keep_pages_bounded_without_truncating_cases(reduction_runtime):
    worker, job = reduction_runtime
    final = advance(worker, job, lambda r: r.snapshot.status in TERMINAL)
    page = reduction_page(worker.store, final)
    assert len(encode(page.model_dump())) <= 245760
    assert len(page.case.query) > 12500
    assert page.attempts and page.attempts[0].parent is None
    parent_id = page.attempts[0].attempt.parentCaseId
    parent_page = reduction_page(worker.store, final, case_id=parent_id)
    assert parent_page.case.caseId == parent_id
    assert len(parent_page.case.query) > 12500
    assert len(encode(parent_page.model_dump())) <= 245760
