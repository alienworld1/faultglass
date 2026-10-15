import hashlib
import os
import shutil
import subprocess
import sys
from uuid import uuid4

import pytest
from redis.exceptions import ResponseError

from faultglass.artifacts import verify
from faultglass.context_artifacts import verify_sidecar
from faultglass.context_config import ContextConfig
from faultglass.context_errors import (
    ContextError,
    ContextUnavailable,
    EvidenceIntegrity,
    IdentityConflict,
    SchemaIncompatible,
)
from faultglass.context_phase import build_phase
from faultglass.graph_repository import INDEXES, GraphRepository, query_text
from faultglass.jsonio import encode, loads

pytestmark = pytest.mark.context


def counts(repo):
    return repo._query("counts")[0]


def test_empty_and_repeated_bootstrap_has_ready_indexes_without_fake_history(
    repository,
):
    before = counts(repository)
    assert before == [24, 0]
    assert repository.ensure_schema().indexes == 12
    assert counts(repository) == before
    assert set(INDEXES) <= repository._indexes()
    assert "Index Scan" in str(
        repository.graph.explain(query_text("lookup"), {"id": "lookup"})
    )
    assert set(row[0] for row in repository._query("labels")) <= {
        label for label, _ in INDEXES
    }


def test_seed_replay_fresh_episode_and_matching_preserve_evidence(
    repository, completed_evidence
):
    root, reports = completed_evidence
    first = repository.record_seed_context(reports[0].runId)
    before = counts(repository)
    replay = repository.record_seed_context(reports[0].runId)
    assert (
        replay.reused and replay.context_payload_sha256 == first.context_payload_sha256
    )
    assert counts(repository) == before
    second = repository.record_seed_context(reports[1].runId)
    assert (
        first.fault_case_id == second.fault_case_id
        and first.fingerprint_id == second.fingerprint_id
    )
    assert second.investigation_id != first.investigation_id
    assert counts(repository) == [before[0] + 4, before[1] + 7]
    context = repository.get_investigation_context(first.investigation_id)
    assert {"CALL", "YIELD", "MATCH"} <= set(context.features)
    assert [r.run.properties["role"] for r in context.runs] == ["baseline", "target"]
    assert len({r.run.properties["id"] for r in context.runs}) == 2
    assert context.divergence.properties["stable"] is False
    assert context.runs[0].run.properties["status"] == "error"
    assert context.runs[1].run.properties["status"] == "crash"
    matching = repository.record_seed_context(reports[2].runId)
    matched = repository.get_investigation_context(matching.investigation_id)
    assert matched.investigation.properties["status"] == "NOT_REPRODUCED"
    assert matched.divergence is None
    assert repository.get_fingerprint_history(first.fingerprint_id).candidates == []
    for report in reports:
        assert verify(root / report.runId) == 6
        assert len(verify_sidecar(root, report.runId)) == 3
    assert not repository.graph.ro_query("MATCH (n:FaultFamily) RETURN n").result_set
    assert not repository.graph.ro_query("MATCH (n:Probe) RETURN n").result_set


def test_real_phase_rolls_back_runtime_failure_and_write_timeout(
    repository, completed_evidence
):
    root, reports = completed_evidence
    phase = build_phase(root, reports[0].runId)
    params = repository._parameters(phase)
    params["zero"] = 0
    query = query_text("record-seed").replace(
        "RETURN i.id, i.context_phase_key, i.context_payload_sha256",
        "SET i.invalid=1 / $zero RETURN i.id",
    )
    before = counts(repository)
    with pytest.raises(ResponseError, match="Division by zero"):
        repository.graph.query(query, params, timeout=2000)
    assert counts(repository) == before
    assert repository._lookup(reports[0].runId) is None
    with pytest.raises(ResponseError, match="timed out"):
        repository.graph.query(
            "UNWIND range(1,1000000) AS x CREATE (:Run {id:toString(x)}) RETURN count(*)",
            timeout=1,
        )
    assert counts(repository) == before
    assert repository.record_seed_context(reports[0].runId).reused is False


