import os
import stat
import time
from datetime import UTC, datetime

from .context_artifacts import owner_directory, read_reference
from .context_errors import EvidenceIntegrity
from .context_models import evidence_id


def owned_bytes(store, record):
    ids = {record.snapshot.id}
    for receipt in store.history(record):
        if receipt.reservation:
            ids.add(receipt.reservation.childId)
    total = 0
    for identity in ids:
        evidence_id(identity)
        try:
            with owner_directory(store.root, identity) as fd:
                for _path, _dirs, files, directory_fd in os.fwalk(
                    ".", dir_fd=fd, follow_symlinks=False
                ):
                    for name in files:
                        info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                        if not stat.S_ISREG(info.st_mode):
                            raise EvidenceIntegrity()
                        total += info.st_size
                        if total > record.snapshot.budget.maxArtifactBytes:
                            raise EvidenceIntegrity()
        except FileNotFoundError:
            if identity == record.snapshot.id:
                raise EvidenceIntegrity() from None
    return total


def execution_deadline(record, monotonic_limit):
    snapshot = record.snapshot
    wall = datetime.now(UTC)
    remaining = (datetime.fromisoformat(snapshot.deadlineAt) - wall).total_seconds()
    if wall < datetime.fromisoformat(snapshot.updatedAt):
        remaining = 0
    return min(monotonic_limit, time.monotonic() + max(0, remaining))


def verify_committed(store, record):
    for receipt in store.history(record):
        read_reference(store.root, receipt.inputRef)
        for ref in receipt.outputs:
            read_reference(store.root, ref)
