import hashlib
import os
from contextlib import suppress
from pathlib import Path

from .artifacts import atomic_write
from .context_artifacts import owner_directory, read_file, read_reference
from .context_errors import EvidenceIntegrity, IdentityConflict
from .context_models import EvidenceReference, evidence_id
from .jsonio import digest, encode, loads
from .planner_models import ExecutionJournal

MAX_DOCUMENT = 1048576
MAX_SET = 4194304


class PlanningStore:
    def __init__(self, root, seed_id):
        self.root, self.seed_id = root, evidence_id(seed_id)
        self.owner = seed_id + "/planning"
        with owner_directory(root, seed_id) as fd:
            with suppress(FileExistsError):
                os.mkdir("planning", 0o700, dir_fd=fd)
            os.fsync(fd)

    def _name(self, filename):
        if (
            Path(filename).name != filename
            or not filename.endswith(".json")
            or filename in (".json", "..json")
        ):
            raise EvidenceIntegrity()

    def get(self, filename):
        self._name(filename)
        with owner_directory(self.root, self.owner) as fd:
            return read_file(fd, filename, MAX_DOCUMENT)

    def optional(self, filename):
        try:
            return self.get(filename)
        except FileNotFoundError:
            return None

    def put(self, filename, data, *, mutable=False):
        self._name(filename)
        if len(data) > MAX_DOCUMENT:
            raise EvidenceIntegrity()
        with owner_directory(self.root, self.owner) as fd:
            size = len(data)
            for name in os.listdir(fd):
                self._name(name)
                if name != filename:
                    size += len(read_file(fd, name, MAX_DOCUMENT))
            if size > MAX_SET:
                raise EvidenceIntegrity()
            try:
                old = read_file(fd, filename, MAX_DOCUMENT)
            except FileNotFoundError:
                old = None
            if old is not None and old != data and not mutable:
                raise IdentityConflict()
            if old != data:
                atomic_write(fd, filename, data)
        ref = EvidenceReference(
            id=digest({"owner": self.owner, "path": filename}),
            kind=filename.removesuffix(".json"),
            path=filename,
            owner=self.owner,
            mediaType="application/json",
            sha256=hashlib.sha256(data).hexdigest(),
            bytes=len(data),
        )
        read_reference(self.root, ref)
        return ref

    def seal(self, phase, documents):
        refs = [self.put(name, data) for name, data in sorted(documents.items())]
        self.put(
            phase + "-manifest.json",
            encode({"phase": phase, "artifacts": [ref.model_dump() for ref in refs]}),
        )
        return refs

    def verify(self, phase):
        manifest = loads(self.get(phase + "-manifest.json"))
        if set(manifest) != {"phase", "artifacts"} or manifest["phase"] != phase:
            raise EvidenceIntegrity()
        refs = [
            EvidenceReference.model_validate(item) for item in manifest["artifacts"]
        ]
        if not 1 <= len(refs) <= 6 or len({ref.path for ref in refs}) != len(refs):
            raise EvidenceIntegrity()
        for ref in refs:
            if ref.owner != self.owner:
                raise EvidenceIntegrity()
            read_reference(self.root, ref)
        return refs

    def journal(self):
        data = self.optional("execution-journal.json")
        return ExecutionJournal.model_validate(loads(data)) if data else None

    def advance(self, journal):
        old = self.journal()
        if old:
            allowed = {
                "reserved": {"started", "incomplete", "evidence_complete"},
                "started": {"incomplete", "evidence_complete"},
                "incomplete": {"evidence_complete"},
                "evidence_complete": set(),
            }
            if (
                old.selection_id != journal.selection_id
                or old.child_evidence_id != journal.child_evidence_id
                or old.reserved_at != journal.reserved_at
                or (old != journal and journal.state not in allowed[old.state])
            ):
                raise IdentityConflict()
        self.put("execution-journal.json", encode(journal.model_dump()), mutable=True)
