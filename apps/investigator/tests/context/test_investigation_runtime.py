from pathlib import Path
from uuid import uuid4

import pytest

from faultglass.context_config import ContextConfig
from faultglass.graph_repository import GraphRepository
from faultglass.investigation_models import Admission, Status
from faultglass.investigation_store import InvestigationStore, RuntimeErrorResponse
from faultglass.worker import Worker

pytestmark = pytest.mark.context


@pytest.fixture
def runtime(tmp_path):
    repo = GraphRepository(
        ContextConfig(graph="faultglass__test_" + uuid4().hex, artifact_root=tmp_path)
    )
    repo.ensure_schema()
    try:
        yield InvestigationStore(repo)
    finally:
        repo.graph.delete()
        repo.close()


def admission(name="matching"):
    return Admission(
        caseFile=(
            Path(__file__).parents[1] / "fixtures" / (name + ".faultglass.json")
        ).read_text(),
        pairId="call-yield-c-rust",
    )


def test_admission_replay_conflict_and_cancel(runtime):
    key = str(uuid4())
    record, reused = runtime.admit(admission(), key)
    assert not reused
    assert record.snapshot.status == Status.QUEUED
    assert runtime.admit(admission(), key)[0].snapshot.id == record.snapshot.id
    with pytest.raises(RuntimeErrorResponse, match="different case"):
        runtime.admit(admission("call-yield"), key)
    assert runtime.lookup(key)["id"] == record.snapshot.id
    cancelled, accepted = runtime.cancel(record.snapshot.id)
    assert accepted
    assert cancelled.snapshot.cancelRequestedAt
    Worker(runtime.repository).step(record.snapshot.id)
    final = runtime.load(record.snapshot.id)
    assert final.snapshot.status == Status.CANCELLED
    assert [r.event.sequence for r in runtime.history(final)] == [1, 2, 3]


def test_matching_worker_preserves_inspectable_seed(runtime):
    record, _ = runtime.admit(admission(), str(uuid4()))
    worker = Worker(runtime.repository)
    for _ in range(6):
        worker.step(record.snapshot.id)
    final = runtime.load(record.snapshot.id)
    assert final.snapshot.status == Status.NOT_REPRODUCED
    context = runtime.repository.get_investigation_context(record.snapshot.id)
    assert len(context.runs) == 2


def test_reproduced_worker_runs_distinct_experiments(runtime):
    record, _ = runtime.admit(admission("call-yield"), str(uuid4()))
    worker = Worker(runtime.repository)
    for _ in range(40):
        worker.step(record.snapshot.id)
        if runtime.load(record.snapshot.id).snapshot.status in {
            Status.UNRESOLVED,
            Status.FAILED,
        }:
            break
    final = runtime.load(record.snapshot.id)
    assert final.snapshot.status == Status.UNRESOLVED
    assert final.snapshot.probeSequence == 1
    assert final.snapshot.terminalReason.code == "analysis_unavailable"
    assert len(final.triedOutputs) == 1
    assert (
        len(runtime.repository.get_investigation_context(record.snapshot.id).runs) == 2
    )


def test_lost_acknowledgment_does_not_repeat_admission_or_phase(runtime, monkeypatch):
    from faultglass.context_errors import ContextUnavailable

    original = runtime.repository._query
    writes = []

    def lost(name, *args, **kwargs):
        result = original(name, *args, **kwargs)
        if name in {"runtime-create", "runtime-commit"}:
            writes.append(name)
            raise ContextUnavailable()
        return result

    monkeypatch.setattr(runtime.repository, "_query", lost)
    key = str(uuid4())
    record, _ = runtime.admit(admission(), key)
    Worker(runtime.repository).step(record.snapshot.id)
    assert runtime.lookup(key)["id"] == record.snapshot.id
    assert runtime.load(record.snapshot.id).snapshot.revision == 2
    assert writes == ["runtime-create", "runtime-commit"]


def test_phase_domain_state_and_event_head_roll_back_together(runtime, monkeypatch):
    from redis.exceptions import ResponseError

    from faultglass.graph_repository import query_text

    record, _ = runtime.admit(admission(), str(uuid4()))
    worker = Worker(runtime.repository)
    worker.step(record.snapshot.id)
    before = runtime.repository._query("counts")
    head = runtime.load(record.snapshot.id)
    original = runtime.repository._query

    def rollback(name, params=None, **kwargs):
        if name == "runtime-commit":
            statement = query_text(name).replace(
                "RETURN i.id, i.revision", "SET i.invalid=1 / $zero RETURN i.id"
            )
            return runtime.repository.graph.query(
                statement, {**params, "zero": 0}, timeout=2000
            ).result_set
        return original(name, params, **kwargs)

    monkeypatch.setattr(runtime.repository, "_query", rollback)
    with pytest.raises(ResponseError, match="Division by zero"):
        worker.step(record.snapshot.id)
    assert runtime.repository._query("counts") == before
    assert runtime.load(record.snapshot.id) == head


