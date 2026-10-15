import hashlib
import os
import stat
from contextlib import contextmanager, suppress
from pathlib import Path

from .artifacts import REQUIRED, atomic_write, open_private_root, verify
from .comparison import COMPARISON_VERSION, assess_oracle, compare
from .context_errors import ContextError, EvidenceIntegrity, IdentityConflict
from .context_models import EvidenceReference, evidence_id, validate_timestamp
from .inputs import executable_envelope
from .jsonio import digest, encode, loads
from .matrix import PLATFORM, engines_for
from .models import ArtifactRef, PairedObservation, RunLimits, RunReport, read_case
from .normalize import VERSION as NORMALIZATION_VERSION


@contextmanager
def owner_directory(root, owner):
    _, fd = open_private_root(root)
    try:
        for part in owner.split("/"):
            next_fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            os.close(fd)
            fd = next_fd
        if os.fstat(fd).st_uid != os.getuid() or os.fstat(fd).st_mode & 0o077:
            raise EvidenceIntegrity()
        yield fd
    finally:
        os.close(fd)


def read_file(fd, filename, maximum):
    descriptor = os.open(
        filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd
    )
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
        ):
            raise EvidenceIntegrity()
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise EvidenceIntegrity()
    return data


def read_reference(root, reference):
    try:
        ref = (
            EvidenceReference.model_validate(reference)
            if isinstance(reference, dict)
            else reference
        )
        with owner_directory(root, ref.owner) as fd:
            data = read_file(fd, ref.path, ref.bytes)
        if len(data) != ref.bytes or hashlib.sha256(data).hexdigest() != ref.sha256:
            raise EvidenceIntegrity()
        return data
    except (OSError, ValueError) as error:
        raise EvidenceIntegrity() from error


def load_evidence(root, run_id):
    evidence_id(run_id)
    try:
        with owner_directory(root, run_id) as fd:
            manifest_bytes = read_file(fd, "manifest.json", 32768)
            manifest = loads(manifest_bytes)
            refs = [
                ArtifactRef.model_validate(value) for value in manifest["artifacts"]
            ]
            if (
                manifest["status"] != "complete"
                or len(refs) != 6
                or {r.kind for r in refs} != REQUIRED
                or len({r.path for r in refs}) != 6
            ):
                raise ContextError(
                    "This comparison has no complete evidence to save. Finish a comparison first."
                )
            verify(Path(root) / run_id)
            values = {}
            for ref in refs:
                if Path(ref.path).name != ref.path:
                    raise EvidenceIntegrity()
                data = read_file(fd, ref.path, min(ref.bytes, 8388608))
                if (
                    len(data) != ref.bytes
                    or hashlib.sha256(data).hexdigest() != ref.sha256
                ):
                    raise EvidenceIntegrity()
                values[ref.kind] = data
        report = RunReport.model_validate(loads(values["report"]))
        if report.outcome == "failed" or report.runId != run_id:
            raise ContextError(
                "This comparison has no complete evidence to save. Finish a comparison first."
            )
        case = read_case(values["original-case"])
        engines = engines_for(report.pairId)
        config = loads(values["run-configuration"])
        normalized = loads(values["normalized-pair"])
        if (
            normalized["comparisonVersion"] != COMPARISON_VERSION
            or normalized["normalizationVersion"] != NORMALIZATION_VERSION
        ):
            raise ContextError("This saved evidence needs a compatible version.")
        pair = PairedObservation.model_validate(normalized["observations"])
        limits = RunLimits.model_validate(config["envelope"]["limits"])
        envelope = executable_envelope(case, limits)
        input_digest = digest(envelope)
        divergence = compare(pair, engines, case.observation)
        valid = (
            report.caseContentHash
            == hashlib.sha256(values["original-case"]).hexdigest()
            and config["engines"] == [engine.model_dump() for engine in engines]
            and config["platform"] == PLATFORM
            and config["envelope"] == envelope
            and config["executableInputDigests"]
            == {role: input_digest for role in ("baseline", "target")}
            and len(config["imageIds"]) == 2
            and all(
                isinstance(v, str) and v.startswith("sha256:") and len(v) == 71
                for v in config["imageIds"]
            )
            and report.observations == pair
            and report.divergence == divergence
            and report.oracleAssessment == assess_oracle(case, pair)
            and report.artifacts == [ref for ref in refs if ref.kind != "report"]
        )
        validate_timestamp(report.startedAt)
        validate_timestamp(report.finishedAt)
        if report.finishedAt < report.startedAt:
            valid = False
        for role, engine in zip(("baseline", "target"), engines, strict=True):
            raw = loads(values["raw-" + role])
            valid = (
                valid
                and getattr(pair, role).engineVersionId == engine.id
                and raw["executableInputDigest"] == input_digest
                and raw["cleanup"] == "removed"
                and raw["engine"] == engine.model_dump()
                and raw["imageId"] == config["imageIds"][0 if role == "baseline" else 1]
                and raw["role"] == role
                and raw["ownershipLabel"] == run_id
            )
        if not valid:
            raise ContextError(
                "Saved comparison details do not agree. Inspect the original evidence."
            )
        return case, report, refs, engines, hashlib.sha256(manifest_bytes).hexdigest()
    except ContextError:
        raise
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        raise EvidenceIntegrity() from error


