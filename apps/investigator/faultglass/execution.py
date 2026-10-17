import argparse
import hashlib
import os
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from docker.errors import DockerException
from pydantic import ValidationError

from .artifacts import ArtifactStore, Lease
from .comparison import COMPARISON_VERSION, assess_oracle, compare
from .errors import ExecutionFailure
from .inputs import executable_envelope
from .jsonio import digest, encode
from .matrix import PLATFORM, engines_for
from .models import Failure, RunLimits, RunReport, read_case
from .normalize import VERSION as NORMALIZATION_VERSION
from .runner import OWNER, DockerRunner, docker_client, verify_images
from .storage_policy import require_storage
from .validation_copy import case_error


def timestamp():
    return datetime.now(UTC).isoformat()


def validate_parameters(case):
    from falkordb.graph import Graph

    class ParameterClient:
        execute_command = None

    graph = Graph(ParameterClient(), "evidence")
    for parameters in [
        case.parameters,
        *(check.parameters for check in case.observation.postconditions),
    ]:
        graph._build_params_header(parameters)


def run_case(
    data,
    case,
    pair_id,
    root,
    limits=None,
    *,
    reserved_id=None,
    admission_deadline=None,
    runtime_existing=False,
):
    limits = limits or RunLimits()
    engines = engines_for(pair_id)
    validate_parameters(case)
    from .context_models import evidence_id

    run_id, started = (
        evidence_id(reserved_id) if reserved_id is not None else str(uuid4()),
        timestamp(),
    )
    store, runner, client = None, None, None
    content_hash = hashlib.sha256(data).hexdigest()
    fields = {
        "runId": run_id,
        "pairId": pair_id,
        "caseContentHash": content_hash,
        "startedAt": started,
    }
    try:
        with Lease():
            try:
                require_storage(root)
                if (
                    admission_deadline is not None
                    and admission_deadline - time.monotonic()
                    < limits.pairSeconds + 2 * limits.cleanupSeconds
                ):
                    raise ExecutionFailure(
                        "budget_exhausted",
                        "admission",
                        "The experiment budget was exhausted.",
                    )
                client = docker_client()
                images = verify_images(client, engines)
                if client.containers.list(all=True, filters={"label": OWNER}):
                    raise ExecutionFailure(
                        "cleanup_required",
                        "preflight",
                        "A previous comparison still owns engines. Run the targeted recovery command before trying again.",
                    )
                store = ArtifactStore(
                    root,
                    run_id,
                    limits.artifactBytes,
                    runtime_existing=runtime_existing,
                )
                store.write("original-case", data)
                envelope = executable_envelope(case, limits)
                input_digest = digest(envelope)
                store.write(
                    "run-configuration",
                    encode(
                        {
                            "engines": [engine.model_dump() for engine in engines],
                            "platform": PLATFORM,
                            "imageIds": [image.id for image in images],
                            "envelope": envelope,
                            "executableInputDigests": {
                                "baseline": input_digest,
                                "target": input_digest,
                            },
                        }
                    ),
                )
                if (
                    admission_deadline is not None
                    and admission_deadline - time.monotonic()
                    < limits.pairSeconds + 2 * limits.cleanupSeconds
                ):
                    raise ExecutionFailure(
                        "budget_exhausted",
                        "admission",
                        "The experiment budget was exhausted.",
                    )
                runner = DockerRunner(client, run_id)
                print("Case: " + case.title, file=sys.stderr)
                print("Running baseline and target…", file=sys.stderr)
                try:
                    pair = runner.execute_pair(case, *engines, limits)
                except ValueError as error:
                    raise ExecutionFailure(
                        "normalization",
                        "normalization",
                        "The engine response could not be compared completely. Inspect the partial evidence for the unsupported value.",
                    ) from error
                if any(
                    runner.evidence[role]["executableInputDigest"] != input_digest
                    for role in ("baseline", "target")
                ):
                    raise ExecutionFailure(
                        "input_mismatch",
                        "comparison",
                        "The engines did not receive identical executable inputs.",
                    )
                for role in ("baseline", "target"):
                    store.write("raw-" + role, encode(runner.evidence[role]))
                    print(
                        f"{role.capitalize()}: {getattr(pair, role).engineVersionId} "
                        f"({engines[0 if role == 'baseline' else 1].imageDigest}) "
                        f"— {getattr(pair, role).status}",
                        file=sys.stderr,
                    )
                store.write(
                    "normalized-pair",
                    encode(
                        {
                            "normalizationVersion": NORMALIZATION_VERSION,
                            "comparisonVersion": COMPARISON_VERSION,
                            "observations": pair.model_dump(),
                        }
                    ),
                )
                divergence = compare(pair, engines, case.observation)
                report = RunReport(
                    **fields,
                    finishedAt=timestamp(),
                    outcome="reproduced" if divergence else "not_reproduced",
                    observations=pair,
                    divergence=divergence,
                    oracleAssessment=assess_oracle(case, pair),
                    artifacts=store.refs.copy(),
                )
                store.write("report", encode(report.model_dump()))
                store.commit()
                return report, store.path, 0
            except (
                KeyboardInterrupt,
                ExecutionFailure,
                DockerException,
                OSError,
                ValueError,
            ) as error:
                interrupted = isinstance(error, KeyboardInterrupt)
                failure = Failure(
                    code="interrupted"
                    if interrupted
                    else getattr(error, "code", "execution_unavailable"),
                    stage=getattr(error, "stage", "execution"),
                    message="The comparison was interrupted. Rerun explicitly when ready."
                    if interrupted
                    else getattr(
                        error,
                        "message",
                        "We couldn't complete the comparison. Check Docker, the approved images, and your writable evidence folder.",
                    ),
                    engineRole=getattr(error, "role", None),
                )
                report = RunReport(
                    **fields,
                    finishedAt=timestamp(),
                    outcome="failed",
                    failure=failure,
                    artifacts=store.refs.copy() if store else [],
                )
                if store:
                    try:
                        store.discard_completion()
                        for role, metadata in runner.evidence.items() if runner else []:
                            store.write("partial-" + role, encode(metadata))
                        store.write("failure", encode(report.model_dump()))
                    except (OSError, ValueError, ExecutionFailure):
                        pass
                return report, None, 130 if interrupted else 1
            finally:
                if store:
                    store.close()
                if client:
                    client.close()
    except ExecutionFailure as error:
        report = RunReport(
            **fields,
            finishedAt=timestamp(),
            outcome="failed",
            failure=Failure(code=error.code, stage=error.stage, message=error.message),
            artifacts=[],
        )
        return report, None, 1