def test_cancel_during_pair_preserves_evidence_and_wins_publication(
    runtime, monkeypatch
):
    import faultglass.worker as worker_module
    from faultglass.graph_repository import GraphRepository

    record, _ = runtime.admit(admission("call-yield"), str(uuid4()))
    worker = Worker(runtime.repository)
    worker.step(record.snapshot.id)
    worker.step(record.snapshot.id)
    execute = worker_module.run_case

    def cancel_after_comparison(*args, **kwargs):
        result = execute(*args, **kwargs)
        repo = GraphRepository(runtime.repository.config)
        try:
            accepted, flag = InvestigationStore(repo).cancel(record.snapshot.id)
            assert flag and accepted.snapshot.status == Status.REPRODUCING
        finally:
            repo.close()
        return result

    monkeypatch.setattr(worker_module, "run_case", cancel_after_comparison)
    worker.step(record.snapshot.id)
    final = runtime.load(record.snapshot.id)
    assert final.snapshot.status == Status.CANCELLED
    assert final.snapshot.seedEvidenceId == record.snapshot.id
    assert (
        len(runtime.repository.get_investigation_context(record.snapshot.id).runs) == 2
    )
    assert runtime.cancel(record.snapshot.id)[1] is False


def test_concurrent_admissions_and_cancels_keep_one_identity_and_intent(runtime):
    from concurrent.futures import ThreadPoolExecutor

    from faultglass.graph_repository import GraphRepository

    key = str(uuid4())

    def start(_):
        repo = GraphRepository(runtime.repository.config)
        try:
            return InvestigationStore(repo).admit(admission(), key)[0].snapshot.id
        finally:
            repo.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(start, range(2)))
    assert ids[0] == ids[1]

    def cancel(_):
        repo = GraphRepository(runtime.repository.config)
        try:
            return InvestigationStore(repo).cancel(ids[0])[0].snapshot.cancelRequestedAt
        finally:
            repo.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        timestamps = list(pool.map(cancel, range(2)))
    assert timestamps[0] == timestamps[1]
    assert runtime.load(ids[0]).snapshot.revision == 2


def test_budget_expiry_and_queue_capacity_do_not_execute(runtime):
    import time

    record, _ = runtime.admit(admission(), str(uuid4()))
    worker = Worker(runtime.repository)
    worker.deadlines[record.snapshot.id] = time.monotonic() - 1
    worker.step(record.snapshot.id)
    assert (
        runtime.load(record.snapshot.id).snapshot.terminalReason.code
        == "budget_exhausted"
    )
    for _ in range(8):
        runtime.admit(admission(), str(uuid4()))
    with pytest.raises(RuntimeErrorResponse) as exc:
        runtime.admit(admission(), str(uuid4()))
    assert exc.value.status == 429


def test_worker_singleton_refuses_second_process_before_engines(runtime):
    import os
    import subprocess
    import sys

    from faultglass.worker_presence import WorkerPresence

    env = {
        **os.environ,
        "FAULTGLASS_CONTEXT_GRAPH": runtime.repository.config.graph,
        "FAULTGLASS_ARTIFACT_ROOT": str(runtime.root),
    }
    with WorkerPresence(runtime.repository.config):
        process = subprocess.run(
            [sys.executable, "-m", "faultglass.worker"],
            env=env,
            capture_output=True,
            timeout=10,
        )
        assert process.returncode == 1
        assert b"could not start" in process.stderr
    assert runtime.pending() == []


def test_unsubmitted_phase_is_rebuilt_without_execution(runtime, monkeypatch):
    from faultglass.context_errors import ContextUnavailable

    record, _ = runtime.admit(admission(), str(uuid4()))
    worker = Worker(runtime.repository)
    worker.step(record.snapshot.id)
    original = runtime.repository._query

    def outage(name, *args, **kwargs):
        if name == "runtime-commit":
            raise ContextUnavailable()
        return original(name, *args, **kwargs)

    monkeypatch.setattr(runtime.repository, "_query", outage)
    with pytest.raises(ContextUnavailable):
        worker.step(record.snapshot.id)
    monkeypatch.setattr(runtime.repository, "_query", original)
    worker.step(record.snapshot.id)
    assert runtime.load(record.snapshot.id).snapshot.status == Status.REPRODUCING


def test_corrupt_committed_output_fails_without_regenerating_bytes(runtime):
    record, _ = runtime.admit(admission(), str(uuid4()))
    worker = Worker(runtime.repository)
    worker.step(record.snapshot.id)
    worker.step(record.snapshot.id)
    current = runtime.load(record.snapshot.id)
    ref = current.outputs[0]
    path = runtime.root / ref.owner / ref.path
    path.write_bytes(b"altered evidence")
    worker.tick()
    failed = runtime.load(record.snapshot.id)
    assert failed.snapshot.status == Status.FAILED
    assert failed.snapshot.terminalReason.code == "integrity_failure"
    assert path.read_bytes() == b"altered evidence"


def test_cleanup_failure_overrides_cancellation_and_requires_recovery(
    runtime, monkeypatch
):
    import faultglass.worker as worker_module
    from faultglass.context_errors import ContextError

    record, _ = runtime.admit(admission(), str(uuid4()))
    worker = Worker(runtime.repository)
    worker.step(record.snapshot.id)
    worker.step(record.snapshot.id)

    def failed_pair(*args, **kwargs):
        runtime.cancel(record.snapshot.id)
        return None, None, 1

    def failed_cleanup():
        raise ContextError("Owned engines remain")

    monkeypatch.setattr(worker_module, "run_case", failed_pair)
    monkeypatch.setattr(worker, "cleanup", failed_cleanup)
    with pytest.raises(ContextError, match="cleanup"):
        worker.step(record.snapshot.id)
    final = runtime.load(record.snapshot.id)
    assert final.snapshot.status == Status.FAILED
    assert final.snapshot.cancelRequestedAt
    assert final.snapshot.terminalReason.code == "cleanup_required"
    assert final.reservation.childId == record.snapshot.id
