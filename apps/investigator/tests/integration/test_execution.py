import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
from docker.errors import APIError
from fastapi.testclient import TestClient

from faultglass.api import app
from faultglass.artifacts import verify
from faultglass.errors import DeadlineExceeded, ExecutionFailure
from faultglass.execution import run_case
from faultglass.jsonio import encode, loads
from faultglass.matrix import engines_for
from faultglass.models import RunLimits, read_case
from faultglass.runner import OWNER, DockerRunner, docker_client, verify_images
from faultglass.transport import ExecTransport

pytestmark = pytest.mark.docker
FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def client():
    connection = docker_client()
    verify_images(connection, engines_for("call-yield-c-rust"))
    yield connection
    connection.close()


def run_fixture(name, root, limits=None):
    data = (FIXTURES / (name + ".faultglass.json")).read_bytes()
    return run_case(data, read_case(data), "call-yield-c-rust", root, limits)


def test_real_seed_repeats_with_fresh_isolated_evidence(client, tmp_path):
    signatures, containers = [], []
    for _ in range(3):
        report, path, code = run_fixture("call-yield", tmp_path)
        assert code == 0 and report.outcome == "reproduced"
        assert report.observations.baseline.status == "error"
        assert report.observations.target.status == "crash"
        assert verify(path) == 6
        metadata = [
            loads((path / ref.path).read_bytes())
            for ref in report.artifacts
            if ref.kind.startswith("raw-")
        ]
        assert (
            metadata[0]["executableInputDigest"] == metadata[1]["executableInputDigest"]
        )
        for value in metadata:
            assert value["cleanup"] == "removed"
            assert value["runtimeProfile"]["NetworkMode"] == "none"
            assert not value["runtimeProfile"]["PortBindings"]
            containers.append(value["containerId"])
        signatures.append(report.divergence.signature)
        assert not client.containers.list(
            all=True, filters={"label": f"{OWNER}={report.runId}"}
        )
    assert len(set(signatures)) == 1 and len(set(containers)) == 6
    assert TestClient(app).get("/api/health").json()["executionReady"] is True
    matching, path, code = run_fixture("matching", tmp_path)
    assert (
        code == 0
        and matching.outcome == "not_reproduced"
        and matching.divergence is None
    )
    assert matching.oracleAssessment == {"baseline": "match", "target": "match"}
    assert verify(path) == 6


def test_real_readonly_state_parameters_graph_values_and_reset(client, tmp_path):
    case = {
        "schemaVersion": 1,
        "title": "State and typed values",
        "setup": ["CREATE (:N {v:1})-[:R {value:2}]->(:N {v:2})"],
        "query": "MATCH p=(a)-[r]->(b) CREATE (:Added) RETURN a, r, p, $v AS value",
        "parameters": {"v": {"a": [None, True, 2**60, 1.5]}},
        "observation": {
            "compareResult": True,
            "ordering": "ordered",
            "postconditions": [
                {"name": "nodes", "query": "MATCH (n) RETURN count(n) AS count"}
            ],
        },
    }
    for _ in range(2):
        data = encode(case)
        report, path, code = run_case(
            data, read_case(data), "call-yield-c-rust", tmp_path
        )
        assert code == 0 and report.outcome == "not_reproduced"
        for role in ("baseline", "target"):
            assert (
                getattr(report.observations, role)
                .postconditions[0]
                .value.rows[0][0]["value"]
                == "3"
            )
        assert verify(path) == 6


def test_real_sandbox_forbids_host_peer_and_external_routes(client):
    runner = DockerRunner(client, str(uuid4()))
    limits = RunLimits()
    runner.deadline = time.monotonic() + 60
    try:
        for role, engine in zip(
            ("baseline", "target"), engines_for("call-yield-c-rust"), strict=True
        ):
            container = runner.create(engine, role, limits)
            transport = ExecTransport(client, container, limits, runner.deadline)
            runner.ready(transport, container, limits)
            checked = container.exec_run(["cat", "/proc/net/route"]).output.decode()
            assert len(checked.strip().splitlines()) == 1
            for host in ("172.17.0.1", "1.1.1.1", "192.0.2.1"):
                response = container.exec_run(
                    ["timeout", "1", "redis-cli", "-h", host, "-p", "6379", "PING"]
                )
                assert response.exit_code != 0 and b"PONG" not in response.output
            assert not container.attrs["Mounts"]
            assert container.attrs["Config"]["User"] == "65534:65534"
            assert all(
                "SECRET" not in value and "API_KEY" not in value
                for value in container.attrs["Config"]["Env"]
            )
    finally:
        runner.cleanup(limits)
    assert not client.containers.list(
        all=True, filters={"label": f"{OWNER}={runner.run_id}"}
    )


