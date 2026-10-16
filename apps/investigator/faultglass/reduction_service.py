import time
from uuid import uuid4

from .canonicalize import case_identity
from .context_artifacts import load_evidence, read_reference
from .context_errors import EvidenceIntegrity
from .context_models import EvidenceReference, Phase
from .context_phase import build_phase, child_id
from .investigation_budget import owned_bytes
from .investigation_models import Reservation, Status
from .investigation_planning import digest_bytes
from .investigation_store import now
from .jsonio import digest, encode, loads
from .models import read_case
from .planner_models import ProbeResult
from .probe_phase import link
from .reduction_artifacts import ReductionStore
from .reduction_candidates import candidates, case_size, validate_candidate
from .reduction_models import (
    ReductionAttempt,
    ReductionCheckpoint,
    ReductionSource,
    ReductionSummary,
)

EXECUTION_BYTES = 10485760
FINAL_BYTES = 2097152


def choose_source(store, record):
    seed = load_evidence(store.root, record.snapshot.id)
    for receipt in store.history(record):
        result_ref = next((r for r in receipt.outputs if r.path == "result.json"), None)
        if result_ref:
            result = ProbeResult.model_validate(
                loads(read_reference(store.root, result_ref))
            )
            case, report, _, _engines, _ = load_evidence(
                store.root, result.child_evidence_id
            )
            if case_identity(case)[
                0
            ] != result.output_case_id or result.child_signature != (
                report.divergence.signature if report.divergence else None
            ):
                raise EvidenceIntegrity()
            if report.divergence and report.divergence == seed[1].divergence:
                return result.child_evidence_id, result.sequence
    return record.snapshot.id, None


def preserving(source, report, engines):
    return (
        report.outcome == "reproduced"
        and report.divergence == source.referenceDivergence
        and list(engines) == source.engines
    )


