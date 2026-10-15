import hashlib
import os
from contextlib import suppress

from .artifacts import atomic_write
from .context_artifacts import owner_directory, read_file, read_reference
from .context_errors import EvidenceIntegrity, IdentityConflict
from .context_models import EvidenceReference, evidence_id
from .jsonio import digest, encode, loads
from .planning_artifacts import PlanningStore
from .reduction_models import ReductionCheckpoint


class ReductionStore:
    _name = PlanningStore._name

    def __init__(self, root, job_id):
        self.root, self.owner = root, evidence_id(job_id) + "/reduction"
        with owner_directory(root, job_id) as fd:
            with suppress(FileExistsError):
                os.mkdir("reduction", 0o700, dir_fd=fd)
            os.fsync(fd)

    def put(self, name, data):
        self._name(name)
        if len(data) > 1048576:
            raise EvidenceIntegrity()
        with owner_directory(self.root, self.owner) as fd:
            try:
                old = read_file(fd, name, 1048576)
            except FileNotFoundError:
                old = None
            if old is not None and old != data:
                raise IdentityConflict()
            if old is None:
                atomic_write(fd, name, data)
        ref = EvidenceReference(
            id=digest({"owner": self.owner, "path": name}),
            kind="reduction",
            owner=self.owner,
            path=name,
            mediaType="application/json",
            sha256=hashlib.sha256(data).hexdigest(),
            bytes=len(data),
        )
        read_reference(self.root, ref)
        return ref

    def document(self, prefix, value):
        data = encode(value.model_dump())
        return self.put(f"{prefix}-{hashlib.sha256(data).hexdigest()}.json", data)

    def checkpoint(self, record):
        ref = record.reductionRef
        if ref is None or ref.owner != self.owner:
            raise EvidenceIntegrity()
        checkpoint = ReductionCheckpoint.model_validate(
            loads(read_reference(self.root, ref))
        )
        if checkpoint.summary != record.snapshot.reduction:
            raise EvidenceIntegrity()
        for reference in [
            checkpoint.summary.currentCaseRef,
            checkpoint.summary.source.sourceCaseRef,
            *checkpoint.attempts,
        ]:
            if reference.owner != self.owner:
                raise EvidenceIntegrity()
            read_reference(self.root, reference)
        return checkpoint