def test_setup_output_storage_and_image_failures_never_complete(client, tmp_path):
    base = loads((FIXTURES / "matching.faultglass.json").read_bytes())
    data = encode({**base, "setup": ["THIS IS NOT CYPHER"]})
    report, path, code = run_case(data, read_case(data), "call-yield-c-rust", tmp_path)
    assert code == 1 and report.failure.stage == "setup" and path is None
    assert not (tmp_path / report.runId / "manifest.json").exists()
    assert not client.containers.list(
        all=True, filters={"label": f"{OWNER}={report.runId}"}
    )
    for query, limits in [
        ("UNWIND range(1,1001) AS v RETURN v", None),
        ("RETURN 1", RunLimits(artifactBytes=10)),
        ('RETURN "' + "x" * 2000 + '"', RunLimits(outputBytes=100)),
    ]:
        data = encode({**base, "query": query})
        report, path, code = run_case(
            data, read_case(data), "call-yield-c-rust", tmp_path, limits
        )
        assert code == 1 and report.outcome == "failed" and path is None
        assert not (tmp_path / report.runId / "manifest.json").exists()
        assert not client.containers.list(
            all=True, filters={"label": f"{OWNER}={report.runId}"}
        )
    missing = engines_for("call-yield-c-rust")[0].model_copy(
        update={
            "imageRef": "falkordb/falkordb@sha256:" + "0" * 64,
            "imageDigest": "sha256:" + "0" * 64,
        }
    )
    with pytest.raises(ExecutionFailure, match="isn't ready"):
        verify_images(client, [missing])


def test_injected_deadline_cleanup_failure_and_recovery(client, tmp_path, monkeypatch):
    original = ExecTransport.command

    def timeout_focal(self, *args, **kwargs):
        if args[0] == "GRAPH.QUERY":
            raise DeadlineExceeded()
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ExecTransport, "command", timeout_focal)
    report, path, code = run_fixture("matching", tmp_path)
    assert code == 0 and report.observations.baseline.status == "timeout"
    assert report.observations.target.status == "timeout"
    assert verify(path) == 6
    monkeypatch.setattr(ExecTransport, "command", original)
    from docker.models.containers import Container

    remove = Container.remove

    def fail_remove(self, **kwargs):
        raise APIError("injected removal failure")

    monkeypatch.setattr(Container, "remove", fail_remove)
    report, path, code = run_fixture("matching", tmp_path)
    assert code == 1 and report.failure.code == "cleanup" and path is None
    assert not (tmp_path / report.runId / "manifest.json").exists()
    owned = client.containers.list(
        all=True, filters={"label": f"{OWNER}={report.runId}"}
    )
    assert len(owned) == 2
    monkeypatch.setattr(Container, "remove", remove)
    subprocess.run(
        [sys.executable, "-m", "faultglass.recover", "--run-id", report.runId],
        check=True,
    )
    assert not client.containers.list(
        all=True, filters={"label": f"{OWNER}={report.runId}"}
    )


