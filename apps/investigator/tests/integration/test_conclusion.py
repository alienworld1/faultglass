import ast
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from faultglass import api
from faultglass.analysis_models import ClassificationEvidence
from faultglass.comparison import material
from faultglass.conclusion_reads import conclusion_page, download
from faultglass.context_artifacts import read_reference
from faultglass.context_config import ContextConfig
from faultglass.context_errors import ContextUnavailable
from faultglass.execution import run_case
from faultglass.graph_repository import GraphRepository
from faultglass.investigation_models import TERMINAL, Admission, Status
from faultglass.jsonio import encode, loads
from faultglass.models import read_case
from faultglass.public_cases import FLAGSHIP
from faultglass.worker import Worker

pytestmark = pytest.mark.docker


def finish(worker, record, predicate=lambda r: r.snapshot.status in TERMINAL):
    for _ in range(120):
        if predicate(record):
            return record
        assert record.snapshot.status not in TERMINAL
        record = worker.step(record.snapshot.id)
    pytest.fail("The investigation did not settle within its bounded actions.")


@pytest.fixture
def completed(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULTGLASS_INVESTIGATION_MODE", "deterministic_diagnostic")
    repo = GraphRepository(
        ContextConfig(graph="faultglass__test_" + uuid4().hex, artifact_root=tmp_path)
    )
    repo.ensure_schema()
    worker = Worker(repo)
    record, _ = worker.store.admit(
        Admission(caseFile=encode(FLAGSHIP).decode(), pairId="call-yield-c-rust"),
        str(uuid4()),
    )
    try:
        yield worker, finish(worker, record)
    finally:
        repo.graph.delete()
        repo.close()


def test_verified_downloads_semantic_assertion_and_replay(completed, tmp_path):
    worker, record = completed
    assert record.snapshot.status == Status.COMPLETE
    page = conclusion_page(worker.store, record)
    assert page.memory.state == "recorded"
    assert len(page.memory.entries) == 2
    assert [e.reason for e in page.memory.entries] == [
        "repeated_source",
        "semantic_contrast",
    ]
    before = [e.model_dump() for e in page.memory.entries]
    for file in page.exports.files:
        reference, data = download(worker.store, record, file.key)
        assert reference == file and data == read_reference(worker.store.root, file)
    _, data = download(worker.store, record, "case")
    case = read_case(data)
    report, _, code = run_case(data, case, record.snapshot.pairId, tmp_path)
    evidence = ClassificationEvidence.model_validate(
        loads(read_reference(worker.store.root, record.classificationRef))
    )
    assert code == 0 and report.divergence.signature == evidence.referenceSignature
    _, code_bytes = download(worker.store, record, "regression-test")
    ast.parse(code_bytes)
    namespace = {}
    exec(compile(code_bytes, "regression_test.py", "exec"), namespace)

    class Harness:
        def __init__(self, role):
            self.role = role
            self.statements = []

        @contextmanager
        def disposable_graph(self):
            yield self

        def execute_setup(self, statement):
            self.statements.append(statement)

        def observe(self, query, parameters, policy):
            assert (
                query == case.query
                and parameters == case.parameters
                and policy == case.observation.model_dump()
            )
            assert self.statements == case.setup
            actual, _, exit_code = run_case(
                data, case, record.snapshot.pairId, tmp_path
            )
            assert exit_code == 0
            return material(getattr(actual.observations, self.role), case.observation)

        def reset(self):
            self.statements = []

    namespace["test_recorded_behavior"](Harness("baseline"))
    with pytest.raises(AssertionError, match="crashed"):
        namespace["test_recorded_behavior"](Harness("target"))
    assert worker.step(record.snapshot.id) == record
    assert [
        e.model_dump() for e in conclusion_page(worker.store, record).memory.entries
    ] == before
    assert download(worker.store, record, "regression-test")[1] == code_bytes


def test_download_routes_reject_foreign_keys_and_corrupt_bytes(completed, monkeypatch):
    worker, record = completed
    monkeypatch.setattr(
        "faultglass.investigation_api.GraphRepository", lambda: worker.repository
    )
    # Keep this disposable repository connected across test-client reads.
    monkeypatch.setattr(worker.repository, "close", lambda: None)
    client = TestClient(api.app)
    base = "/api/investigations/" + record.snapshot.id
    response = client.get(base + "/export/regression-test")
    assert response.status_code == 200
    assert "attachment;" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "private, no-store"
    assert client.get(base + "/export/unknown").status_code == 422
    assert client.get(base + "/conclusion?cursor=-1").status_code == 422
    assert client.get("/api/investigations/not-an-id/export/case").status_code == 422
    file = conclusion_page(worker.store, record).exports.files[1]
    (worker.store.root / file.owner / file.path).write_bytes(b"changed")
    assert client.get(base + "/export/regression-test").status_code == 409


def test_export_receipt_survives_memory_acknowledgement_loss(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULTGLASS_INVESTIGATION_MODE", "deterministic_diagnostic")
    repo = GraphRepository(
        ContextConfig(graph="faultglass__test_" + uuid4().hex, artifact_root=tmp_path)
    )
    repo.ensure_schema()
    worker = Worker(repo)
    record, _ = worker.store.admit(
        Admission(caseFile=encode(FLAGSHIP).decode(), pairId="call-yield-c-rust"),
        str(uuid4()),
    )
    try:
        record = finish(worker, record, lambda r: r.exportRef is not None)
        original = repo._query
        lost = []

        def query(name, params=None, **kwargs):
            result = original(name, params, **kwargs)
            if name == "runtime-commit" and params.get("MemoryUpdates"):
                lost.append(params["id"])
                raise ContextUnavailable()
            return result

        monkeypatch.setattr(repo, "_query", query)
        completed = worker.step(record.snapshot.id)
        assert completed.snapshot.status == Status.COMPLETE and lost == [
            record.snapshot.id
        ]
        memory = conclusion_page(worker.store, completed).memory
        assert all(entry.after.attempts == 1 for entry in memory.entries)
        worker = Worker(repo)
        for _ in range(3):
            assert worker.step(record.snapshot.id).receiptKey == completed.receiptKey
        assert all(
            entry.after.attempts == 1
            for entry in conclusion_page(worker.store, completed).memory.entries
        )
    finally:
        repo.graph.delete()
        repo.close()


@pytest.mark.parametrize("failure", ["export", "memory"])
def test_required_publication_failure_preserves_verified_evidence(
    tmp_path, monkeypatch, failure
):
    from faultglass.analysis_artifacts import AnalysisStore

    monkeypatch.setenv("FAULTGLASS_INVESTIGATION_MODE", "deterministic_diagnostic")
    repo = GraphRepository(
        ContextConfig(graph="faultglass__test_" + uuid4().hex, artifact_root=tmp_path)
    )
    repo.ensure_schema()
    worker = Worker(repo)
    record, _ = worker.store.admit(
        Admission(caseFile=encode(FLAGSHIP).decode(), pairId="call-yield-c-rust"),
        str(uuid4()),
    )
    try:
        record = finish(worker, record, lambda r: r.snapshot.status == Status.EXPORTING)
        if failure == "export":
            original = AnalysisStore.put

            def denied(self, name, data, **kwargs):
                if kwargs.get("key") == "report":
                    raise OSError("Controlled storage failure")
                return original(self, name, data, **kwargs)

            monkeypatch.setattr(AnalysisStore, "put", denied)
        else:
            record = finish(worker, record, lambda r: r.exportRef is not None)

            def denied(*args, **kwargs):
                raise OSError("Controlled storage failure")

            monkeypatch.setattr(worker.finishing.memory, "prepare", denied)
        final = worker.step(record.snapshot.id)
        assert final.snapshot.status == Status.FAILED
        assert final.snapshot.terminalReason.code == failure + "_failure"
        assert final.memoryRef is None
        assert (final.exportRef is not None) == (failure == "memory")
        assert repo.graph.ro_query(
            "MATCH (:Probe)-[e:EFFECTIVE_FOR]->() RETURN count(e)"
        ).result_set == [[0]]
        if failure == "memory":
            assert download(worker.store, final, "case")[1]
        else:
            assert repo.graph.ro_query(
                "MATCH (r:RegressionTest) RETURN count(r)"
            ).result_set == [[0]]
    finally:
        repo.graph.delete()
        repo.close()


def test_fresh_related_ranking_preserves_exact_contributor_provenance(completed):
    from faultglass.analysis_models import HistoricalInfluence
    from faultglass.public_cases import RELATED

    worker, original = completed
    fresh, _ = worker.store.admit(
        Admission(caseFile=encode(RELATED).decode(), pairId="call-yield-c-rust"),
        str(uuid4()),
    )
    assert (
        fresh.snapshot.id != original.snapshot.id
        and fresh.admissionKey != original.admissionKey
    )
    fresh = finish(worker, fresh)
    assert fresh.snapshot.status == Status.COMPLETE
    assert fresh.snapshot.conclusion.state == "matched"
    assert fresh.snapshot.conclusion.familyId == original.snapshot.conclusion.familyId
    influence = HistoricalInfluence.model_validate(
        loads(read_reference(worker.store.root, fresh.influenceRef))
    )
    assert influence.priorInvestigationIds == [original.snapshot.id]
    before = [r.probeId for r in influence.withoutHistory]
    after = [r.probeId for r in influence.withHistory]
    assert influence.changed == (before != after)
    assert influence.selectedProbeId == after[0]
    page = conclusion_page(worker.store, fresh)
    assert all(
        entry.before.attempts == 1 and entry.after.attempts == 2
        for entry in page.memory.entries
    )
    history = worker.repository.get_fingerprint_history(fresh.snapshot.fingerprintId)
    assert all(
        {episode.investigation.properties["id"] for episode in row.supporting_episodes}
        == {original.snapshot.id, fresh.snapshot.id}
        for row in history.candidates
    )
    print(
        "Related action:",
        original.snapshot.id,
        fresh.snapshot.id,
        "without",
        before,
        "with",
        after,
        "changed",
        influence.changed,
        flush=True,
    )
