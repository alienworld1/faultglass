from docker.errors import DockerException
from fastapi.testclient import TestClient

from faultglass import api


def test_unavailable_docker_keeps_api_alive_and_exposes_safe_codes(monkeypatch):
    def unavailable():
        raise DockerException("private runtime detail")

    monkeypatch.setattr(api, "docker_client", unavailable)
    monkeypatch.setattr(
        api,
        "service_readiness",
        lambda repository: {"contextReady": False, "workerReady": False},
    )
    client = TestClient(api.app)
    health = client.get("/api/health")
    assert health.status_code == 200
    assert {k: v for k, v in health.json().items() if not k.startswith("agent")} == {
        "contextReady": False,
        "workerReady": False,
        "status": "ok",
        "executionReady": False,
        "issues": ["docker_unavailable"],
    }
    matrix = client.get("/api/engine-matrix").json()
    assert not matrix["pairs"][0]["available"]
    assert "private" not in str(matrix)
    assert client.post("/api/execution").status_code == 404
