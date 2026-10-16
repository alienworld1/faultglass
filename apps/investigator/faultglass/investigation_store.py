import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .artifacts import atomic_write, open_private_root
from .context_artifacts import owner_directory, read_file, read_reference
from .context_errors import ContextUnavailable, EvidenceIntegrity, IdentityConflict
from .context_lock import ContextLease
from .context_models import ENDPOINTS, EvidenceReference, Node, evidence_id
from .investigation_models import (
    TERMINAL,
    Capabilities,
    Event,
    EventData,
    PhaseReceipt,
    RuntimeRecord,
    Snapshot,
    Status,
    transition,
)
from .jsonio import digest, encode, loads
from .matrix import engines_for


class RuntimeErrorResponse(Exception):
    def __init__(self, code, message, status=503):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def now():
    return datetime.now(UTC).isoformat()


class InvestigationStore:
    def __init__(self, repository):
        self.repository = repository
        self.root = repository.config.artifact_root

    def put(self, job_id, name, data):
        evidence_id(job_id)
        if not name.endswith(".json") or "/" in name or len(data) > 262144:
            raise EvidenceIntegrity()
        with owner_directory(self.root, job_id + "/runtime") as fd:
            try:
                old = read_file(fd, name, 262144)
            except FileNotFoundError:
                old = None
            if old is not None and old != data:
                raise IdentityConflict()
            if old is None:
                atomic_write(fd, name, data)
        ref = EvidenceReference(
            id=digest({"owner": job_id + "/runtime", "path": name}),
            owner=job_id + "/runtime",
            path=name,
            kind="runtime",
            mediaType="application/json",
            sha256=hashlib.sha256(data).hexdigest(),
            bytes=len(data),
        )
        read_reference(self.root, ref)
        return ref

    def load(self, job_id, *, verify_outputs=True):
        evidence_id(job_id)
        props = self.repository._lookup(job_id)
        if props is None:
            raise RuntimeErrorResponse(
                "not_found", "We couldn't find that investigation.", 404
            )
        if props.get("runtime_version") != "runtime-v1":
            raise RuntimeErrorResponse(
                "unsupported_record",
                "This saved investigation cannot be resumed by this version.",
                409,
            )
        Node(label="Investigation", properties=props)
        ref = EvidenceReference.model_validate(loads(props["runtime_artifact_ref"]))
        record = RuntimeRecord.model_validate(loads(read_reference(self.root, ref)))
        if (
            record.snapshot.id != job_id
            or ref.owner != job_id + "/runtime"
            or props["revision"] != record.snapshot.revision
            or props["status"] != record.snapshot.status
            or props["runtime_receipt_key"] != record.receiptKey
        ):
            raise EvidenceIntegrity()
        if verify_outputs:
            for output in record.outputs:
                read_reference(self.root, output)
            if record.reductionRef:
                from .reduction_reads import reduction_page

                reduction_page(self, record)
        return record

    def lookup(self, key):
        evidence_id(key)
        rows = self.repository._query("runtime-admission", {"key": key})
        if len(rows) > 1:
            raise IdentityConflict()
        if not rows:
            return None
        record = self.load(rows[0][0])
        return {"id": record.snapshot.id, "payloadSha256": record.payloadSha256}

    def pending(self):
        return [
            row[0]
            for row in self.repository._query(
                "runtime-pending", {"terminal": list(TERMINAL)}
            )
        ]

    def admit(self, command, key):
        payload = digest(
            {
                "caseFile": command.caseFile,
                "pairId": command.pairId,
                "version": "runtime-v1",
            }
        )
        with ContextLease():
            self.repository._assert_ready()
            existing = self.lookup(key)
            if existing:
                if existing["payloadSha256"] != payload:
                    raise RuntimeErrorResponse(
                        "admission_conflict",
                        "This start request was already used for a different case or engine pair.",
                        409,
                    )
                return self.load(existing["id"]), True
            queued = self.repository._query("runtime-queued")
            if queued[0][0] >= 8:
                raise RuntimeErrorResponse(
                    "queue_full",
                    "The investigation queue is full. Try again shortly.",
                    429,
                )
            from .models import read_case

            case = read_case(command.caseFile.encode())
            job_id, created = str(uuid4()), now()
            _, fd = open_private_root(self.root)
            try:
                os.mkdir(job_id, 0o700, dir_fd=fd)
                os.fsync(fd)
            finally:
                os.close(fd)
            with owner_directory(self.root, job_id) as fd:
                os.mkdir("runtime", 0o700, dir_fd=fd)
                os.fsync(fd)
            input_ref = self.put(job_id, "input.json", command.caseFile.encode())
            snapshot = Snapshot(
                id=job_id,
                title=case.title,
                pairId=command.pairId,
                engines=list(engines_for(command.pairId)),
                createdAt=created,
                updatedAt=created,
                deadlineAt=(
                    datetime.fromisoformat(created) + timedelta(seconds=900)
                ).isoformat(),
            )
            from .analysis_artifacts import AnalysisStore
            from .explorer import initial_run, summary
            from .worker_presence import worker_agent_readiness

            worker_agent = worker_agent_readiness(self.repository.config)
            run = initial_run(
                job_id,
                created,
                None
                if worker_agent["agentReason"] == "worker_unavailable"
                else worker_agent,
            )
            agent_ref = AnalysisStore(self.root, job_id, "agent").document("run", run)
            snapshot.agent = summary(run)
            snapshot.capabilities = Capabilities(
                reducing=True, classifying=True, exporting=True
            )
            event = self.event(
                snapshot, "investigation.created", "Waiting to investigate."
            )
            record = RuntimeRecord(
                snapshot=snapshot,
                admissionKey=key,
                payloadSha256=payload,
                inputRef=input_ref,
                agentRef=agent_ref,
                event=event,
                receiptKey=digest(
                    {"investigation": job_id, "revision": 1, "handler": "runtime-v1"}
                ),
            )
            self._publish(record, None)
            return self.load(job_id), False

    def event(self, snapshot, kind, summary):
        return Event(
            id=f"{snapshot.id}:{snapshot.lastEventSequence}",
            investigationId=snapshot.id,
            sequence=snapshot.lastEventSequence,
            type=kind,
            at=snapshot.updatedAt,
            phase=snapshot.phase,
            summary=summary,
            data=EventData(
                revision=snapshot.revision,
                status=snapshot.status,
                probeSequence=snapshot.probeSequence,
                currentCaseId=snapshot.reduction.currentCaseId
                if snapshot.reduction
                else None,
            ),
        )

    def commit(
        self,
        job_id,
        kind,
        summary,
        *,
        status=None,
        update=None,
        outputs=(),
        phase=None,
        expected_reservation=None,
        memory_updates=(),
    ):
        with ContextLease():
            self.repository._assert_ready()
            current = self.load(job_id, verify_outputs=status != Status.FAILED)
            snapshot = current.snapshot
            if phase:
                phase_key = digest(
                    {
                        "investigation": job_id,
                        "phase": phase.phase_key,
                        "attempt": snapshot.phaseAttempt,
                        "handler": "runtime-v1",
                    }
                )
                for previous in self.history(current):
                    receipt = previous.phaseReceipt
                    if receipt and receipt.key == phase_key:
                        if receipt.payloadSha256 != phase.payload_sha256:
                            raise IdentityConflict()
                        return current
            if snapshot.status in TERMINAL or (
                kind == "cancellation.requested" and snapshot.cancelRequestedAt
            ):
                return current
            if kind == "cancellation.requested" and snapshot.status in {
                Status.CLASSIFYING,
                Status.EXPORTING,
            }:
                raise RuntimeErrorResponse(
                    "finishing",
                    "This investigation is finishing and can no longer be cancelled.",
                    409,
                )
            if (
                expected_reservation is not None
                and current.reservation != expected_reservation
            ):
                raise IdentityConflict()
            changes = dict(update or {})
            record_changes = changes.pop("record", {})
            target = status or snapshot.status
            if (
                snapshot.cancelRequestedAt
                and kind != "cancellation.requested"
                and target != Status.FAILED
            ):
                target = Status.CANCELLED
                changes["terminalReason"] = {
                    "code": "cancelled",
                    "message": "Investigation cancelled. Collected evidence is preserved.",
                }
                kind, summary = (
                    "investigation.cancelled",
                    changes["terminalReason"]["message"],
                )
            if target != snapshot.status:
                transition(
                    snapshot.status,
                    target,
                    reducing=True,
                    downstream=snapshot.capabilities.classifying
                    and snapshot.capabilities.exporting,
                )
            if target == Status.CANCELLED and (
                changes.get("reduction") or snapshot.reduction
            ):
                from .reduction_artifacts import ReductionStore
                from .reduction_models import ReductionCheckpoint

                storage = ReductionStore(self.root, job_id)
                checkpoint_ref = (
                    record_changes.get("reductionRef") or current.reductionRef
                )
                if isinstance(checkpoint_ref, dict):
                    checkpoint_ref = EvidenceReference.model_validate(checkpoint_ref)
                checkpoint = ReductionCheckpoint.model_validate(
                    loads(read_reference(self.root, checkpoint_ref))
                )
                checkpoint.summary.state = "cancelled"
                checkpoint.summary.stopReason = "cancelled"
                checkpoint.summary.finalCaseRef = storage.put(
                    "reduced.faultglass.json",
                    read_reference(self.root, checkpoint.summary.currentCaseRef),
                )
                fresh_ref = storage.document("checkpoint", checkpoint)
                changes["reduction"] = checkpoint.summary.model_dump()
                record_changes["reductionRef"] = fresh_ref.model_dump()
                outputs = [fresh_ref]
                record_changes["reservation"] = None
            if target in TERMINAL:
                changes["finishedAt"] = now()
                record_changes["workerId"] = None
            changes.update(
                status=target,
                phase=target,
                revision=snapshot.revision + 1,
                lastEventSequence=snapshot.lastEventSequence + 1,
                updatedAt=now(),
            )
            if changes["lastEventSequence"] > 512:
                raise EvidenceIntegrity()
            if phase:
                self.repository._check_immutable(phase)
            previous_ref = EvidenceReference.model_validate(
                loads(self.repository._lookup(job_id)["runtime_artifact_ref"])
            )
            values = {**snapshot.model_dump(), **changes}
            fresh = Snapshot.model_validate(values)
            record = RuntimeRecord.model_validate(
                {
                    **current.model_dump(),
                    **record_changes,
                    "snapshot": fresh.model_dump(),
                    "previous": previous_ref.model_dump(),
                    "outputs": [ref.model_dump() for ref in outputs],
                    "event": self.event(fresh, kind, summary).model_dump(),
                    "receiptKey": digest(
                        {
                            "investigation": job_id,
                            "phase": fresh.phase,
                            "sequence": fresh.probeSequence,
                            "attempt": fresh.phaseAttempt,
                            "revision": fresh.revision,
                            "handler": "runtime-v1",
                        }
                    ),
                }
            )
            if record.reductionRef:
                from .reduction_artifacts import ReductionStore
                from .reduction_models import ReductionAttempt

                checkpoint = ReductionStore(self.root, job_id).checkpoint(record)
                attempt = checkpoint.activeAttempt
                if (
                    attempt is None
                    and checkpoint.attempts
                    and kind in {"reduction.accepted", "reduction.rejected"}
                ):
                    attempt = ReductionAttempt.model_validate(
                        loads(read_reference(self.root, checkpoint.attempts[-1]))
                    )
                if attempt:
                    record.event.data.attemptId = attempt.id
                    record.event.data.attemptOrdinal = attempt.ordinal
                record.event.data.references = [record.reductionRef]
            if phase:
                record.phaseReceipt = PhaseReceipt(
                    key=digest(
                        {
                            "investigation": job_id,
                            "phase": phase.phase_key,
                            "attempt": fresh.phaseAttempt,
                            "handler": "runtime-v1",
                        }
                    ),
                    payloadSha256=phase.payload_sha256,
                    sequence=next(
                        (
                            int(ref.owner.rsplit("/", 1)[1])
                            for ref in outputs
                            if "/planning/" in ref.owner
                        ),
                        fresh.probeSequence,
                    ),
                    attempt=fresh.phaseAttempt,
                    purpose=current.reservation.purpose
                    if current.reservation
                    else None,
                    ordinal=current.reservation.ordinal if current.reservation else 0,
                    previous=previous_ref,
                    inputs=[current.inputRef],
                    outputs=list(outputs),
                )
            else:
                record.phaseReceipt = None
            self._publish(record, current, phase, memory_updates=memory_updates)
            return self.load(job_id)

    def _publish(self, record, current, phase=None, *, memory_updates=()):
        from .investigation_budget import owned_bytes

        snapshot = record.snapshot
        used = owned_bytes(self, current or record)
        if record.reservation and (
            not current or current.reservation != record.reservation
        ):
            used = max(used, owned_bytes(self, record))
        for _ in range(4):
            charged = used + len(encode(record.model_dump()))
            record.snapshot.budget.chargedBytes = charged
        if record.snapshot.budget.chargedBytes > 67108864:
            raise EvidenceIntegrity()
        if len(encode(record.event.model_dump())) > 4096:
            raise EvidenceIntegrity()
        ref = self.put(
            snapshot.id,
            f"receipt-{snapshot.revision}-{digest(record.model_dump())}.json",
            encode(record.model_dump()),
        )
        props = dict(
            id=snapshot.id,
            created_at=snapshot.createdAt,
            updated_at=snapshot.updatedAt,
            runtime_version="runtime-v1",
            workspace_id="falkordb-core",
            context_schema_version="context-v1",
            canonicalization_version="case-v1",
            fingerprint_version="fingerprint-v1",
            status=snapshot.status.value,
            revision=snapshot.revision,
            admission_key=record.admissionKey,
            payload_sha256=record.payloadSha256,
            runtime_artifact_ref=encode(ref.model_dump()).decode(),
            runtime_receipt_key=record.receiptKey,
        )
        params = {
            "id": snapshot.id,
            "expected": current.snapshot.revision if current else 0,
            "props": props,
        }
        for label in (
            "FaultCase",
            "Fingerprint",
            "EngineVersion",
            "Run",
            "Divergence",
            "FaultFamily",
            "RegressionTest",
        ):
            params[label] = (
                [n.properties for n in phase.nodes if n.label == label] if phase else []
            )
        params["MemoryUpdates"] = list(memory_updates)
        params["memory_ids"] = [entry["properties"]["id"] for entry in memory_updates]
        for kind in ENDPOINTS:
            params[kind] = (
                [e.model_dump() for e in phase.edges if e.type == kind] if phase else []
            )
        if phase:
            i = next(
                (n.properties for n in phase.nodes if n.label == "Investigation"), None
            )
            if i:
                params["props"].update(
                    {
                        k: v
                        for k, v in i.items()
                        if k
                        not in {
                            "id",
                            "status",
                            "updated_at",
                            "created_at",
                            "terminal_reason",
                        }
                    }
                )
                params["props"].update(
                    seed_status=i["status"],
                    context_payload_sha256=phase.payload_sha256,
                    context_recorded_at=now(),
                )
        Node(label="Investigation", properties=params["props"])
        uncertain = False
        try:
            self.repository._query(
                "runtime-commit" if current else "runtime-create", params, write=True
            )
        except ContextUnavailable:
            uncertain = True
            self.repository.close()
        try:
            saved = self.load(snapshot.id)
        except RuntimeErrorResponse as exc:
            if uncertain and exc.status == 404:
                raise ContextUnavailable() from None
            raise
        if saved.receiptKey == record.receiptKey and digest(
            saved.model_dump()
        ) != digest(record.model_dump()):
            raise IdentityConflict()
        if saved.receiptKey == record.receiptKey and memory_updates:
            for entry in memory_updates:
                rows = self.repository._query(
                    "edge-identities", {"ids": [entry["properties"]["id"]]}
                )
                if len(rows) != 1 or dict(rows[0][3]) != entry["properties"]:
                    raise IdentityConflict()
        if saved.receiptKey != record.receiptKey:
            if (
                uncertain
                and current
                and saved.snapshot.revision == current.snapshot.revision
            ):
                raise ContextUnavailable()
            raise IdentityConflict()

    def cancel(self, job_id):
        with ContextLease():
            current = self.load(job_id)
            if (
                current.snapshot.status in TERMINAL
                or current.snapshot.cancelRequestedAt
            ):
                return current, False
            if current.snapshot.status in {Status.CLASSIFYING, Status.EXPORTING}:
                raise RuntimeErrorResponse(
                    "finishing",
                    "This investigation is finishing and can no longer be cancelled.",
                    409,
                )
        requested_at = now()
        record = self.commit(
            job_id,
            "cancellation.requested",
            "Cancellation requested. Finishing the current comparison and cleanup.",
            update={"cancelRequestedAt": requested_at},
        )
        return (
            record,
            record.snapshot.cancelRequestedAt == requested_at
            and record.snapshot.status not in TERMINAL,
        )

    def history(self, record):
        result = []
        cursor = record
        while True:
            result.append(cursor)
            if cursor.previous is None:
                break
            previous = RuntimeRecord.model_validate(
                loads(read_reference(self.root, cursor.previous))
            )
            if (
                previous.snapshot.id != record.snapshot.id
                or previous.snapshot.revision + 1 != cursor.snapshot.revision
                or previous.event.sequence + 1 != cursor.event.sequence
            ):
                raise EvidenceIntegrity()
            cursor = previous
            if len(result) > 512:
                raise EvidenceIntegrity()
        return list(reversed(result))
