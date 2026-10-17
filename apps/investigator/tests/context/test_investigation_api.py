import time
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from faultglass import api, investigation_api
from faultglass.context_config import ContextConfig
from faultglass.context_errors import ContextUnavailable
from faultglass.graph_repository import GraphRepository
from faultglass.investigation_store import InvestigationStore
from faultglass.worker import Worker

pytestmark = pytest.mark.context


@pytest.fixture
def connected_api(tmp_path, monkeypatch):
    config = ContextConfig(
        graph="faultglass__test_" + uuid4().hex, artifact_root=tmp_path
    )
    repo = GraphRepository(config)
    repo.ensure_schema()
    monkeypatch.setattr(
        investigation_api, "GraphRepository", lambda: GraphRepository(config)
    )
    monkeypatch.setattr(
        investigation_api,
        "service_readiness",
        lambda repository: {"workerReady": True, "contextReady": True},
    )
    monkeypatch.setattr(api, "readiness", lambda: {})
    investigation_api.starts.clear()
    try:
        with TestClient(api.app) as client:
            yield client, repo
    finally:
        repo.graph.delete()
        repo.close()


def body(name="matching"):
    return {
        "caseFile": (
            Path(__file__).parents[1] / "fixtures" / (name + ".faultglass.json")
        ).read_text(),
        "pairId": "call-yield-c-rust",
    }


def test_recent_investigations_are_bounded_and_do_not_expose_case_contents(
    connected_api,
):
    from faultglass.investigation_models import Admission, Status

    client, repo = connected_api
    assert client.get("/api/investigations").json() == {"items": []}
    store = InvestigationStore(repo)
    identities = []
    for _ in range(11):
        record, _ = store.admit(Admission(**body()), str(uuid4()))
        identities.append(record.snapshot.id)
        store.commit(
            record.snapshot.id,
            "investigation.cancelled",
            "Investigation cancelled.",
            status=Status.CANCELLED,
            update={
                "terminalReason": {
                    "code": "cancelled",
                    "message": "Investigation cancelled.",
                }
            },
        )
    response = client.get("/api/investigations")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 10
    assert [item["id"] for item in items] == list(reversed(identities[1:]))
    assert all(
        item["status"] == "CANCELLED" and item["plannedExperiments"] == 0
        for item in items
    )
    assert all(
        set(item)
        == {
            "id",
            "title",
            "status",
            "baseline",
            "target",
            "updatedAt",
            "plannedExperiments",
            "verifiedDifferences",
            "sourceBehavior",
            "familyState",
        }
        for item in items
    )
    assert (
        "caseFile" not in response.text and "runtime_artifact_ref" not in response.text
    )


def test_api_admission_returns_promptly_and_replay_survives_restart(
    connected_api, monkeypatch
):
    client, repo = connected_api
    import faultglass.worker as worker_module

    monkeypatch.setattr(
        worker_module,
        "run_case",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Admission executed engines")
        ),
    )
    key = str(uuid4())
    at = time.monotonic()
    response = client.post(
        "/api/investigations", json=body(), headers={"Idempotency-Key": key}
    )
    assert response.status_code == 202, response.text
    assert time.monotonic() - at < 2
    job = response.json()["investigation"]
    assert job["status"] == "QUEUED"
    assert client.post(
        "/api/investigations", json=body(), headers={"Idempotency-Key": key}
    ).json()["reused"]
    assert (
        client.post(
            "/api/investigations",
            json=body("call-yield"),
            headers={"Idempotency-Key": key},
        ).status_code
        == 409
    )
    with TestClient(api.app) as restarted:
        assert (
            restarted.get("/api/investigations/admission/" + key).json()["id"]
            == job["id"]
        )
        assert restarted.get("/api/investigations/" + job["id"]).json() == job
    assert InvestigationStore(repo).pending() == [job["id"]]


def test_storage_refusal_preserves_existing_admission_and_reads(
    connected_api, monkeypatch
):
    from faultglass import storage_policy

    client, repo = connected_api
    key = str(uuid4())
    first = client.post(
        "/api/investigations", json=body(), headers={"Idempotency-Key": key}
    )
    assert first.status_code == 202
    identity = first.json()["investigation"]["id"]
    monkeypatch.setattr(
        storage_policy, "storage_issue", lambda root: "storage_reserve_low"
    )
    investigation_api.starts.clear()
    rejected = client.post(
        "/api/investigations", json=body(), headers={"Idempotency-Key": str(uuid4())}
    )
    assert rejected.status_code == 503
    assert rejected.json()["error"]["code"] == "storage_reserve_low"
    assert InvestigationStore(repo).pending() == [identity]
    assert client.get("/api/investigations/" + identity).status_code == 200
    assert client.post(
        "/api/investigations", json=body(), headers={"Idempotency-Key": key}
    ).json()["reused"]