def interrupt(signum, frame):
    raise KeyboardInterrupt()


def main():
    parser = argparse.ArgumentParser(
        description="Compare a reproducible case across approved engines."
    )
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--pair", required=True)
    args = parser.parse_args()
    print("Checking case…", file=sys.stderr)
    try:
        with args.case.open("rb") as stream:
            data = stream.read(262145)
        case = read_case(data)
        engines_for(args.pair)
        validate_parameters(case)
    except ValidationError as error:
        for item in error.errors(include_url=False, include_input=False):
            print(case_error(item), file=sys.stderr)
        return 2
    except (OSError, ValueError, RecursionError) as error:
        print(
            str(error)
            if isinstance(error, ValueError)
            else "Choose a readable case file.",
            file=sys.stderr,
        )
        return 2
    signal.signal(signal.SIGTERM, interrupt)
    report, path, code = run_case(
        data, case, args.pair, os.environ.get("FAULTGLASS_ARTIFACT_ROOT", "./evidence")
    )
    print(encode(report.model_dump()).decode())
    if code == 0:
        print(
            "Difference observed."
            if report.divergence
            else "No difference observed for this case and engine pair.",
            file=sys.stderr,
        )
        if report.divergence:
            print(
                "Changed: " + ", ".join(report.divergence.changedDimensions),
                file=sys.stderr,
            )
            print("Signature: " + report.divergence.signature, file=sys.stderr)
        print("Evidence saved: " + str(path), file=sys.stderr)
    else:
        print(
            "We couldn't complete the comparison. " + report.failure.message,
            file=sys.stderr,
        )
        if report.artifacts:
            partial_path = (
                Path(
                    os.environ.get("FAULTGLASS_ARTIFACT_ROOT", "./evidence")
                ).absolute()
                / report.runId
            )
            print("Incomplete evidence: " + str(partial_path), file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
