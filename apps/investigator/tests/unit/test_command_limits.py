import asyncio

import pytest
from fastapi.testclient import TestClient

from faultglass import investigation_api
from faultglass.api import app
from faultglass.investigation_store import RuntimeErrorResponse


class Upload:
    def __init__(self, chunks, delay=0):
        self.chunks, self.delay = chunks, delay

    async def stream(self):
        for chunk in self.chunks:
            await asyncio.sleep(self.delay)
            yield chunk


def test_streamed_envelope_has_exact_byte_boundary():
    assert (
        len(asyncio.run(investigation_api.command_body(Upload([b"x" * 327680]))))
        == 327680
    )
    with pytest.raises(RuntimeErrorResponse) as failure:
        asyncio.run(investigation_api.command_body(Upload([b"x" * 327680, b"x"])))
    assert failure.value.status == 413


def test_trickled_body_has_total_deadline(monkeypatch):
    monkeypatch.setattr(investigation_api, "COMMAND_SECONDS", 0.025)
    with pytest.raises(RuntimeErrorResponse) as failure:
        asyncio.run(investigation_api.command_body(Upload([b"x"] * 20, 0.01)))
    assert failure.value.status == 408


@pytest.mark.parametrize(
    "path",
    [
        "/api/cases/validate",
        "/api/investigations",
        "/api/investigations/" + "a" * 36 + "/cancel",
    ],
)
def test_oversized_commands_do_not_open_context(path, monkeypatch):
    def forbidden():
        pytest.fail("Rejected commands must not open investigation memory")

    monkeypatch.setattr(investigation_api, "GraphRepository", forbidden)
    # Cancellation validates its identity before reading a bounded body.
    path = path.replace("a" * 36, "00000000-0000-0000-0000-000000000000")
    response = TestClient(app).post(path, content=b"x" * 327681)
    assert response.status_code == 413
