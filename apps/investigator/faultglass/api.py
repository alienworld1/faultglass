from contextlib import closing

from docker.errors import DockerException
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from .context_errors import ContextError, ContextUnavailable
from .errors import ExecutionFailure
from .graph_repository import GraphRepository
from .investigation_api import error, mutation_origins, router, service_readiness
from .investigation_store import RuntimeErrorResponse
from .matrix import ENGINES, PAIRS, engines_for
from .runner import docker_client, verify_images

app = FastAPI(title="FaultGlass")
app.include_router(router)


@app.middleware("http")
async def protect_commands(request: Request, call_next):
    if request.method == "POST":
        origin = request.headers.get("origin")
        if origin and origin not in mutation_origins():
            return error(
                "origin_not_allowed",
                "This page cannot start or change investigations.",
                403,
            )
        if request.headers.get("sec-fetch-site") == "cross-site":
            return error(
                "origin_not_allowed",
                "This page cannot start or change investigations.",
                403,
            )
    return await call_next(request)


@app.exception_handler(RuntimeErrorResponse)
async def runtime_error(request, exc):
    return error(exc.code, exc.message, exc.status)


@app.exception_handler(ContextError)
async def context_error(request, exc):
    return error(
        "context_unavailable"
        if isinstance(exc, ContextUnavailable)
        else "evidence_unavailable",
        "Investigation memory is temporarily unavailable."
        if isinstance(exc, ContextUnavailable)
        else "Saved evidence could not be verified.",
        503,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return error("invalid_request", "Choose a valid investigation request.", 422)


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    return error(
        "service_unavailable",
        "Investigations are temporarily unavailable. Try reconnecting shortly.",
        503,
    )


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
    with closing(GraphRepository()) as repository:
        runtime = service_readiness(repository)
    return {
        **runtime,
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


@app.post("/api/cases/validate")
async def validate_case(request: Request):
    from pydantic import ValidationError

    from .investigation_api import command_body
    from .investigation_models import Admission
    from .jsonio import loads
    from .models import read_case
    from .validation_copy import case_error

    try:
        command = Admission.model_validate(loads(await command_body(request)))
        if len(command.caseFile.encode()) > 262144:
            return error(
                "input_too_large", "Choose a case file smaller than 256 KiB.", 413
            )
        case = read_case(command.caseFile.encode())
        engines_for(command.pairId)
        return {"title": case.title, "query": case.query}
    except ValidationError as exc:
        return error(
            "invalid_case",
            "Choose a valid case file.",
            422,
            fields=[
                {"path": ".".join(map(str, item["loc"])), "message": case_error(item)}
                for item in exc.errors(include_input=False, include_url=False)
            ][:16],
        )
    except (ValueError, RecursionError, UnicodeError):
        return error(
            "invalid_case", "Choose a valid case file and supported engine pair.", 422
        )
