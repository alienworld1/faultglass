import http.client
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from faultglass.context_config import ContextConfig
from faultglass.graph_repository import GraphRepository
from faultglass.investigation_models import Admission
from faultglass.investigation_store import InvestigationStore
from faultglass.worker import Worker

ROOT = Path(__file__).resolve().parents[4]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(port, method, path, body=None, headers=None, *, source="127.0.0.1"):
    connection = http.client.HTTPConnection(
        "127.0.0.1", port, timeout=20, source_address=(source, 0)
    )
    try:
        connection.request(
            method, path, body=body, headers=headers or {}, encode_chunked=True
        )
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


@pytest.fixture(scope="module")
def ingress(tmp_path_factory):
    binary = os.environ.get("FAULTGLASS_NGINX_BINARY") or shutil.which("nginx")
    assert binary, "Install Nginx or set FAULTGLASS_NGINX_BINARY to run ingress checks."
    static = ROOT / "apps/web/dist"
    assert (static / "index.html").is_file(), (
        "Build the frontend before ingress checks."
    )
    folder = tmp_path_factory.mktemp("ingress")
    upstream, port = free_port(), free_port()
    config = (ROOT / "deploy/nginx.conf").read_text()
    config = config.replace("user www-data;", "")
    config = config.replace("/run/faultglass-nginx.pid", str(folder / "nginx.pid"))
    config = config.replace("/opt/faultglass/apps/web/dist", str(static))
    config = config.replace(
        "include /etc/nginx/mime.types;", "types { text/html html; }"
    )
    config = config.replace(
        "http {",
        f"http {{\n client_body_temp_path {folder}/body;\n proxy_temp_path {folder}/proxy;",
    )
    config = config.replace(
        "http {",
        f"http {{\n fastcgi_temp_path {folder}/fastcgi;\n uwsgi_temp_path {folder}/uwsgi;\n scgi_temp_path {folder}/scgi;",
    )
    config = config.replace("127.0.0.1:8080", f"127.0.0.1:{port}")
    config = config.replace("127.0.0.1:8000", f"127.0.0.1:{upstream}")
    path = folder / "nginx.conf"
    path.write_text(config)
    environment = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    graph = "faultglass__test_" + uuid4().hex
    environment.update(
        FAULTGLASS_CONTEXT_GRAPH=graph,
        FAULTGLASS_ARTIFACT_ROOT=str(folder / "evidence"),
    )
    repository = GraphRepository(
        ContextConfig(graph=graph, artifact_root=folder / "evidence")
    )
    repository.ensure_schema()
    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "faultglass.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(upstream),
            "--no-proxy-headers",
            "--no-access-log",
        ],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proxy = None
    try:
        for _ in range(100):
            try:
                request(upstream, "GET", "/api/unknown")
                break
            except OSError:
                time.sleep(0.05)
        else:
            pytest.fail("The private API did not start")
        subprocess.run([binary, "-t", "-p", str(folder), "-c", str(path)], check=True)
        proxy = subprocess.Popen(
            [binary, "-p", str(folder), "-c", str(path), "-g", "daemon off;"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            try:
                request(port, "GET", "/")
                break
            except OSError:
                time.sleep(0.05)
        else:
            pytest.fail("The ingress did not start")
        yield port, repository
    finally:
        for process in (proxy, api):
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        repository.graph.delete()
        repository.close()


def test_static_deep_links_and_api_never_share_fallback(ingress):
    ingress, _ = ingress
    root = request(ingress, "GET", "/")
    deep = request(
        ingress, "GET", "/investigations/00000000-0000-0000-0000-000000000000"
    )
    assert root[0] == deep[0] == 200 and root[2] == deep[2]
    assert request(ingress, "GET", "/api/unknown")[0] == 404
    assert b"<!doctype html>" not in request(ingress, "GET", "/api/unknown")[2].lower()


def test_exact_and_chunked_command_limits(ingress):
    ingress, _ = ingress
    assert (
        request(
            ingress, "POST", "/api/cases/validate", b"x" * 327680, source="127.0.0.2"
        )[0]
        == 422
    )
    for path in (
        "/api/cases/validate",
        "/api/investigations",
        "/api/investigations/00000000-0000-0000-0000-000000000000/cancel",
    ):
        assert (
            request(
                ingress, "POST", path, iter([b"x" * 327680, b"x"]), source="127.0.0.2"
            )[0]
            == 413
        )


def test_forwarded_headers_cannot_bypass_command_pressure(ingress):
    ingress, _ = ingress
    responses = [
        request(
            ingress,
            "POST",
            "/api/cases/validate",
            b"{}",
            {"X-Forwarded-For": f"192.0.2.{i}", "Forwarded": f"for=192.0.2.{i}"},
            source="127.0.0.3",
        )
        for i in range(9)
    ]
    limited = [r for r in responses if r[0] == 429]
    assert limited and all(r[1].get("Retry-After") == "10" for r in limited)
    assert request(ingress, "GET", "/api/unknown", source="127.0.0.3")[0] == 404


def test_foreign_origin_and_slow_body(ingress):
    ingress, _ = ingress
    assert (
        request(
            ingress,
            "POST",
            "/api/cases/validate",
            b"{}",
            {"Origin": "https://foreign.invalid"},
            source="127.0.0.4",
        )[0]
        == 403
    )
    with socket.create_connection(("127.0.0.1", ingress), timeout=20) as sock:
        sock.sendall(
            b"POST /api/cases/validate HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\nConnection: close\r\n\r\nx"
        )
        started = time.monotonic()
        # Keep the connection active so only the API's total body deadline can stop it.
        for _ in range(17):
            time.sleep(1)
            try:
                sock.sendall(b"x")
            except OSError:
                break
        response = sock.recv(8192)
        assert b" 408 " in response
        assert time.monotonic() - started < 20


def test_heartbeats_and_terminal_replay_stream_through_ingress(ingress):
    port, repository = ingress
    store = InvestigationStore(repository)
    case = (
        ROOT / "apps/investigator/tests/fixtures/matching.faultglass.json"
    ).read_text()
    record, _ = store.admit(
        Admission(caseFile=case, pairId="call-yield-c-rust"), str(uuid4())
    )
    identity = record.snapshot.id
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        connection.request("GET", f"/api/investigations/{identity}/events")
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Content-Type").startswith("text/event-stream")
        started = time.monotonic()
        lines = []
        while True:
            line = response.readline()
            assert line, "The live stream ended before a heartbeat"
            lines.append(line)
            if line.startswith(b": keep-alive"):
                break
        assert 14 <= time.monotonic() - started < 20
        assert any(b"event: investigation.created" in line for line in lines)
        requested, _ = store.cancel(identity)
        assert requested.snapshot.cancelRequestedAt
        cancelled = Worker(repository).step(identity)
        assert cancelled.snapshot.status == "CANCELLED"
        assert b"investigation.cancelled" in response.read()
    finally:
        connection.close()
    status, _, replay = request(port, "GET", f"/api/investigations/{identity}/events")
    assert status == 200 and b"investigation.cancelled" in replay
    assert b": keep-alive" not in replay
