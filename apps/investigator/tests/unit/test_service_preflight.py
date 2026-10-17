from contextlib import nullcontext
from types import SimpleNamespace

from faultglass import gemini, preflight, worker


def test_bad_provider_configuration_never_reaches_engines(
    monkeypatch, tmp_path, capsys
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid provider configuration reached engines")

    monkeypatch.setattr(
        worker,
        "GraphRepository",
        lambda: SimpleNamespace(
            config=SimpleNamespace(artifact_root=tmp_path), close=lambda: None
        ),
    )
    monkeypatch.setattr(worker, "WorkerPresence", lambda config: nullcontext())
    monkeypatch.setattr(worker, "docker_client", forbidden)
    monkeypatch.setattr(
        gemini,
        "agent_readiness",
        lambda: {"agentReady": False, "agentReason": "missing_key"},
    )
    assert worker.main() == 1
    assert "could not start" in capsys.readouterr().err


def test_preflight_redacts_dependency_failures(monkeypatch, tmp_path, capsys):
    from docker.errors import DockerException

    from faultglass.context_errors import ContextUnavailable

    monkeypatch.setenv("FAULTGLASS_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setenv("FAULTGLASS_ALLOWED_ORIGINS", "http://127.0.0.1:8080")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(
        preflight,
        "docker_client",
        lambda: (_ for _ in ()).throw(DockerException("private key and path")),
    )
    monkeypatch.setattr(
        preflight.GraphRepository,
        "_assert_ready",
        lambda self: (_ for _ in ()).throw(ContextUnavailable()),
    )
    issues = preflight.check(worker=True)
    assert any("approved images" in issue for issue in issues)
    assert any("persistent context" in issue for issue in issues)
    assert any("missing_key" in issue for issue in issues)
    assert "private key and path" not in str(issues)
    assert str(tmp_path) not in str(issues)
    assert list(tmp_path.iterdir()) == []