def test_interrupt_actual_command_leaves_incomplete_evidence_and_cleans(
    client, tmp_path
):
    case = loads((FIXTURES / "matching.faultglass.json").read_bytes())
    case["query"] = "UNWIND range(1,100000000) AS x WITH sum(x) AS s RETURN s"
    source = tmp_path / "long.faultglass.json"
    source.write_bytes(encode(case))
    environment = {**os.environ, "FAULTGLASS_ARTIFACT_ROOT": str(tmp_path / "evidence")}
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "faultglass.execution",
            "--case",
            str(source),
            "--pair",
            "call-yield-c-rust",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if client.containers.list(filters={"label": OWNER}):
                break
            assert process.poll() is None
            time.sleep(0.01)
        process.send_signal(signal.SIGINT)
        output, _ = process.communicate(timeout=15)
        assert process.returncode == 130
        report = loads(output)
        assert (
            report["outcome"] == "failed" and report["failure"]["code"] == "interrupted"
        )
        assert not (tmp_path / "evidence" / report["runId"] / "manifest.json").exists()
        assert not client.containers.list(
            all=True, filters={"label": f"{OWNER}={report['runId']}"}
        )
        assert TestClient(app).get("/api/health").status_code == 200
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_postcondition_crash_keeps_focal_result_and_records_skipped_checks(
    client, tmp_path, monkeypatch
):
    original = ExecTransport.command

    def crash_check(self, *args, **kwargs):
        if args[0] == "GRAPH.RO_QUERY":
            self.container.kill()
            raise ExecutionFailure(
                "transport",
                "postcondition",
                "The engine connection stopped unexpectedly.",
            )
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ExecTransport, "command", crash_check)
    case = loads((FIXTURES / "matching.faultglass.json").read_bytes())
    case["observation"]["postconditions"] = [
        {"name": "first", "query": "RETURN 1"},
        {"name": "later", "query": "RETURN 2"},
    ]
    data = encode(case)
    report, path, code = run_case(data, read_case(data), "call-yield-c-rust", tmp_path)
    assert code == 0
    for role in ("baseline", "target"):
        observed = getattr(report.observations, role)
        assert observed.status == "result"
        assert observed.postconditions[0].value.category == "CRASH"
        metadata = next(
            loads((path / ref.path).read_bytes())
            for ref in report.artifacts
            if ref.kind == "raw-" + role
        )
        assert metadata["skippedPostconditions"] == [
            {"name": "later", "reason": "engine_stopped"}
        ]
    assert verify(path) == 6


def test_creation_interruption_and_disk_failure_never_complete(
    client, tmp_path, monkeypatch
):
    from docker.models.containers import ContainerCollection

    from faultglass.artifacts import ArtifactStore

    original_create = ContainerCollection.create

    def interrupted_create(self, *args, **kwargs):
        original_create(self, *args, **kwargs)
        raise KeyboardInterrupt()

    monkeypatch.setattr(ContainerCollection, "create", interrupted_create)
    report, path, code = run_fixture("matching", tmp_path)
    assert code == 130 and path is None
    assert not client.containers.list(
        all=True, filters={"label": f"{OWNER}={report.runId}"}
    )
    assert not (tmp_path / report.runId / "manifest.json").exists()
    monkeypatch.setattr(ContainerCollection, "create", original_create)
    original_write = ArtifactStore.write

    def disk_full(self, kind, data, *args, **kwargs):
        if kind == "normalized-pair":
            raise OSError("injected disk quota failure")
        return original_write(self, kind, data, *args, **kwargs)

    monkeypatch.setattr(ArtifactStore, "write", disk_full)
    report, path, code = run_fixture("matching", tmp_path)
    assert code == 1 and path is None
    assert not (tmp_path / report.runId / "manifest.json").exists()
    assert not client.containers.list(
        all=True, filters={"label": f"{OWNER}={report.runId}"}
    )


def test_cleanup_deadline_surfaces_owned_resources_for_targeted_recovery(
    client, tmp_path, monkeypatch
):
    from docker.models.containers import Container

    original_logs = Container.logs

    def stalled_logs(self, **kwargs):
        time.sleep(2)
        return iter([b"late logs"])

    monkeypatch.setattr(Container, "logs", stalled_logs)
    started = time.monotonic()
    report, path, code = run_fixture("matching", tmp_path, RunLimits(cleanupSeconds=1))
    assert time.monotonic() - started < 5
    assert code == 1 and path is None and report.failure.code == "cleanup"
    assert not (tmp_path / report.runId / "manifest.json").exists()
    assert (
        len(
            client.containers.list(
                all=True, filters={"label": f"{OWNER}={report.runId}"}
            )
        )
        == 2
    )
    monkeypatch.setattr(Container, "logs", original_logs)
    subprocess.run(
        [sys.executable, "-m", "faultglass.recover", "--run-id", report.runId],
        check=True,
    )
    assert not client.containers.list(
        all=True, filters={"label": f"{OWNER}={report.runId}"}
    )
