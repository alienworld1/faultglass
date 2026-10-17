from types import SimpleNamespace

import pytest

from faultglass import storage_policy
from faultglass.errors import ExecutionFailure


def stats(monkeypatch, *, total=8 * 1024**3, free=3 * 1024**3, inodes=10):
    monkeypatch.setattr(
        storage_policy.os,
        "fstatvfs",
        lambda fd: SimpleNamespace(
            f_frsize=1, f_blocks=total, f_bavail=free, f_favail=inodes
        ),
    )


def test_bounded_storage_verifies_actual_filesystem(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULTGLASS_STORAGE_MODE", "bounded")
    stats(monkeypatch)
    assert storage_policy.storage_issue(tmp_path) is None
    stats(monkeypatch, total=8 * 1024**3 + 1)
    assert storage_policy.storage_issue(tmp_path) == "storage_quota_required"


def test_reserve_and_inodes_fail_before_work(tmp_path, monkeypatch):
    stats(monkeypatch, free=2 * 1024**3 - 1)
    with pytest.raises(ExecutionFailure) as failure:
        storage_policy.require_storage(tmp_path)
    assert failure.value.code == "storage_reserve_low"
    stats(monkeypatch, free=2 * 1024**3)
    assert storage_policy.storage_issue(tmp_path) is None
    stats(monkeypatch, inodes=0)
    assert storage_policy.storage_issue(tmp_path) == "storage_inodes_low"
    assert list(tmp_path.iterdir()) == []


def test_policy_and_symlinks_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("FAULTGLASS_STORAGE_MODE", "unknown")
    assert storage_policy.storage_issue(tmp_path) == "storage_policy_invalid"
    monkeypatch.setenv("FAULTGLASS_STORAGE_MODE", "monitored_local")
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    assert storage_policy.storage_issue(link) == "storage_unavailable"


def test_low_storage_refuses_execution_before_docker(tmp_path, monkeypatch):
    from pathlib import Path

    from faultglass import execution
    from faultglass.models import read_case

    def forbidden():
        pytest.fail("Storage refusal must precede Docker access")

    stats(monkeypatch, free=1)
    monkeypatch.setattr(execution, "docker_client", forbidden)
    data = (
        Path(__file__).parents[1] / "fixtures/matching.faultglass.json"
    ).read_bytes()
    report, _, code = execution.run_case(
        data, read_case(data), "call-yield-c-rust", tmp_path
    )
    assert code == 1 and report.failure.code == "storage_reserve_low"
    assert list(tmp_path.iterdir()) == []
