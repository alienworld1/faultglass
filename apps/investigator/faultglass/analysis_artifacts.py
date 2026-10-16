import hashlib
import os
from contextlib import suppress

from .artifacts import atomic_write
from .context_artifacts import owner_directory, read_file, read_reference
from .context_errors import EvidenceIntegrity, IdentityConflict
from .context_models import EvidenceReference, evidence_id
from .jsonio import digest, encode


class AnalysisStore:
    def __init__(self, root, job_id, area):
        if area not in {"classification", "export", "agent"}:
            raise EvidenceIntegrity()
        self.root, self.owner = root, evidence_id(job_id) + "/" + area
        with owner_directory(root, job_id) as fd:
            with suppress(FileExistsError):
                os.mkdir(area, 0o700, dir_fd=fd)
            os.fsync(fd)

    def put(self, name, data, *, key=None):
        from .analysis_models import DownloadReference

        fields = dict(
            id=digest({"owner": self.owner, "path": name}),
            kind=self.owner.split("/")[-1],
            owner=self.owner,
            path=name,
            sha256=hashlib.sha256(data).hexdigest(),
            bytes=len(data),
        )
        if key:
            ref = DownloadReference(
                **fields,
                key=key,
                mediaType={
                    "case": "application/json",
                    "regression-test": "text/x-python",
                    "report": "text/markdown",
                }[key],
            )
        else:
            ref = EvidenceReference(**fields, mediaType="application/json")
        with owner_directory(self.root, self.owner) as fd:
            try:
                old = read_file(fd, name, ref.bytes)
            except FileNotFoundError:
                old = None
            if old is not None and old != data:
                raise IdentityConflict()
            if old is None:
                atomic_write(fd, name, data)
        read_reference(self.root, ref)
        return ref

    def document(self, prefix, value):
        data = encode(value.model_dump())
        return self.put(f"{prefix}-{hashlib.sha256(data).hexdigest()}.json", data)