def write_sidecar(root, run_id, documents):
    evidence_id(run_id)
    if (
        any(len(data) > 1048576 for data in documents.values())
        or sum(map(len, documents.values())) > 4194304
    ):
        raise ContextError("Case context exceeds its storage limit.")
    references = []
    try:
        with owner_directory(root, run_id) as run_fd:
            with suppress(FileExistsError):
                os.mkdir("context", 0o700, dir_fd=run_fd)
            os.fsync(run_fd)
        with owner_directory(root, run_id + "/context") as fd:
            try:
                read_file(fd, "manifest.json", 32768)
            except FileNotFoundError:
                pass
            else:
                verify_sidecar(root, run_id)
            for filename, data in documents.items():
                if Path(filename).name != filename:
                    raise EvidenceIntegrity()
                try:
                    if read_file(fd, filename, 1048576) != data:
                        raise IdentityConflict()
                except FileNotFoundError:
                    atomic_write(fd, filename, data)
                references.append(
                    EvidenceReference(
                        id=digest({"owner": run_id, "path": filename}),
                        kind=filename.removesuffix(".json"),
                        path=filename,
                        owner=run_id + "/context",
                        mediaType="application/json",
                        sha256=hashlib.sha256(data).hexdigest(),
                        bytes=len(data),
                    )
                )
            manifest = encode(
                {
                    "status": "complete",
                    "version": "context-v1",
                    "artifacts": [r.model_dump() for r in references],
                }
            )
            try:
                if read_file(fd, "manifest.json", 32768) != manifest:
                    raise IdentityConflict()
            except FileNotFoundError:
                atomic_write(fd, "manifest.json", manifest)
        for reference in references:
            read_reference(root, reference)
        return references
    except ContextError:
        raise
    except (OSError, ValueError) as error:
        raise EvidenceIntegrity() from error


def verify_sidecar(root, run_id):
    try:
        with owner_directory(root, run_id + "/context") as fd:
            manifest = loads(read_file(fd, "manifest.json", 32768))
        if (
            manifest["status"] != "complete"
            or manifest["version"] != "context-v1"
            or len(manifest["artifacts"]) != 3
        ):
            raise EvidenceIntegrity()
        refs = [
            EvidenceReference.model_validate(value) for value in manifest["artifacts"]
        ]
        if (
            {r.path for r in refs}
            != {"case.faultglass.json", "identity.json", "fingerprint.json"}
            or any(r.owner != run_id + "/context" for r in refs)
            or sum(r.bytes for r in refs) > 4194304
        ):
            raise EvidenceIntegrity()
        for ref in refs:
            read_reference(root, ref)
        return refs
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise EvidenceIntegrity() from error
