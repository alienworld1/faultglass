import os
from pathlib import Path

from .artifacts import open_private_root
from .errors import ExecutionFailure

RESERVE_BYTES = 2 * 1024**3
MAX_FILESYSTEM_BYTES = 8 * 1024**3


def storage_issue(root):
    try:
        mode = os.environ.get("FAULTGLASS_STORAGE_MODE", "monitored_local")
        if mode not in {"bounded", "monitored_local"}:
            return "storage_policy_invalid"
        # Follow the existing safe directory traversal and ownership policy.
        _, fd = open_private_root(Path(root))
        try:
            stats = os.fstatvfs(fd)
            if mode == "bounded" and (
                stats.f_blocks * stats.f_frsize > MAX_FILESYSTEM_BYTES
            ):
                return "storage_quota_required"
            if stats.f_bavail * stats.f_frsize < RESERVE_BYTES:
                return "storage_reserve_low"
            if stats.f_favail == 0:
                return "storage_inodes_low"
        finally:
            os.close(fd)
    except (OSError, ValueError):
        return "storage_unavailable"
    return None


def require_storage(root):
    issue = storage_issue(root)
    if issue:
        raise ExecutionFailure(
            issue,
            "preflight",
            "Evidence storage cannot accept new work. Preserve saved evidence and check the storage policy.",
        )