def test_invalid_requests_never_admit_and_errors_are_bounded(connected_api):
    client, repo = connected_api
    command = body()
    command["caseFile"] = '{"private_query":"sensitive"}'
    response = client.post(
        "/api/investigations", json=command, headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 422
    assert "sensitive" not in response.text
    assert client.post("/api/investigations", content=b"x" * 327681).status_code == 413
    assert (
        client.post(
            "/api/investigations", json={**body(), "pairId": "unapproved"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/investigations",
            json=body(),
            headers={"Origin": "https://untrusted.example"},
        ).status_code
        == 403
    )
    assert InvestigationStore(repo).pending() == []
    assert client.get("/api/investigations/not-an-id").status_code == 422
    assert client.get("/api/investigations/" + str(uuid4())).status_code == 404


def test_terminal_replay_cursor_precedence_evidence_and_cancel(connected_api):
    client, repo = connected_api
    response = client.post(
        "/api/investigations", json=body(), headers={"Idempotency-Key": str(uuid4())}
    )
    job_id = response.json()["investigation"]["id"]
    worker = Worker(repo)
    for _ in range(4):
        worker.step(job_id)
    saved = client.get("/api/investigations/" + job_id).json()
    trace = client.get(f"/api/investigations/{job_id}/events?after=0")
    assert trace.status_code == 200
    assert trace.headers["content-type"].startswith("text/event-stream")
    ids = [line[4:] for line in trace.text.splitlines() if line.startswith("id: ")]
    assert ids == [
        f"{job_id}:{index}" for index in range(1, saved["lastEventSequence"] + 1)
    ]
    replay = client.get(
        f"/api/investigations/{job_id}/events?after=0",
        headers={"Last-Event-ID": f"{job_id}:2"},
    )
    assert f"id: {job_id}:1\n" not in replay.text and f"id: {job_id}:3\n" in replay.text
    assert (
        client.get(f"/api/investigations/{job_id}/events?after=512").status_code == 409
    )
    assert (
        client.get(
            f"/api/investigations/{job_id}/events",
            headers={"Last-Event-ID": f"{uuid4()}:1"},
        ).status_code
        == 422
    )
    assert (
        client.get(f"/api/investigations/{job_id}/evidence").json()["items"][0]["kind"]
        == "seed"
    )
    assert (
        client.post(f"/api/investigations/{job_id}/cancel").json()["accepted"] is False
    )


def test_context_outage_is_not_absence(connected_api, monkeypatch):
    client, _repo = connected_api

    def unavailable(*args, **kwargs):
        raise ContextUnavailable()

    monkeypatch.setattr(GraphRepository, "_query", unavailable)
    response = client.get("/api/investigations/admission/" + str(uuid4()))
    assert response.status_code == 503
    assert response.json()["error"]["retryable"]


def test_reduction_reads_validate_cursors_and_never_execute(connected_api, monkeypatch):
    client, repo = connected_api
    response = client.post(
        "/api/investigations", json=body(), headers={"Idempotency-Key": str(uuid4())}
    )
    job = response.json()["investigation"]["id"]
    monkeypatch.setattr(
        "faultglass.worker.run_case",
        lambda *_a, **_k: pytest.fail("A read must never execute work"),
    )
    path = f"/api/investigations/{job}/reduction"
    page = client.get(path)
    assert page.status_code == 200
    assert (
        page.json()["summary"] is None
        and page.json()["case"] is None
        and page.json()["attempts"] == []
    )
    for query in (
        "cursor=-1",
        "cursor=1.0",
        "cursor=33",
        "setupCursor=x",
        "setupCursor=33",
        "cursor=99999999999999999999999999",
        "caseId=foreign",
    ):
        assert client.get(path + "?" + query).status_code == 422
    assert client.get(path + "?caseId=" + "a" * 64).status_code == 404
    assert client.get(f"/api/investigations/{uuid4()}/reduction").status_code == 404
    assert InvestigationStore(repo).load(job).snapshot.revision == 1
