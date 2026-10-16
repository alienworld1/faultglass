import fcntl
import hashlib
import os
from contextlib import suppress
from pathlib import Path
from uuid import UUID, uuid4

from .errors import ExecutionFailure
from .jsonio import encode, loads
from .models import ArtifactRef

REQUIRED = {
    "original-case",
    "run-configuration",
    "raw-baseline",
    "raw-target",
    "normalized-pair",
    "report",
}


def open_private_root(path):
    path = Path(path).absolute()
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if part in (".", ".."):
                raise ValueError("Choose a direct evidence folder without traversal.")
            try:
                next_fd = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
            except NotADirectoryError as error:
                raise ValueError(
                    "Choose an evidence folder without symbolic links."
                ) from error
            except FileNotFoundError:
                os.mkdir(part, mode=0o700, dir_fd=fd)
                next_fd = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
            os.close(fd)
            fd = next_fd
        if os.fstat(fd).st_uid != os.getuid():
            raise ValueError("Choose an evidence folder owned by your account.")
        os.fchmod(fd, 0o700)
        return path, fd
    except BaseException:
        os.close(fd)
        raise


class Lease:
    def __enter__(self):
        _, root_fd = open_private_root(Path("/tmp") / f"faultglass-{os.getuid()}")
        try:
            self.fd = os.open(
                "execution.lock",
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                0o600,
                dir_fd=root_fd,
            )
        finally:
            os.close(root_fd)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            os.close(self.fd)
            raise ExecutionFailure(
                "busy",
                "admission",
                "A comparison is already running. Try again when it finishes.",
            ) from error
        return self

    def __exit__(self, *args):
        os.close(self.fd)


class ArtifactStore:
    def __init__(self, root, run_id, budget, *, runtime_existing=False):
        if str(UUID(run_id)) != run_id:
            raise ValueError("Use a generated run identity.")
        self.root, root_fd = open_private_root(root)
        self.path = self.root / run_id
        try:
            try:
                os.mkdir(run_id, mode=0o700, dir_fd=root_fd)
            except FileExistsError:
                if not runtime_existing:
                    raise
                with os.scandir(self.path) as entries:
                    if any(
                        entry.name not in {"runtime", "agent"}
                        or not entry.is_dir(follow_symlinks=False)
                        for entry in entries
                    ):
                        raise ValueError(
                            "Reserved evidence folder already contains comparison evidence."
                        ) from None
            self.fd = os.open(
                run_id, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd
            )
        finally:
            os.close(root_fd)
        self.budget, self.used, self.refs = budget, 0, []

    def write(self, kind, data, media_type="application/json"):
        if self.used + len(data) > self.budget:
            raise ExecutionFailure(
                "artifact_limit",
                "persistence",
                "The complete evidence exceeded its storage limit.",
            )
        filename = uuid4().hex + (
            ".faultglass.json" if kind == "original-case" else ".json"
        )
        self.atomic(filename, data)
        ref = ArtifactRef(
            id=uuid4().hex,
            kind=kind,
            path=filename,
            mediaType=media_type,
            sha256=hashlib.sha256(data).hexdigest(),
            bytes=len(data),
        )
        self.used += len(data)
        self.refs.append(ref)
        return ref

    def atomic(self, filename, data):
        atomic_write(self.fd, filename, data)

    def commit(self):
        if not REQUIRED.issubset({ref.kind for ref in self.refs}):
            raise ValueError("Complete evidence requires all paired artifacts.")
        for ref in self.refs:
            fd = os.open(ref.path, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.fd)
            with os.fdopen(fd, "rb") as stream:
                data = stream.read(ref.bytes + 1)
            if len(data) != ref.bytes or hashlib.sha256(data).hexdigest() != ref.sha256:
                raise ValueError("An evidence artifact is incomplete or changed.")
        manifest = encode(
            {"status": "complete", "artifacts": [ref.model_dump() for ref in self.refs]}
        )
        if self.used + len(manifest) > self.budget:
            raise ExecutionFailure(
                "artifact_limit",
                "persistence",
                "The complete evidence exceeded its storage limit.",
            )
        self.atomic("manifest.json", manifest)

    def discard_completion(self):
        try:
            os.unlink("manifest.json", dir_fd=self.fd)
            os.fsync(self.fd)
        except FileNotFoundError:
            pass

    def close(self):
        os.close(self.fd)


def verify(path):
    path = Path(path)
    if any(parent.is_symlink() for parent in [path, *path.parents]):
        raise ValueError("Evidence must not be a symbolic link.")
    manifest = loads((path / "manifest.json").read_bytes())
    if manifest["status"] != "complete":
        raise ValueError("This evidence is incomplete.")
    refs = [ArtifactRef.model_validate(value) for value in manifest["artifacts"]]
    if not REQUIRED.issubset({ref.kind for ref in refs}):
        raise ValueError("Required paired evidence is missing.")
    for ref in refs:
        file = path / ref.path
        if Path(ref.path).name != ref.path or file.is_symlink():
            raise ValueError("Evidence references must stay inside their run folder.")
        if ref.bytes > 8388608:
            raise ValueError("Evidence exceeds its storage limit.")
        with file.open("rb") as stream:
            data = stream.read(ref.bytes + 1)
        if len(data) != ref.bytes or hashlib.sha256(data).hexdigest() != ref.sha256:
            raise ValueError("Evidence hash or size does not match.")
    return len(refs)


def atomic_write(directory_fd, filename, data):
    temporary = uuid4().hex + ".pending"
    fd = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory_fd,
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.rename(temporary, filename, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(temporary, dir_fd=directory_fd)