def test_acknowledgment_loss_reconciles_receipt_without_a_second_mutation(
    repository, completed_evidence, monkeypatch
):
    _, reports = completed_evidence
    original = repository._query
    writes = []

    def lost_ack(name, *args, **kwargs):
        result = original(name, *args, **kwargs)
        if name == "record-seed":
            writes.append(name)
            raise ContextUnavailable()
        return result

    monkeypatch.setattr(repository, "_query", lost_ack)
    receipt = repository.record_seed_context(reports[0].runId)
    assert receipt.reused and writes == ["record-seed"]
    before = counts(repository)
    assert repository.record_seed_context(reports[0].runId) == receipt
    assert counts(repository) == before


def test_interrupted_submission_without_receipt_can_be_retried(
    repository, completed_evidence, monkeypatch
):
    _, reports = completed_evidence
    original = repository._query

    def no_submission(name, *args, **kwargs):
        if name == "record-seed":
            raise ContextUnavailable()
        return original(name, *args, **kwargs)

    monkeypatch.setattr(repository, "_query", no_submission)
    with pytest.raises(ContextError, match="interrupted"):
        repository.record_seed_context(reports[0].runId)
    assert counts(repository) == [24, 0]
    monkeypatch.setattr(repository, "_query", original)
    assert not repository.record_seed_context(reports[0].runId).reused


def test_conflicting_receipt_and_canonical_properties_do_not_overwrite(
    repository, completed_evidence
):
    _, reports = completed_evidence
    receipt = repository.record_seed_context(reports[0].runId)
    repository.graph.query(
        "MATCH (i:Investigation {id:$id}) SET i.context_payload_sha256=$hash",
        {"id": receipt.investigation_id, "hash": "0" * 64},
    )
    before = counts(repository)
    with pytest.raises(IdentityConflict):
        repository.record_seed_context(receipt.investigation_id)
    assert counts(repository) == before
    assert (
        repository._lookup(receipt.investigation_id)["context_payload_sha256"]
        == "0" * 64
    )
    repository.graph.query(
        "MATCH (c:FaultCase {id:$id}) SET c.query_sha256=$hash",
        {"id": receipt.fault_case_id, "hash": "0" * 64},
    )
    with pytest.raises(IdentityConflict):
        repository.record_seed_context(reports[1].runId)
    assert counts(repository) == before
    assert repository._lookup(reports[1].runId) is None


@pytest.mark.parametrize(
    "change", ["missing", "hash", "symlink", "sidecar", "sidecar_missing", "manifest"]
)
def test_evidence_damage_fails_before_any_graph_write_and_can_be_restored(
    repository, completed_evidence, tmp_path, monkeypatch, change
):
    root, reports = completed_evidence
    run_id = reports[0].runId
    copy = tmp_path / "copy"
    copy.mkdir(mode=0o700)
    shutil.copytree(root / run_id, copy / run_id)
    repository.config = repository.config.model_copy(update={"artifact_root": copy})
    source = copy / run_id
    manifest = loads((source / "manifest.json").read_bytes())
    file = source / manifest["artifacts"][0]["path"]
    if change in ("sidecar", "sidecar_missing"):
        build_phase(copy, run_id)
        file = source / "context" / "identity.json"
    original = file.read_bytes()
    if change in ("missing", "sidecar_missing"):
        file.unlink()
    elif change == "symlink":
        file.unlink()
        file.symlink_to(root / run_id / manifest["artifacts"][0]["path"])
    elif change == "manifest":
        manifest["artifacts"].append(manifest["artifacts"][0])
        (source / "manifest.json").write_bytes(encode(manifest))
    else:
        file.write_bytes(b"changed")
    before = counts(repository)
    writes = []
    query = repository._query

    def observed(name, *args, **kwargs):
        if kwargs.get("write"):
            writes.append(name)
        return query(name, *args, **kwargs)

    monkeypatch.setattr(repository, "_query", observed)
    with pytest.raises((EvidenceIntegrity, IdentityConflict, ContextError)):
        repository.record_seed_context(run_id)
    assert writes == [] and counts(repository) == before
    if change == "manifest":
        shutil.copyfile(root / run_id / "manifest.json", source / "manifest.json")
    else:
        file.unlink(missing_ok=True)
        file.write_bytes(original)
        file.chmod(0o600)
    assert not repository.record_seed_context(run_id).reused


