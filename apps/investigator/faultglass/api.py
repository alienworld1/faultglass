from contextlib import closing

from docker.errors import DockerException
from fastapi import FastAPI

from .errors import ExecutionFailure
from .matrix import ENGINES, PAIRS, engines_for
from .runner import docker_client, verify_images

app = FastAPI(title="FaultGlass")


def readiness():
    issues = {}
    try:
        with closing(docker_client()) as client:
            for pair in PAIRS:
                try:
                    verify_images(client, engines_for(pair.id))
                except ExecutionFailure as error:
                    issues[pair.id] = error.code
    except (DockerException, OSError):
        issues = {pair.id: "docker_unavailable" for pair in PAIRS}
    return issues


@app.get("/api/health")
def health():
    issues = readiness()
    return {
        "status": "ok",
        "executionReady": any(pair.id not in issues for pair in PAIRS),
        "issues": sorted(set(issues.values()))
        or ([] if PAIRS else ["no_verified_pair"]),
    }


@app.get("/api/engine-matrix")
def engine_matrix():
    issues = readiness()
    return {
        "engines": [engine.model_dump() for engine in ENGINES],
        "pairs": [
            {
                **pair.model_dump(),
                "available": pair.id not in issues,
                **({"unavailableReason": issues[pair.id]} if pair.id in issues else {}),
            }
            for pair in PAIRS
        ],
    }
