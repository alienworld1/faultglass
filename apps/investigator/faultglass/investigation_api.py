import json
import os
import threading
import time
from contextlib import closing
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from .context_artifacts import read_reference
from .context_errors import ContextError, ContextUnavailable, EvidenceIntegrity
from .context_models import evidence_id
from .graph_repository import GraphRepository
from .investigation_models import (
    TERMINAL,
    Admission,
    EvidenceItem,
    EvidencePage,
    ObservationSummary,
    PairedSummary,
)
from .investigation_store import InvestigationStore, RuntimeErrorResponse
from .jsonio import encode, loads
from .matrix import engines_for
from .models import read_case
from .validation_copy import case_error
from .worker_presence import worker_ready

router = APIRouter(prefix="/api/investigations")
streams = threading.BoundedSemaphore(16)
rate_lock = threading.Lock()
starts = {}


def error(code, message, status, *, fields=None):
    body = {"code": code, "message": message, "retryable": status in {429, 503}}
    if fields:
        body["fields"] = [
            {"path": str(item["path"])[:160], "message": str(item["message"])[:256]}
            for item in fields[:16]
        ]
    return JSONResponse(
        {"error": body},
        status_code=status,
        headers={"Retry-After": "10"} if status == 429 else None,
    )


def validate_id(value):
    try:
        return evidence_id(value)
    except ValueError:
        raise RuntimeErrorResponse(
            "invalid_id", "Choose a valid investigation ID.", 422
        ) from None


def bounded_response(value, status=200, headers=None):
    body = encode(value)
    if len(body) > 262144:
        raise EvidenceIntegrity()
    return JSONResponse(json.loads(body), status_code=status, headers=headers)


async def command_body(request):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 327680:
            raise RuntimeErrorResponse(
                "input_too_large", "Choose a case file smaller than 256 KiB.", 413
            )
    return bytes(data)


def service_readiness(repository):
    try:
        repository._assert_ready()
        context_ready = True
    except (ContextError, ValueError):
        context_ready = False
    ready = worker_ready(repository.config)
    return {"contextReady": context_ready, "workerReady": ready}


@router.post("")
async def start(request: Request):
    data = await command_body(request)
    try:
        command = Admission.model_validate(loads(data))
        if len(command.caseFile.encode()) > 262144:
            raise RuntimeErrorResponse(
                "input_too_large", "Choose a case file smaller than 256 KiB.", 413
            )
        read_case(command.caseFile.encode())
        engines_for(command.pairId)
        key = request.headers.get("Idempotency-Key", "")
        if str(UUID(key)) != key:
            raise ValueError()
    except ValidationError as exc:
        return error(
            "invalid_case",
            "Choose a valid case file and supported engine pair.",
            422,
            fields=[
                {"path": ".".join(map(str, item["loc"])), "message": case_error(item)}
                for item in exc.errors(include_input=False, include_url=False)
            ][:16],
        )
    except (ValueError, RecursionError, UnicodeError):
        return error(
            "invalid_command",
            "Choose a valid case file, supported engine pair, and start request ID.",
            422,
        )
    # Blocking graph and preflight work stays off the API event loop.
    from starlette.concurrency import run_in_threadpool

    def admit():
        with closing(GraphRepository()) as repository:
            store = InvestigationStore(repository)
            existing = store.lookup(key)
            if not existing:
                readiness = service_readiness(repository)
                from .api import readiness as engine_readiness

                if not all(readiness.values()) or command.pairId in engine_readiness():
                    raise RuntimeErrorResponse(
                        "service_unavailable",
                        "Investigations are temporarily unavailable. Check the worker and available engines.",
                    )
                address = request.client.host if request.client else "local"
                with rate_lock:
                    instant = time.monotonic()
                    if instant - starts.get(address, -10) < 10:
                        raise RuntimeErrorResponse(
                            "start_limited",
                            "Please wait a few seconds before starting another investigation.",
                            429,
                        )
                    starts[address] = instant
                    for old in list(starts):
                        if instant - starts[old] >= 10:
                            del starts[old]
            record, reused = store.admit(command, key)
            return bounded_response(
                {
                    "investigation": record.snapshot.model_dump(mode="json"),
                    "reused": reused,
                },
                202,
                {"Location": "/api/investigations/" + record.snapshot.id},
            )

    return await run_in_threadpool(admit)


@router.get("/admission/{key}")
def admission_lookup(key: str):
    validate_id(key)
    with closing(GraphRepository()) as repository:
        value = InvestigationStore(repository).lookup(key)
        if value is None:
            raise RuntimeErrorResponse(
                "not_found", "This start request was not found.", 404
            )
        return value


@router.get("/{job_id}")
def snapshot(job_id: str):
    validate_id(job_id)
    with closing(GraphRepository()) as repository:
        record = InvestigationStore(repository).load(job_id)
        return bounded_response(record.snapshot.model_dump(mode="json"))


@router.post("/{job_id}/cancel")
async def cancel(job_id: str, request: Request):
    validate_id(job_id)
    body = await command_body(request)
    if body.strip() not in {b"", b"{}"}:
        return error(
            "invalid_command", "Cancellation does not accept additional options.", 422
        )
    from starlette.concurrency import run_in_threadpool

    def persist():
        with closing(GraphRepository()) as repository:
            record, accepted = InvestigationStore(repository).cancel(job_id)
            return bounded_response(
                {
                    "investigation": record.snapshot.model_dump(mode="json"),
                    "accepted": accepted,
                },
                200 if record.snapshot.status in TERMINAL else 202,
            )

    return await run_in_threadpool(persist)


