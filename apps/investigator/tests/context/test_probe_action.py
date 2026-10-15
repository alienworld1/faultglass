import shutil
from uuid import uuid4

import pytest
from test_history import install_history

from faultglass.context_artifacts import load_evidence
from faultglass.context_config import ContextConfig
from faultglass.context_errors import ContextUnavailable, IdentityConflict
from faultglass.context_models import VersionScope
from faultglass.graph_repository import GraphRepository
from faultglass.jsonio import encode
from faultglass.probe_graph import catalog
from faultglass.probe_registry import REGISTRY
from faultglass.probe_service import execute_probe, plan_probe, saved_action

pytestmark = pytest.mark.context


@pytest.fixture
def repository(completed_evidence, tmp_path):
    source, _ = completed_evidence
    root = tmp_path / "evidence"
    shutil.copytree(source, root, ignore=shutil.ignore_patterns("planning", "context"))
    repo = GraphRepository(
        ContextConfig(graph="faultglass__test_" + uuid4().hex, artifact_root=root)
    )
    repo.ensure_schema()
    try:
        yield repo
    finally:
        repo.graph.delete()
        repo.close()


def register_history(repository, receipt, definition):
    assert repository.config.graph.startswith("faultglass__test_")
    install_history(repository, receipt)
    context = repository.get_investigation_context(receipt.investigation_id)
    scope = VersionScope(
        baseline=context.runs[0].engine.properties["id"],
        target=context.runs[1].engine.properties["id"],
        comparison_version="paired-evidence-v1/typed-values-v1",
    )
    repository.graph.query("MATCH (p:Probe {id:'synthetic-probe-a'}) DETACH DELETE p")
    repository.graph.query(
        """MATCH (p:Probe {id:$id}), (f:FaultFamily {id:'synthetic-family-a'})
    CREATE (p)-[:EFFECTIVE_FOR {id:'synthetic-registered-effectiveness',created_at:$now,source_kind:'verified_classification',
    source_id:$ref,attempts:4,successes:3,avg_cost_ms:20.0,last_seen_at:$now,version_scope:$scope}]->(f)""",
        {
            "id": definition.id,
            "now": context.investigation.properties["created_at"],
            "ref": context.investigation.properties["report_artifact_ref"],
            "scope": encode(scope.model_dump()).decode(),
        },
    )


def test_cold_start_executes_once_and_seed_receipt_remains_immutable(
    repository, completed_evidence
):
    _, reports = completed_evidence
    root = repository.config.artifact_root
    receipt = repository.record_seed_context(reports[0].runId)
    seed_bytes = (root / reports[0].runId / "manifest.json").read_bytes()
    context_bytes = (root / reports[0].runId / "context/manifest.json").read_bytes()
    view = plan_probe(repository, reports[0].runId)
    assert view["decision"]["novel"] and len(view["decision"]["candidates"]) == 2
    assert view["decision"]["selected_probe_id"] == REGISTRY[0].id
    assert not view["reused"]
    again = plan_probe(repository, reports[0].runId)
    assert again["reused"] and again["decision"] == view["decision"]
    executed = execute_probe(repository, reports[0].runId)
    assert executed["result"]["relationship"] in ("preserved", "eliminated", "changed")
    child = executed["result"]["child_evidence_id"]
    assert load_evidence(root, child)[1].runId == child
    assert not (root / child / "context").exists()
    assert execute_probe(repository, reports[0].runId)["reused"]
    replayed_plan = plan_probe(repository, reports[0].runId)
    assert (
        replayed_plan["result"] == executed["result"]
        and replayed_plan["execution_state"] == "evidence_complete"
    )
    assert (
        saved_action(repository, reports[0].runId, commit=True)["result"]
        == executed["result"]
    )
    assert saved_action(repository, reports[0].runId)["result"] == executed["result"]
    assert len(repository.get_investigation_context(reports[0].runId).runs) == 2
    assert (
        repository.record_seed_context(reports[0].runId).context_payload_sha256
        == receipt.context_payload_sha256
    )
    assert (root / reports[0].runId / "manifest.json").read_bytes() == seed_bytes
    assert (
        root / reports[0].runId / "context/manifest.json"
    ).read_bytes() == context_bytes
    assert repository.graph.ro_query(
        "MATCH (:Investigation {id:$id})-[:EXECUTED_AS {sequence:1}]->(r:Run) RETURN count(r)",
        {"id": reports[0].runId},
    ).result_set == [[2]]
    assert repository.graph.ro_query(
        "MATCH (:FaultFamily) RETURN count(*)"
    ).result_set == [[0]]
    assert repository.graph.ro_query(
        "MATCH ()-[e:EFFECTIVE_FOR]->() RETURN count(e)"
    ).result_set == [[0]]


