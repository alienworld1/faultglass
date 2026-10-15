import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from docker.errors import APIError
from docker.models.containers import Container

from faultglass import probe_service
from faultglass.artifacts import ArtifactStore
from faultglass.context_config import ContextConfig
from faultglass.context_errors import ContextError
from faultglass.execution import run_case
from faultglass.graph_repository import GraphRepository
from faultglass.models import read_case
from faultglass.planning_artifacts import PlanningStore
from faultglass.probe_service import execute_probe, plan_probe, saved_action
from faultglass.runner import OWNER, DockerRunner, docker_client
from faultglass.transport import ExecTransport

pytestmark = pytest.mark.docker


@pytest.fixture(scope="module")
def original_seed(tmp_path_factory):
    root = tmp_path_factory.mktemp("original-experiment-evidence")
    data = (
        Path(__file__).parents[1] / "fixtures/call-yield.faultglass.json"
    ).read_bytes()
    report, _, code = run_case(data, read_case(data), "call-yield-c-rust", root)
    assert code == 0, "Prepare Docker and both approved local engine images."
    return root, report.runId


@pytest.fixture
def action(original_seed, tmp_path):
    source, seed = original_seed
    root = tmp_path / "evidence"
    shutil.copytree(source, root)
    repo = GraphRepository(
        ContextConfig(graph="faultglass__test_" + uuid4().hex, artifact_root=root)
    )
    repo.ensure_schema()
    repo.record_seed_context(seed)
    plan_probe(repo, seed)
    try:
        yield repo, seed, PlanningStore(root, seed)
    finally:
        repo.graph.delete()
        repo.close()


def forbidden(*args, **kwargs):
    pytest.fail("An admitted experiment must not be executed twice.")


def test_interrupted_child_is_preserved_and_never_resumed(action, monkeypatch):
    repo, seed, store = action
    original = ExecTransport.command

    def interrupt_focal(self, *args, **kwargs):
        if args[0] == "GRAPH.QUERY":
            raise KeyboardInterrupt()
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ExecTransport, "command", interrupt_focal)
    view = execute_probe(repo, seed)
    assert view["exit_code"] == 130 and view["result"] is None
    assert store.journal().state == "incomplete"
    child = store.journal().child_evidence_id
    assert not (store.root / child / "manifest.json").exists()
    monkeypatch.setattr(probe_service, "run_case", forbidden)
    with pytest.raises(ContextError, match="previous experiment did not finish"):
        execute_probe(repo, seed)
    inspected = saved_action(repo, seed, commit=True)
    assert inspected["result"] is None and inspected["execution_state"] == "incomplete"
    assert inspected["recovery_command"].endswith(child)
    client = docker_client()
    try:
        assert not client.containers.list(
            all=True, filters={"label": f"{OWNER}={child}"}
        )
    finally:
        client.close()


@pytest.mark.parametrize("failure", ["normalization", "storage", "cleanup"])
def test_infrastructure_failure_never_becomes_a_completed_observation(
    action, monkeypatch, failure
):
    repo, seed, store = action
    remove = Container.remove
    if failure == "normalization":
        original = DockerRunner.execute_pair

        def invalid_value(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("Unsupported engine value")

        monkeypatch.setattr(DockerRunner, "execute_pair", invalid_value)
    elif failure == "storage":
        original = ArtifactStore.write

        def full(self, kind, data, *args, **kwargs):
            if kind == "normalized-pair":
                raise OSError("Injected storage failure")
            return original(self, kind, data, *args, **kwargs)

        monkeypatch.setattr(ArtifactStore, "write", full)
    else:

        def removal_failure(*args, **kwargs):
            raise APIError("Injected cleanup failure")

        monkeypatch.setattr(Container, "remove", removal_failure)
    try:
        view = execute_probe(repo, seed)
        assert view["exit_code"] == 1 and view["result"] is None
        assert store.journal().state == "incomplete"
        assert not (
            store.root / store.journal().child_evidence_id / "manifest.json"
        ).exists()
        assert repo.graph.ro_query(
            "MATCH (:Investigation {id:$id})-[:EXECUTED_AS {sequence:1}]->(r:Run) RETURN count(r)",
            {"id": seed},
        ).result_set == [[0]]
    finally:
        monkeypatch.setattr(Container, "remove", remove)
        client = docker_client()
        try:
            for container in client.containers.list(
                all=True,
                filters={"label": f"{OWNER}={store.journal().child_evidence_id}"},
            ):
                container.remove(force=True, v=True)
        finally:
            client.close()


def test_complete_manifest_reconciles_after_result_write_interruption_without_engines(
    action, monkeypatch
):
    repo, seed, store = action
    original = PlanningStore.put

    def interrupted_result(self, filename, data, **kwargs):
        if filename == "result.json":
            raise KeyboardInterrupt()
        return original(self, filename, data, **kwargs)

    monkeypatch.setattr(PlanningStore, "put", interrupted_result)
    with pytest.raises(KeyboardInterrupt):
        execute_probe(repo, seed)
    child = store.journal().child_evidence_id
    assert (store.root / child / "manifest.json").exists()
    monkeypatch.setattr(PlanningStore, "put", original)
    monkeypatch.setattr(probe_service, "run_case", forbidden)
    recovered = saved_action(repo, seed, commit=True)
    assert recovered["result"]["child_evidence_id"] == child
    assert (
        not recovered["commit_pending"] and store.journal().state == "evidence_complete"
    )


def test_budget_refusal_precedes_child_reservation_and_provisioning(
    action, monkeypatch
):
    repo, seed, store = action
    moments = iter([0.0, 100.0])
    monkeypatch.setattr(
        probe_service, "time", SimpleNamespace(monotonic=lambda: next(moments))
    )
    monkeypatch.setattr(probe_service, "run_case", forbidden)
    view = execute_probe(repo, seed)
    assert view["reason"] == "budget_exhausted"
    assert store.journal() is None


def test_fully_captured_query_timeouts_remain_comparable_observations(
    action, monkeypatch
):
    from faultglass.errors import DeadlineExceeded

    repo, seed, _ = action
    original = ExecTransport.command

    def timeout_focal(self, *args, **kwargs):
        if args[0] == "GRAPH.QUERY" and args[2].lstrip().startswith("CALL "):
            raise DeadlineExceeded()
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ExecTransport, "command", timeout_focal)
    view = execute_probe(repo, seed)
    assert not view["commit_pending"]
    assert view["result"]["paired_statuses"] == {
        "baseline": "timeout",
        "target": "timeout",
    }
    assert view["result"]["relationship"] == "eliminated"