def cursor_for(job_id, after, header):
    try:
        if not after.isascii() or not after.isdecimal():
            raise ValueError()
        cursor = int(after)
        if header:
            identity, sequence = header.rsplit(":", 1)
            if identity != job_id or not sequence.isascii() or not sequence.isdecimal():
                raise ValueError()
            cursor = int(sequence)
        if not 0 <= cursor <= 512:
            raise ValueError()
        return cursor
    except (ValueError, TypeError):
        raise RuntimeErrorResponse(
            "invalid_cursor", "Choose a valid event cursor for this investigation.", 422
        ) from None


@router.get("/{job_id}/events")
def events(job_id: str, request: Request, after: str = "0"):
    validate_id(job_id)
    cursor = cursor_for(job_id, after, request.headers.get("Last-Event-ID"))
    repository = GraphRepository()
    store = InvestigationStore(repository)
    try:
        record = store.load(job_id)
        if cursor > record.snapshot.lastEventSequence:
            raise RuntimeErrorResponse(
                "cursor_ahead",
                "Reload the saved investigation before reconnecting.",
                409,
            )
        if not streams.acquire(blocking=False):
            raise RuntimeErrorResponse(
                "stream_limit",
                "Live connections are busy. Try reconnecting shortly.",
                429,
            )
    except BaseException:
        repository.close()
        raise

    def frames():
        nonlocal cursor, record
        heartbeat = time.monotonic()
        try:
            yield "retry: 3000\n\n"
            while True:
                for receipt in store.history(record):
                    event = receipt.event
                    if event.sequence > cursor:
                        yield f"id: {event.id}\nevent: {event.type}\ndata: {encode(event.model_dump(mode='json')).decode()}\n\n"
                        cursor = event.sequence
                if record.snapshot.status in TERMINAL:
                    return
                if time.monotonic() - heartbeat >= 15:
                    yield ": keep-alive\n\n"
                    heartbeat = time.monotonic()
                time.sleep(0.5)
                record = store.load(job_id)
        except (ContextUnavailable, EvidenceIntegrity, OSError, ValueError):
            return
        finally:
            repository.close()
            streams.release()

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{job_id}/evidence")
def evidence(job_id: str, cursor: int = 0, sequence: int | None = None):
    validate_id(job_id)
    if cursor < 0 or (sequence is not None and not 0 <= sequence <= 4):
        raise RuntimeErrorResponse(
            "invalid_cursor", "Choose a valid evidence page.", 422
        )
    with closing(GraphRepository()) as repository:
        store = InvestigationStore(repository)
        record = store.load(job_id)
        items = []
        for receipt in store.history(record):
            refs = receipt.outputs
            if not refs:
                continue
            report_ref = next((ref for ref in refs if ref.kind == "report"), None)
            plan_ref = next((ref for ref in refs if ref.path == "plan.json"), None)
            result_ref = next((ref for ref in refs if ref.path == "result.json"), None)
            if not any((report_ref, plan_ref, result_ref)):
                continue
            index = receipt.snapshot.probeSequence
            if sequence is not None and sequence != index:
                continue
            for ref in refs:
                read_reference(store.root, ref)
            observations = None
            case_query = None
            if report_ref:
                from .models import RunReport

                report = RunReport.model_validate(
                    loads(read_reference(store.root, report_ref))
                )
                summaries = {}
                for role in ("baseline", "target"):
                    observed = getattr(report.observations, role)
                    summaries[role] = ObservationSummary(
                        engineVersionId=observed.engineVersionId,
                        status=observed.status,
                        rowCount=len(observed.result.rows) if observed.result else None,
                        columns=[
                            column[:160] for column in observed.result.columns[:32]
                        ]
                        if observed.result
                        else [],
                        errorCategory=observed.error.category
                        if observed.error
                        else None,
                        detail=observed.error.detail[:256] if observed.error else None,
                    )
                observations = PairedSummary(**summaries)
                from .context_artifacts import load_evidence

                case_query = load_evidence(store.root, report.runId)[0].query
            plan = read_reference(store.root, plan_ref).decode() if plan_ref else None
            from .planner_models import Decision

            if plan and not Decision.model_validate(loads(plan)).selected_probe_id:
                continue
            items.append(
                EvidenceItem(
                    sequence=index,
                    kind="selection"
                    if plan_ref
                    else ("result" if result_ref else "seed"),
                    references=refs,
                    decision=plan,
                    observations=observations,
                    query=case_query,
                )
            )

        page, size, index = [], 0, cursor
        while index < len(items) and len(page) < 25:
            item = items[index]
            length = len(encode(item.model_dump()))
            if size + length > 240000:
                break
            page.append(item)
            size += length
            index += 1
        return bounded_response(
            EvidencePage(
                revision=record.snapshot.revision,
                items=page,
                nextCursor=index if index < len(items) else None,
            ).model_dump()
        )


def mutation_origins():
    return set(
        os.environ.get(
            "FAULTGLASS_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
        ).split(",")
    )