def test_relevant_history_changes_selected_real_action_and_path_removal_restores_fallback(
    repository, completed_evidence
):
    _, reports = completed_evidence
    root = repository.config.artifact_root
    historical = repository.record_seed_context(reports[0].runId)
    cold = plan_probe(repository, historical.investigation_id)
    assert cold["decision"]["selected_probe_id"] == REGISTRY[0].id
    catalog(repository, bootstrap=True)
    seed = repository.record_seed_context(reports[1].runId)
    register_history(repository, historical, REGISTRY[1])
    view = plan_probe(repository, seed.investigation_id)
    assert view["decision"]["selected_probe_id"] == REGISTRY[1].id
    assert not view["decision"]["novel"]
    winner = view["decision"]["candidates"][0]
    assert winner["version_affinity"] == 1.0 and winner["attempts"] == 4
    result = execute_probe(repository, seed.investigation_id)
    assert (
        "OPTIONAL MATCH"
        in load_evidence(root, result["result"]["child_evidence_id"])[0].query
    )
    assert repository.graph.ro_query(
        "MATCH ()-[e:EFFECTIVE_FOR]->() RETURN e.attempts,e.successes"
    ).result_set == [[4, 3]]
    repository.graph.query("MATCH ()-[e:EFFECTIVE_FOR]->() SET e.successes=0")
    assert (
        saved_action(repository, seed.investigation_id)["decision"] == view["decision"]
    )
    assert repository.graph.ro_query(
        "MATCH ()-[e:EFFECTIVE_FOR]->() RETURN e.attempts,e.successes"
    ).result_set == [[4, 0]]
    repository.graph.query("MATCH (:FaultFamily)-[e:INVOLVES_FEATURE]->() DELETE e")
    assert not repository.get_fingerprint_history(
        seed.fingerprint_id, exclude_id=seed.investigation_id
    ).candidates
    restored = plan_probe(repository, historical.investigation_id)
    assert (
        restored["decision"]["novel"]
        and restored["decision"]["selected_probe_id"] == REGISTRY[0].id
    )


def test_lost_acknowledgment_and_post_execution_outage_reconcile_without_rerun(
    repository, completed_evidence, monkeypatch
):
    _, reports = completed_evidence
    seed = repository.record_seed_context(reports[0].runId)
    original = repository._query

    def lost_ack(name, *args, **kwargs):
        result = original(name, *args, **kwargs)
        if name in ("probe-selection", "probe-observation"):
            raise ContextUnavailable()
        return result

    monkeypatch.setattr(repository, "_query", lost_ack)
    assert plan_probe(repository, seed.investigation_id)["selection_receipt"]
    monkeypatch.setattr(repository, "_query", original)

    def outage(name, *args, **kwargs):
        if name == "probe-observation":
            raise ContextUnavailable()
        return original(name, *args, **kwargs)

    monkeypatch.setattr(repository, "_query", outage)
    pending = execute_probe(repository, seed.investigation_id)
    assert pending["result"] and pending["commit_pending"]
    monkeypatch.setattr(repository, "_query", lost_ack)
    from faultglass import probe_service

    monkeypatch.setattr(
        probe_service,
        "run_case",
        lambda *args, **kwargs: pytest.fail(
            "Saved observations must never rerun engines."
        ),
    )
    repaired = saved_action(repository, seed.investigation_id, commit=True)
    assert not repaired["commit_pending"] and repaired["result"] == pending["result"]
    assert repaired["observation_receipt"]["reused"]


def test_nonreproduced_and_disabled_selection_never_start_engines(
    repository, completed_evidence, monkeypatch
):
    _, reports = completed_evidence
    matching = repository.record_seed_context(reports[2].runId)
    assert (
        plan_probe(repository, matching.investigation_id)["decision"]["outcome"]
        == "not_reproduced"
    )
    seed = repository.record_seed_context(reports[0].runId)
    plan = plan_probe(repository, seed.investigation_id)
    repository.graph.query(
        "MATCH (p:Probe {id:$id}) SET p.enabled=false",
        {"id": plan["decision"]["selected_probe_id"]},
    )
    from faultglass import probe_service

    monkeypatch.setattr(
        probe_service,
        "run_case",
        lambda *args, **kwargs: pytest.fail("Disabled selections must not execute."),
    )
    with pytest.raises(ValueError, match="no longer available"):
        execute_probe(repository, seed.investigation_id)
    repository.graph.query(
        "MATCH (i:Investigation {id:$id}) SET i.selection_payload_sha256=$hash",
        {"id": seed.investigation_id, "hash": "0" * 64},
    )
    with pytest.raises(IdentityConflict):
        saved_action(repository, seed.investigation_id)


