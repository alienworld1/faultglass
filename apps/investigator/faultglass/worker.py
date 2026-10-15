import signal
import sys
import time
from contextlib import closing
from datetime import UTC, datetime
from uuid import uuid4

from docker.errors import DockerException

from .artifacts import Lease
from .context_artifacts import load_evidence, read_reference
from .context_errors import ContextError, ContextUnavailable, EvidenceIntegrity
from .execution import interrupt, run_case
from .graph_repository import GraphRepository
from .investigation_budget import execution_deadline, owned_bytes, verify_committed
from .investigation_models import TERMINAL, Reservation, Status
from .investigation_planning import (
    digest_bytes,
    fingerprint_phase,
    plan_next,
    seed_phase,
    verify_selection,
)
from .investigation_store import InvestigationStore, now
from .jsonio import digest
from .lifecycle import cleanup_deadline
from .matrix import PAIRS, engines_for
from .models import read_case
from .probe_service import reconcile_result
from .runner import OWNER, docker_client, verify_images
from .worker_presence import WorkerPresence


class Worker:
    def __init__(self, repository):
        self.repository = repository
        self.store = InvestigationStore(repository)
        self.id = str(uuid4())
        self.deadlines = {}

    def cleanup(self):
        known = {}
        for job_id in self.store.pending():
            record = self.store.load(job_id, verify_outputs=False)
            if record.reservation:
                known[record.reservation.childId] = record
        with Lease(), closing(docker_client()) as client:
            containers = client.containers.list(all=True, filters={"label": OWNER})
            for container in containers:
                identity = container.labels.get(OWNER)
                if identity not in known:
                    raise ContextError(
                        "An unrecognized comparison still owns engines. Inspect its run identity before targeted recovery."
                    )
                with cleanup_deadline(10):
                    container.remove(force=True, v=True)
            if client.containers.list(all=True, filters={"label": OWNER}):
                raise ContextError(
                    "Owned engines could not be removed. Targeted recovery is required."
                )

    def clean_or_fail(self, record):
        try:
            self.cleanup()
        except (ContextError, DockerException, OSError, ValueError):
            self.store.commit(
                record.snapshot.id,
                "investigation.failed",
                "Owned engines could not be removed. Targeted recovery is required.",
                status=Status.FAILED,
                update={
                    "terminalReason": {
                        "code": "cleanup_required",
                        "message": "Owned engines could not be removed. Targeted recovery is required.",
                    }
                },
            )
            raise ContextError(
                "Targeted engine cleanup is required before execution can continue."
            ) from None

    def stop(self, record, status, code, message, *, phase=None, outputs=()):
        return self.store.commit(
            record.snapshot.id,
            "investigation." + status.value.lower(),
            message,
            status=status,
            update={
                "terminalReason": {"code": code, "message": message},
                "record": {"reservation": None, "workerId": None},
            },
            phase=phase,
            outputs=outputs,
        )

    def step(self, job_id):
        record = self.store.load(job_id)
        if record.snapshot.status in TERMINAL:
            return record
        verify_committed(self.store, record)
        snapshot = record.snapshot
        limit = self.deadlines.setdefault(
            job_id,
            time.monotonic()
            + min(
                900,
                max(
                    0,
                    (
                        datetime.fromisoformat(snapshot.deadlineAt) - datetime.now(UTC)
                    ).total_seconds(),
                ),
            ),
        )
        deadline = execution_deadline(record, limit)
        # Started work is reconciled before control intents or expired budgets are applied.
        if record.reservation and record.reservation.state == "started":
            try:
                load_evidence(self.store.root, record.reservation.childId)
            except ContextError:
                self.clean_or_fail(record)
                return self.stop(
                    record,
                    Status.FAILED,
                    "recovery_required",
                    "The comparison was interrupted before complete evidence was saved. Start a new investigation when ready.",
                )
            return self.complete_execution(record)
        if snapshot.cancelRequestedAt:
            return self.stop(
                record,
                Status.CANCELLED,
                "cancelled",
                "Investigation cancelled. Collected evidence is preserved.",
            )
        if time.monotonic() >= deadline or snapshot.lastEventSequence >= 470:
            return self.stop(
                record,
                Status.UNRESOLVED,
                "budget_exhausted",
                "The experiment budget was reached.",
            )
        handlers = {
            Status.QUEUED: self.claim,
            Status.FINGERPRINTING: self.fingerprint,
            Status.PLANNING: self.plan,
            Status.REPRODUCING: self.execute,
            Status.PROBING: self.execute,
        }
        handler = handlers.get(snapshot.status)
        if handler is None:
            raise EvidenceIntegrity()
        return handler(record, deadline)

    def claim(self, record, _deadline):
        job_id = record.snapshot.id
        return self.store.commit(
            job_id,
            "phase.started",
            "Fingerprinting case",
            status=Status.FINGERPRINTING,
            update={
                "startedAt": now(),
                "phaseAttempt": 1,
                "record": {"workerId": self.id},
            },
        )

    def fingerprint(self, record, _deadline):
        job_id = record.snapshot.id
        phase = fingerprint_phase(self.store, record)
        reservation = Reservation(
            key=digest({"job": job_id, "phase": "seed", "attempt": 1}),
            childId=job_id,
            inputSha256=record.inputRef.sha256,
            state="reserved",
            sequence=0,
            reservedAt=now(),
        )
        return self.store.commit(
            job_id,
            "fingerprint.completed",
            "Fingerprint recorded. Reproducing the difference.",
            status=Status.REPRODUCING,
            update={
                "fingerprintId": phase.fingerprint_id,
                "record": {"reservation": reservation.model_dump()},
            },
            outputs=phase.artifacts,
            phase=phase,
        )

    def plan(self, record, deadline):
        job_id = record.snapshot.id
        snapshot = record.snapshot
        if snapshot.budget.reservedProbes >= 4:
            return self.stop(
                record,
                Status.UNRESOLVED,
                "budget_exhausted",
                "The experiment budget was reached.",
            )
        plan, phase = plan_next(self.repository, record)
        if not plan.candidates:
            return self.stop(
                record,
                Status.UNRESOLVED,
                "no_applicable_probe",
                "No supported experiments remain.",
                phase=phase,
                outputs=phase.artifacts,
            )
        used = owned_bytes(self.store, record)
        if (
            deadline - time.monotonic() < 80
            or used + 12582912 > snapshot.budget.maxArtifactBytes
        ):
            return self.stop(
                record,
                Status.UNRESOLVED,
                "budget_exhausted",
                "The experiment budget was reached.",
                phase=phase,
                outputs=phase.artifacts,
            )
        reservation = Reservation(
            key=digest({"selection": plan.selection_id, "attempt": 1}),
            childId=str(uuid4()),
            inputSha256=plan.transformed_case_ref.sha256,
            state="reserved",
            sequence=plan.sequence,
            reservedAt=now(),
        )
        budget = snapshot.budget.model_copy(
            update={
                "reservedProbes": snapshot.budget.reservedProbes + 1,
                "chargedBytes": used,
            }
        )
        return self.store.commit(
            job_id,
            "probe.selected",
            plan.candidates[0].reason,
            status=Status.PROBING,
            update={
                "probeSequence": plan.sequence,
                "budget": budget.model_dump(),
                "record": {
                    "reservation": reservation.model_dump(),
                    "triedOutputs": [
                        *record.triedOutputs,
                        plan.candidates[0].output_case_id,
                    ],
                },
            },
            phase=phase,
            outputs=phase.artifacts,
        )

    def execute(self, record, deadline):
        job_id = record.snapshot.id
        snapshot = record.snapshot
        if (
            deadline - time.monotonic() < 80
            or owned_bytes(self.store, record) + 10485760
            > snapshot.budget.maxArtifactBytes
        ):
            return self.stop(
                record,
                Status.UNRESOLVED,
                "budget_exhausted",
                "The experiment budget was reached.",
            )
        reservation = record.reservation
        if reservation is None or reservation.state != "reserved":
            raise EvidenceIntegrity()
        if snapshot.status == Status.PROBING:
            _, _, data = verify_selection(self.repository, record)
        else:
            data = read_reference(self.store.root, record.inputRef)
        if digest_bytes(data) != reservation.inputSha256:
            raise EvidenceIntegrity()
        started = reservation.model_copy(update={"state": "started"})
        active = self.store.commit(
            job_id,
            "phase.started",
            "Reproducing the difference"
            if snapshot.status == Status.REPRODUCING
            else "Running an experiment",
            update={"record": {"reservation": started.model_dump()}},
            expected_reservation=reservation,
        )
        if active.snapshot.status in TERMINAL:
            return active
        _report, _, code = run_case(
            data,
            read_case(data),
            snapshot.pairId,
            self.store.root,
            reserved_id=reservation.childId,
            admission_deadline=deadline,
            runtime_existing=reservation.childId == job_id,
        )
        if code:
            self.clean_or_fail(active)
            stopped = self.stop(
                active,
                Status.FAILED,
                "execution_failure",
                "We couldn't complete the paired comparison. Collected evidence is preserved.",
            )
            if code == 130:
                raise KeyboardInterrupt()
            return stopped
        return self.complete_execution(active)

    def complete_execution(self, record):
        job_id = record.snapshot.id
        if record.snapshot.status == Status.REPRODUCING:
            phase, report, originals = seed_phase(self.repository, record)
            changes = {
                "seedEvidenceId": job_id,
                "evidence": [*originals, *phase.artifacts],
                "record": {"reservation": None},
            }
            if not report.divergence:
                changes.update(
                    terminalReason={
                        "code": "not_reproduced",
                        "message": "No difference observed for this case and engine pair.",
                    }
                )
            return self.store.commit(
                job_id,
                "divergence.detected"
                if report.divergence
                else "investigation.not_reproduced",
                "Difference observed. Choosing an experiment."
                if report.divergence
                else "No difference observed for this case and engine pair.",
                status=Status.PLANNING if report.divergence else Status.NOT_REPRODUCED,
                update=changes,
                phase=phase,
                outputs=phase.artifacts,
            )
        store, plan, _data = verify_selection(self.repository, record)
        from .planner_models import ExecutionJournal

        journal = store.journal()
        if journal is None:
            journal = ExecutionJournal(
                selection_id=plan.selection_id,
                child_evidence_id=record.reservation.childId,
                state="started",
                reserved_at=record.reservation.reservedAt,
                started_at=record.reservation.reservedAt,
            )
            store.advance(journal)
        _, seed_report, _, _, _ = load_evidence(self.store.root, job_id)
        result, phase = reconcile_result(self.repository, store, plan, seed_report)
        if result is None:
            raise EvidenceIntegrity()
        return self.store.commit(
            job_id,
            "graph.write",
            {
                "preserved": "Difference preserved",
                "eliminated": "No difference observed",
                "changed": "Difference changed",
            }[result.relationship],
            status=Status.PLANNING,
            update={
                "evidence": [*record.snapshot.evidence, *phase.artifacts],
                "record": {"reservation": None},
                "budget": record.snapshot.budget.model_copy(
                    update={"chargedBytes": owned_bytes(self.store, record)}
                ).model_dump(),
            },
            phase=phase,
            outputs=phase.artifacts,
        )

    def tick(self):
        pending = self.store.pending()
        if not pending:
            return False
        active = next(
            (
                identity
                for identity in pending
                if self.store.load(identity, verify_outputs=False).snapshot.status
                != Status.QUEUED
            ),
            pending[0],
        )
        try:
            self.step(active)
        except ContextUnavailable:
            raise
        except (EvidenceIntegrity, ValueError, OSError):
            record = self.store.load(active, verify_outputs=False)
            self.clean_or_fail(record)
            self.stop(
                record,
                Status.FAILED,
                "integrity_failure",
                "Saved evidence could not be verified. Preserve this investigation and start a new one when ready.",
            )
        return True


def main():
    signal.signal(signal.SIGTERM, interrupt)
    repository = GraphRepository()
    try:
        with WorkerPresence(repository.config) as presence:
            repository.ensure_schema()
            with closing(docker_client()) as client:
                for pair in PAIRS:
                    verify_images(client, engines_for(pair.id))
            worker = Worker(repository)
            worker.cleanup()
            presence.ready = True
            while True:
                try:
                    if not presence.thread.is_alive():
                        raise ContextError("Worker readiness could not be saved.")
                    worker.tick()
                    presence.ready = True
                    time.sleep(0.25)
                except ContextUnavailable:
                    presence.ready = False
                    repository.close()
                    time.sleep(2)
    except KeyboardInterrupt:
        return 0
    except (ContextError, DockerException, OSError, ValueError):
        print(
            "Investigation worker could not start or continue safely. Check context, approved engines, evidence storage, and targeted cleanup.",
            file=sys.stderr,
        )
        return 1
    finally:
        repository.close()


if __name__ == "__main__":
    sys.exit(main())