def test_unsupported_comparator_and_report_disagreement_reject_before_writes(
    repository, completed_evidence, tmp_path
):
    root, reports = completed_evidence
    copy = tmp_path / "comparison"
    copy.mkdir(mode=0o700)
    run_id = reports[0].runId
    shutil.copytree(root / run_id, copy / run_id)
    manifest_path = copy / run_id / "manifest.json"
    manifest = loads(manifest_path.read_bytes())
    ref = next(r for r in manifest["artifacts"] if r["kind"] == "normalized-pair")
    file = copy / run_id / ref["path"]
    normalized = loads(file.read_bytes())
    normalized["comparisonVersion"] = "unknown-version"
    data = encode(normalized)
    file.write_bytes(data)
    ref.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    manifest_path.write_bytes(encode(manifest))
    repository.config = repository.config.model_copy(update={"artifact_root": copy})
    with pytest.raises(ContextError, match="compatible version"):
        repository.record_seed_context(run_id)
    assert counts(repository) == [24, 0]


def test_two_cli_writers_converge_and_process_restart_preserves_context(
    repository, completed_evidence
):
    root, reports = completed_evidence
    env = {
        **os.environ,
        "FAULTGLASS_ARTIFACT_ROOT": str(root),
        "FAULTGLASS_CONTEXT_GRAPH": repository.config.graph,
    }
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "faultglass.context",
                "record",
                "--evidence-id",
                r.runId,
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for r in reports[:2]
    ]
    results = []
    for process in processes:
        out, err = process.communicate(timeout=20)
        assert process.returncode == 0, err.decode()
        results.append(loads(out))
    assert results[0]["fault_case_id"] == results[1]["fault_case_id"]
    assert results[0]["fingerprint_id"] == results[1]["fingerprint_id"]
    rows = repository.graph.ro_query("MATCH (n:FaultCase) RETURN count(n)").result_set
    assert rows == [[1]]
    repository.close()
    for report in reports[:2]:
        assert (
            repository.get_investigation_context(report.runId).investigation.properties[
                "id"
            ]
            == report.runId
        )


def test_missing_and_invalid_identity_and_duplicate_schema_fail_explicitly(repository):
    with pytest.raises(ContextError, match="couldn't find that saved"):
        repository.get_investigation_context(str(uuid4()))
    with pytest.raises(ContextError, match="couldn't find that fingerprint"):
        repository.get_fingerprint_history("0" * 64)
    for value in ("../escape", "not-a-uuid", "A" * 64):
        with pytest.raises(ValueError):
            repository.record_seed_context(value)
        with pytest.raises(ValueError):
            repository.get_fingerprint_history(value)
    repository.graph.query("CREATE (:Feature {id:'CALL'})")
    with pytest.raises(SchemaIncompatible):
        repository.ensure_schema()


def test_unavailable_context_is_never_empty_history_or_success(completed_evidence):
    root, reports = completed_evidence
    repo = GraphRepository(ContextConfig(port=1, artifact_root=root))
    try:
        for action in (
            lambda: repo.ensure_schema(),
            lambda: repo.record_seed_context(reports[0].runId),
            lambda: repo.get_investigation_context(reports[0].runId),
            lambda: repo.get_fingerprint_history("0" * 64),
        ):
            with pytest.raises(ContextUnavailable):
                action()
    finally:
        repo.close()