@pytest.mark.parametrize("phase", ["selection", "observation"])
def test_phase_runtime_failure_rolls_back_receipt_and_all_links(
    repository, completed_evidence, monkeypatch, phase
):
    from redis.exceptions import ResponseError

    from faultglass.graph_repository import query_text

    _, reports = completed_evidence
    seed = repository.record_seed_context(reports[0].runId)
    if phase == "observation":
        plan_probe(repository, seed.investigation_id)
    original = repository._query

    def fail_atomically(name, params=None, **kwargs):
        if name == "probe-" + phase:
            query = query_text(name).replace(
                "RETURN i.id", "SET i.invalid=1 / $zero RETURN i.id"
            )
            with pytest.raises(ResponseError, match="Division by zero"):
                repository.graph.query(query, {**params, "zero": 0}, timeout=2000)
            raise ContextUnavailable()
        return original(name, params, **kwargs)

    monkeypatch.setattr(repository, "_query", fail_atomically)
    view = (execute_probe if phase == "observation" else plan_probe)(
        repository, seed.investigation_id
    )
    assert view["commit_pending"]
    assert repository._lookup(seed.investigation_id).get(phase + "_phase_key") is None
    assert "invalid" not in repository._lookup(seed.investigation_id)
    relation = "SELECTED_PROBE" if phase == "selection" else "EXECUTED_AS {sequence:1}"
    assert repository.graph.ro_query(
        "MATCH (:Investigation {id:$id})-[e:" + relation + "]->() RETURN count(e)",
        {"id": seed.investigation_id},
    ).result_set == [[0]]
    monkeypatch.setattr(repository, "_query", original)
    from faultglass import probe_service

    monkeypatch.setattr(
        probe_service,
        "run_case",
        lambda *args, **kwargs: pytest.fail("Commit must not execute engines."),
    )
    assert not saved_action(repository, seed.investigation_id, commit=True)[
        "commit_pending"
    ]


def test_concurrent_cli_plan_and_execute_converge_on_one_child(
    repository, completed_evidence
):
    import os
    import subprocess
    import sys

    from faultglass.jsonio import loads

    _, reports = completed_evidence
    seed = repository.record_seed_context(reports[0].runId)
    env = {
        **os.environ,
        "FAULTGLASS_ARTIFACT_ROOT": str(repository.config.artifact_root),
        "FAULTGLASS_CONTEXT_GRAPH": repository.config.graph,
        "NO_COLOR": "1",
    }
    for command in ("plan", "execute"):
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "faultglass.probe",
                    command,
                    "--evidence-id",
                    seed.investigation_id,
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(2)
        ]
        results = []
        for process in processes:
            out, err = process.communicate(timeout=30)
            assert process.returncode == 0, err.decode()
            results.append(loads(out))
        assert sorted(view["reused"] for view in results) == [False, True]
        assert results[0]["decision"] == results[1]["decision"]
        if command == "execute":
            assert results[0]["result"] == results[1]["result"]
    assert repository.graph.ro_query(
        "MATCH (:Investigation {id:$id})-[:EXECUTED_AS {sequence:1}]->(r:Run) RETURN count(r)",
        {"id": seed.investigation_id},
    ).result_set == [[2]]


def test_overflow_corrupt_history_and_unavailable_memory_fail_without_execution(
    repository, completed_evidence, monkeypatch
):
    _, reports = completed_evidence
    source = repository.record_seed_context(reports[0].runId)
    seed = repository.record_seed_context(reports[1].runId)
    catalog(repository, bootstrap=True)
    register_history(repository, source, REGISTRY[1])
    from faultglass import probe_service

    monkeypatch.setattr(
        probe_service,
        "run_case",
        lambda *args, **kwargs: pytest.fail("Invalid context must not start engines."),
    )
    original = repository._query

    def overflow(name, params=None, **kwargs):
        rows = original(name, params, **kwargs)
        return rows * 101 if name == "history" else rows

    monkeypatch.setattr(repository, "_query", overflow)
    with pytest.raises(ValueError, match="supported planning limit"):
        plan_probe(repository, seed.investigation_id)
    monkeypatch.setattr(repository, "_query", original)
    repository.graph.query("MATCH ()-[e:EFFECTIVE_FOR]->() SET e.successes=999")
    with pytest.raises(ValueError, match="could not be verified"):
        plan_probe(repository, seed.investigation_id)
    repository.close()
    repository.config = repository.config.model_copy(update={"port": 1})
    try:
        with pytest.raises(ContextUnavailable):
            plan_probe(repository, seed.investigation_id)
    finally:
        repository.config = repository.config.model_copy(update={"port": 6380})
        repository._connect()


def test_reproduced_unsupported_shape_returns_no_applicable_probe(
    repository, completed_evidence
):
    from faultglass.execution import run_case
    from faultglass.models import read_case

    _, reports = completed_evidence
    original = load_evidence(repository.config.artifact_root, reports[0].runId)[0]
    data = encode(
        {
            **original.model_dump(),
            "query": "CALL db.labels() YIELD label MATCH (node:N)",
        }
    )
    report, _, code = run_case(
        data, read_case(data), "call-yield-c-rust", repository.config.artifact_root
    )
    assert code == 0 and report.outcome == "reproduced"
    repository.record_seed_context(report.runId)
    view = plan_probe(repository, report.runId)
    assert view["decision"]["outcome"] == "unresolved"
    assert view["decision"]["terminal_reason"] == "no_applicable_probe"
    assert not view["decision"]["candidates"]
    assert execute_probe(repository, report.runId)["result"] is None
