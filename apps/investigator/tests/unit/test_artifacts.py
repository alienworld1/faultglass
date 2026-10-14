from uuid import uuid4

import pytest

from faultglass.artifacts import REQUIRED, ArtifactStore, Lease, verify
from faultglass.errors import ExecutionFailure


def test_manifest_is_last_and_detects_corruption(tmp_path):
    store = ArtifactStore(tmp_path, str(uuid4()), 8388608)
    try:
        with pytest.raises(ValueError):
            store.commit()
        assert not (store.path / "manifest.json").exists()
        for kind in REQUIRED:
            store.write(kind, b"{}")
        store.commit()
        assert verify(store.path) == len(REQUIRED)
        (store.path / store.refs[0].path).write_bytes(b"changed")
        with pytest.raises(ValueError):
            verify(store.path)
    finally:
        store.close()


def test_quota_and_symlink_escape_leave_no_complete_evidence(tmp_path):
    store = ArtifactStore(tmp_path, str(uuid4()), 1)
    try:
        with pytest.raises(ExecutionFailure):
            store.write("original-case", b"{}")
        assert not (store.path / "manifest.json").exists()
    finally:
        store.close()
    escape = tmp_path / "escape"
    escape.symlink_to("/tmp", target_is_directory=True)
    with pytest.raises(ValueError):
        ArtifactStore(escape, str(uuid4()), 100)


def test_lease_is_atomic_and_released_after_failure():
    with Lease(), pytest.raises(ExecutionFailure, match="already running"), Lease():
        pass
    with Lease():
        pass


def test_manifest_failure_can_be_marked_incomplete_without_overwriting_evidence(
    tmp_path,
):
    store = ArtifactStore(tmp_path, str(uuid4()), 8388608)
    try:
        for kind in REQUIRED:
            store.write(kind, b"{}")
        store.commit()
        store.discard_completion()
        assert not (store.path / "manifest.json").exists()
        assert all((store.path / ref.path).exists() for ref in store.refs)
    finally:
        store.close()


def test_ancestor_symlinks_and_external_case_ids_cannot_control_run_paths(tmp_path):
    folder = tmp_path / "alias"
    folder.symlink_to("/tmp", target_is_directory=True)
    with pytest.raises((OSError, ValueError)):
        ArtifactStore(folder / "nested", str(uuid4()), 1000)
    with pytest.raises(ValueError):
        ArtifactStore(tmp_path, "../../escape", 1000)