class ReductionHandler:
    def __init__(self, worker):
        self.worker, self.store = worker, worker.store

    def storage(self, record):
        return ReductionStore(self.store.root, record.snapshot.id)

    def checkpoint(self, record):
        return self.storage(record).checkpoint(record)

    def limit(self, record, deadline, *, executions=1):
        if record.snapshot.cancelRequestedAt:
            return "cancelled"
        if deadline - time.monotonic() < 80 * executions:
            return "time_limit"
        if record.snapshot.lastEventSequence >= 460:
            return "event_limit"
        if (
            owned_bytes(self.store, record) + EXECUTION_BYTES * executions + FINAL_BYTES
            > record.snapshot.budget.maxArtifactBytes
        ):
            return "storage_limit"
        return None

    def publish(
        self,
        record,
        checkpoint,
        kind,
        message,
        *,
        reservation=None,
        phase=None,
        terminal=False,
    ):
        storage = self.storage(record)
        ref = storage.document("checkpoint", checkpoint)
        budget = record.snapshot.budget.model_copy(
            update={
                "reservedCandidates": checkpoint.summary.reservedCandidates,
                "stabilityChecks": int(checkpoint.stabilityReserved),
                "consideredAttempts": checkpoint.summary.consideredCount,
            }
        )
        changes = {
            "reduction": checkpoint.summary.model_dump(),
            "budget": budget.model_dump(),
            "record": {
                "reductionRef": ref.model_dump(),
                "reservation": reservation.model_dump() if reservation else None,
            },
        }
        eligible = (
            terminal
            and checkpoint.summary.state == "finished"
            and checkpoint.summary.source.stable
            and not checkpoint.summary.verificationFailures
            and record.snapshot.capabilities.classifying
        )
        if terminal and not eligible:
            cancelled = checkpoint.summary.stopReason == "cancelled"
            changes["terminalReason"] = {
                "code": "cancelled" if cancelled else "analysis_unavailable",
                "message": "Investigation cancelled. Collected evidence is preserved."
                if cancelled
                else "Reduction evidence is saved. Further analysis is unavailable.",
            }
        return self.store.commit(
            record.snapshot.id,
            kind,
            message,
            status=Status.CLASSIFYING
            if eligible
            else (
                Status.CANCELLED
                if checkpoint.summary.stopReason == "cancelled"
                else Status.UNRESOLVED
            )
            if terminal
            else Status.REDUCING,
            update=changes,
            outputs=[ref],
            phase=phase,
            expected_reservation=record.reservation,
        )

    def enter(self, record, deadline):
        identity, sequence = choose_source(self.store, record)
        case, report, _, engines, _ = load_evidence(self.store.root, identity)
        if not report.divergence:
            raise EvidenceIntegrity()
        storage = self.storage(record)
        source_ref = storage.put("source.faultglass.json", encode(case.model_dump()))
        size = case_size(case)
        original = read_case(read_reference(self.store.root, record.inputRef))
        source = ReductionSource(
            sourceKind="probe" if sequence else "seed",
            sourceProbeSequence=sequence,
            sourceEvidenceId=identity,
            sourceCaseId=case_identity(case)[0],
            sourceCaseRef=source_ref,
            referenceDivergence=report.divergence,
            engines=list(engines),
        )
        checkpoint = ReductionCheckpoint(
            summary=ReductionSummary(
                source=source,
                state="checking",
                originalSize=case_size(original),
                sourceSize=size,
                currentSize=size,
                currentCaseId=source.sourceCaseId,
                currentCaseRef=source_ref,
            ),
            seen=[source.sourceCaseId],
        )
        reason = self.limit(record, deadline, executions=2)
        if reason:
            return self.finish(record, checkpoint, reason)
        return self.publish(
            record, checkpoint, "reduction.started", "Checking the difference again."
        )

    def finish(self, record, checkpoint, reason):
        summary = checkpoint.summary
        summary.state = (
            "cancelled"
            if reason == "cancelled"
            else ("failed" if reason == "verification_failed" else "finished")
        )
        summary.stopReason = reason
        summary.finalCaseRef = self.storage(record).put(
            "reduced.faultglass.json",
            read_reference(self.store.root, summary.currentCaseRef),
        )
        messages = {
            "unstable_source": "The difference changed when checked again. Reduction was not started.",
            "verification_failed": "We couldn't verify this change. The last verified case is preserved.",
            "cancelled": "Investigation cancelled. Collected evidence is preserved.",
            "supported_passes_exhausted": "No smaller case found with the supported reductions.",
            "unsupported_shape": "No smaller case found with the supported reductions.",
        }
        return self.publish(
            record,
            checkpoint,
            "reduction.finished",
            messages.get(
                reason,
                "Reduction stopped at its limit. The last verified case is preserved.",
            ),
            terminal=True,
        )

    def reserve(self, record, checkpoint, data, purpose):
        ordinal = (
            1 if purpose == "stability" else checkpoint.summary.reservedCandidates + 1
        )
        reservation = Reservation(
            key=digest(
                {"job": record.snapshot.id, "purpose": purpose, "ordinal": ordinal}
            ),
            childId=str(uuid4()),
            inputSha256=digest_bytes(data),
            sequence=record.snapshot.probeSequence,
            state="reserved",
            reservedAt=now(),
            purpose=purpose,
            ordinal=ordinal,
        )
        if purpose == "stability":
            checkpoint.stabilityReserved = True
            checkpoint.summary.source.stabilityEvidenceId = reservation.childId
        else:
            checkpoint.summary.reservedCandidates += 1
            checkpoint.summary.state = "verifying"
            checkpoint.activeAttempt.state = "verifying"
            checkpoint.activeAttempt.verificationEvidenceId = reservation.childId
        return self.publish(
            record,
            checkpoint,
            "reduction.verifying",
            "Checking the difference again."
            if purpose == "stability"
            else "Verifying a smaller case.",
            reservation=reservation,
        )

    def step(self, record, deadline):
        checkpoint = self.checkpoint(record)
        reason = self.limit(record, deadline)
        if reason:
            return self.finish(record, checkpoint, reason)
        if record.reservation:
            return self.execute(record, checkpoint, deadline)
        if not checkpoint.stabilityReserved:
            return self.reserve(
                record,
                checkpoint,
                read_reference(
                    self.store.root, checkpoint.summary.source.sourceCaseRef
                ),
                "stability",
            )
        if not checkpoint.summary.source.stable:
            raise EvidenceIntegrity()
        if checkpoint.activeAttempt:
            return self.reserve(
                record,
                checkpoint,
                read_reference(self.store.root, checkpoint.activeAttempt.candidateRef),
                "reduction",
            )
        summary = checkpoint.summary
        if summary.reservedCandidates >= 4:
            return self.finish(record, checkpoint, "candidate_limit")
        if summary.consideredCount >= 32:
            return self.finish(record, checkpoint, "consideration_limit")
        parent = read_case(read_reference(self.store.root, summary.currentCaseRef))
        proposals = list(candidates(parent))
        if checkpoint.cursor >= len(proposals):
            return self.finish(
                record,
                checkpoint,
                "supported_passes_exhausted" if proposals else "unsupported_shape",
            )
        phase, transform, data, change = proposals[checkpoint.cursor]
        checkpoint.cursor += 1
        summary.consideredCount += 1
        ref = self.storage(record).put(
            f"candidate-{summary.consideredCount}.faultglass.json", data
        )
        candidate, rejection = None, None
        try:
            candidate = read_case(data)
            validate_candidate(parent, data)
        except ValueError as error:
            rejection = (
                "not_smaller" if "not smaller" in str(error) else "invalid_candidate"
            )
        identity = case_identity(candidate)[0] if candidate else None
        if not rejection and identity in checkpoint.seen:
            rejection = "duplicate"
        attempt = ReductionAttempt(
            id=digest(
                {
                    "job": record.snapshot.id,
                    "source": summary.source.sourceCaseId,
                    "parent": summary.currentCaseId,
                    "candidate": identity,
                    "transform": transform,
                    "ordinal": summary.consideredCount,
                }
            ),
            ordinal=summary.consideredCount,
            phase=phase,
            transformId=transform,
            parentCaseId=summary.currentCaseId,
            candidateCaseId=identity,
            candidatePayloadSha256=digest_bytes(data),
            candidateRef=ref,
            change=change,
            beforeSize=summary.currentSize,
            afterSize=case_size(candidate) if candidate else None,
            state="proposed",
            createdAt=now(),
            artifactRefs=[ref],
        )
        if identity and identity not in checkpoint.seen:
            checkpoint.seen.append(identity)
        checkpoint.activeAttempt = attempt
        summary.state = "proposing"
        if rejection:
            attempt.state, attempt.reason, attempt.resolvedAt = (
                "rejected",
                rejection,
                now(),
            )
            summary.rejectedCount += 1
            checkpoint.attempts.append(
                self.storage(record).document("attempt", attempt)
            )
            checkpoint.activeAttempt = None
            return self.publish(
                record,
                checkpoint,
                "reduction.rejected",
                "Change not retained. The case is not smaller."
                if rejection == "not_smaller"
                else "Change not retained. This change isn't supported.",
            )
        return self.publish(
            record, checkpoint, "phase.started", "Looking for a smaller case."
        )

    def execution_data(self, record, checkpoint):
        reservation = record.reservation
        ref = (
            checkpoint.summary.source.sourceCaseRef
            if reservation.purpose == "stability"
            else checkpoint.activeAttempt.candidateRef
        )
        data = read_reference(self.store.root, ref)
        if digest_bytes(data) != reservation.inputSha256:
            raise EvidenceIntegrity()
        return data

    def execute(self, record, checkpoint, deadline):
        from .worker import run_case

        data = self.execution_data(record, checkpoint)
        reservation = record.reservation
        active = self.publish(
            record,
            checkpoint,
            "reduction.verifying",
            "Checking the difference again."
            if reservation.purpose == "stability"
            else "Verifying a smaller case.",
            reservation=reservation.model_copy(update={"state": "started"}),
        )
        if active.snapshot.status != Status.REDUCING:
            return active
        _, _, code = run_case(
            data,
            read_case(data),
            record.snapshot.pairId,
            self.store.root,
            reserved_id=reservation.childId,
            admission_deadline=deadline,
        )
        if code:
            self.worker.clean_or_fail(active)
            stopped = self.fail(active)
            if code == 130:
                raise KeyboardInterrupt()
            return stopped
        return self.complete(active)

    def fail(self, record):
        checkpoint = self.checkpoint(record)
        checkpoint.summary.verificationFailures += 1
        if checkpoint.activeAttempt:
            attempt = checkpoint.activeAttempt
            attempt.state, attempt.reason, attempt.resolvedAt = (
                "failed",
                "execution_failure",
                now(),
            )
            checkpoint.attempts.append(
                self.storage(record).document("attempt", attempt)
            )
            checkpoint.activeAttempt = None
        return self.finish(record, checkpoint, "verification_failed")

    def complete(self, record):
        checkpoint = self.checkpoint(record)
        reservation = record.reservation
        data = self.execution_data(record, checkpoint)
        candidate, report, _, engines, _ = load_evidence(
            self.store.root, reservation.childId
        )
        if (
            encode(candidate.model_dump()) != encode(read_case(data).model_dump())
            or report.caseContentHash != reservation.inputSha256
            or list(engines) != checkpoint.summary.source.engines
        ):
            raise EvidenceIntegrity()
        same = preserving(checkpoint.summary.source, report, engines)
        phase = self.graph_phase(record, checkpoint, same)
        summary = checkpoint.summary
        if reservation.purpose == "stability":
            if not same:
                # Publish both observations before recording the honest stop.
                saved = self.publish(
                    record,
                    checkpoint,
                    "reduction.verifying",
                    "The difference changed when checked again.",
                    phase=phase,
                )
                if saved.snapshot.status == Status.CANCELLED:
                    return saved
                return self.finish(saved, self.checkpoint(saved), "unstable_source")
            summary.source.stable = True
            summary.state = "proposing"
            return self.publish(
                record, checkpoint, "phase.started", "Reducing the query.", phase=phase
            )
        attempt = checkpoint.activeAttempt
        parent = read_case(read_reference(self.store.root, summary.currentCaseRef))
        validate_candidate(parent, data)
        if (
            attempt.parentCaseId != summary.currentCaseId
            or attempt.candidateCaseId != case_identity(candidate)[0]
            or attempt.beforeSize != case_size(parent)
            or attempt.afterSize != case_size(candidate)
        ):
            raise EvidenceIntegrity()
        attempt.observedDivergence = report.divergence
        attempt.artifactRefs = [attempt.candidateRef, *phase.artifacts]
        attempt.resolvedAt = report.finishedAt
        attempt.state = "accepted" if same else "rejected"
        attempt.reason = (
            "verified"
            if same
            else ("signature_changed" if report.divergence else "difference_eliminated")
        )
        decision = self.storage(record).document("attempt", attempt)
        checkpoint.attempts.append(decision)
        checkpoint.activeAttempt = None
        summary.state = "proposing"
        if same:
            summary.acceptedCount += 1
            summary.currentCaseId, summary.currentCaseRef, summary.currentSize = (
                attempt.candidateCaseId,
                attempt.candidateRef,
                attempt.afterSize,
            )
            checkpoint.cursor = 0
            phase.edges.append(
                link(
                    "REDUCED_TO",
                    child_id(summary.source.sourceEvidenceId, "divergence"),
                    summary.currentCaseId,
                    report.finishedAt,
                    decision,
                    investigation_id=record.snapshot.id,
                    attempt_id=attempt.id,
                    ordinal=attempt.ordinal,
                    parent_case_id=attempt.parentCaseId,
                    verification_evidence_id=reservation.childId,
                    reference_signature=summary.source.referenceDivergence.signature,
                )
            )
            phase.payload_sha256 = digest(
                {"phase": phase.model_dump(), "decision": decision.model_dump()}
            )
        else:
            summary.rejectedCount += 1
        return self.publish(
            record,
            checkpoint,
            "reduction.accepted" if same else "reduction.rejected",
            "Smaller case verified. The same difference remains."
            if same
            else (
                "Change not retained. A different difference was observed."
                if report.divergence
                else "Change not retained. The difference disappeared."
            ),
            phase=phase,
        )

    def graph_phase(self, record, checkpoint, same):
        reservation = record.reservation
        phase = build_phase(self.store.root, reservation.childId)
        phase.investigation_id = record.snapshot.id
        phase.nodes = [n for n in phase.nodes if n.label != "Investigation"]
        phase.edges = [e for e in phase.edges if e.type != "STARTED_FROM"]
        for node in phase.nodes:
            if node.label in {"Run", "Divergence"}:
                node.properties["investigation_id"] = record.snapshot.id
                if node.label == "Run":
                    node.properties["child_evidence_id"] = reservation.childId
            if (
                node.label == "Divergence"
                and reservation.purpose == "stability"
                and same
            ):
                source = checkpoint.summary.source
                source_report = next(
                    r
                    for r in load_evidence(self.store.root, source.sourceEvidenceId)[2]
                    if r.kind == "report"
                )
                source_ref = EvidenceReference(
                    **source_report.model_dump(), owner=source.sourceEvidenceId
                )
                node.properties.update(
                    stable=True,
                    stability_source_artifact_ref=encode(
                        source_ref.model_dump()
                    ).decode(),
                    stability_case_id=source.sourceCaseId,
                )
        for edge in phase.edges:
            if edge.type == "EXECUTED_AS":
                edge.source_id = record.snapshot.id
                edge.properties.update(
                    purpose=reservation.purpose, ordinal=reservation.ordinal
                )
        phase.phase_key = reservation.key
        phase.payload_sha256 = digest(
            {
                "key": reservation.key,
                "nodes": [n.model_dump() for n in phase.nodes],
                "edges": [e.model_dump() for e in phase.edges],
            }
        )
        return Phase.model_validate(phase.model_dump())
