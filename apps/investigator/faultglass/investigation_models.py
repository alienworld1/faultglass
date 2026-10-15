from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .context_models import EvidenceReference, evidence_id, validate_timestamp
from .models import Contract, EngineSpec, Hash


class Status(StrEnum):
    QUEUED = "QUEUED"
    FINGERPRINTING = "FINGERPRINTING"
    REPRODUCING = "REPRODUCING"
    PLANNING = "PLANNING"
    PROBING = "PROBING"
    REDUCING = "REDUCING"
    CLASSIFYING = "CLASSIFYING"
    EXPORTING = "EXPORTING"
    COMPLETE = "COMPLETE"
    NOT_REPRODUCED = "NOT_REPRODUCED"
    UNRESOLVED = "UNRESOLVED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


RuntimeStatus = Annotated[Status, BeforeValidator(lambda value: Status(value))]


TERMINAL = frozenset(
    {
        Status.COMPLETE,
        Status.NOT_REPRODUCED,
        Status.UNRESOLVED,
        Status.CANCELLED,
        Status.FAILED,
    }
)
NEXT = {
    Status.QUEUED: {Status.FINGERPRINTING},
    Status.FINGERPRINTING: {Status.REPRODUCING},
    Status.REPRODUCING: {Status.PLANNING, Status.NOT_REPRODUCED},
    Status.PLANNING: {Status.PROBING},
    Status.PROBING: {Status.PLANNING, Status.REDUCING},
    Status.REDUCING: {Status.CLASSIFYING},
    Status.CLASSIFYING: {Status.EXPORTING},
    Status.EXPORTING: {Status.COMPLETE},
}


def transition(before, after, *, downstream=False):
    if before in TERMINAL or (
        after not in NEXT.get(before, set())
        and after not in {Status.FAILED, Status.CANCELLED, Status.UNRESOLVED}
    ):
        raise ValueError("This investigation cannot change to that action.")
    if (
        after
        in {Status.REDUCING, Status.CLASSIFYING, Status.EXPORTING, Status.COMPLETE}
        and not downstream
    ):
        raise ValueError("Further analysis is unavailable.")


class Admission(Contract):
    caseFile: str = Field(max_length=262144)
    pairId: str = Field(min_length=1, max_length=160)


class RuntimeContract(Contract):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Budget(RuntimeContract):
    maxProbes: Literal[4] = 4
    maxSeconds: Literal[900] = 900
    maxArtifactBytes: Literal[67108864] = 67108864
    maxEvents: Literal[512] = 512
    reducerCandidates: Literal[0] = 0
    reservedProbes: int = Field(default=0, ge=0, le=4)
    chargedBytes: int = Field(default=0, ge=0, le=67108864)


class Capabilities(RuntimeContract):
    reducing: Literal[False] = False
    classifying: Literal[False] = False
    exporting: Literal[False] = False


class Reason(Contract):
    code: Literal[
        "no_applicable_probe",
        "budget_exhausted",
        "analysis_unavailable",
        "not_reproduced",
        "cancelled",
        "recovery_required",
        "integrity_failure",
        "execution_failure",
        "storage_failure",
        "cleanup_required",
        "registry_changed",
    ]
    message: str = Field(min_length=1, max_length=256)


class Snapshot(RuntimeContract):
    schemaVersion: Literal[1] = 1
    id: str
    workspaceId: Literal["falkordb-core"] = "falkordb-core"
    title: str = Field(min_length=1, max_length=160)
    pairId: str
    engines: list[EngineSpec] = Field(min_length=2, max_length=2)
    status: RuntimeStatus = Status.QUEUED
    revision: int = Field(default=1, ge=1)
    createdAt: str
    updatedAt: str
    startedAt: str | None = None
    finishedAt: str | None = None
    deadlineAt: str
    phase: RuntimeStatus = Status.QUEUED
    phaseAttempt: int = Field(default=0, ge=0)
    fingerprintId: Hash | None = None
    seedEvidenceId: str | None = None
    probeSequence: int = Field(default=0, ge=0, le=4)
    cancelRequestedAt: str | None = None
    budget: Budget = Field(default_factory=Budget)
    terminalReason: Reason | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=80)
    lastEventSequence: int = Field(default=1, ge=0, le=512)
    capabilities: Capabilities = Field(default_factory=Capabilities)

    _id = field_validator("id")(evidence_id)

    @model_validator(mode="after")
    def coherent(self):
        for value in (
            self.createdAt,
            self.updatedAt,
            self.startedAt,
            self.finishedAt,
            self.deadlineAt,
            self.cancelRequestedAt,
        ):
            if value is not None:
                validate_timestamp(value)
        if (self.status in TERMINAL) != (
            self.terminalReason is not None and self.finishedAt is not None
        ):
            raise ValueError("A finished investigation requires a stopping reason.")
        return self


EventType = Literal[
    "investigation.created",
    "phase.started",
    "fingerprint.completed",
    "graph.read",
    "probe.candidates",
    "probe.selected",
    "engine.observed",
    "divergence.detected",
    "graph.write",
    "cancellation.requested",
    "investigation.not_reproduced",
    "investigation.unresolved",
    "investigation.cancelled",
    "investigation.failed",
]


class EventData(Contract):
    revision: int = Field(ge=1)
    status: RuntimeStatus
    probeSequence: int = Field(ge=0, le=4)
    childId: str | None = None
    references: list[EvidenceReference] = Field(default_factory=list, max_length=3)


class Event(Contract):
    id: str
    investigationId: str
    sequence: int = Field(ge=1, le=512)
    type: EventType
    at: str
    phase: RuntimeStatus
    summary: str = Field(min_length=1, max_length=256)
    data: EventData

    @model_validator(mode="after")
    def identity(self):
        evidence_id(self.investigationId)
        validate_timestamp(self.at)
        if self.id != f"{self.investigationId}:{self.sequence}":
            raise ValueError("The event identity does not agree.")
        return self


class Reservation(Contract):
    key: Hash
    childId: str
    inputSha256: Hash
    state: Literal["reserved", "started", "evidence_complete", "incomplete"]
    sequence: int = Field(ge=0, le=4)
    reservedAt: str

    _id = field_validator("childId")(evidence_id)


class PhaseReceipt(Contract):
    key: Hash
    payloadSha256: Hash
    handlerVersion: Literal["runtime-v1"] = "runtime-v1"
    sequence: int = Field(ge=0, le=4)
    attempt: int = Field(ge=1)
    previous: EvidenceReference | None
    inputs: list[EvidenceReference] = Field(max_length=4)
    outputs: list[EvidenceReference] = Field(max_length=10)


class RuntimeRecord(Contract):
    snapshot: Snapshot
    admissionKey: str
    payloadSha256: Hash
    inputRef: EvidenceReference
    previous: EvidenceReference | None = None
    event: Event
    workerId: str | None = None
    reservation: Reservation | None = None
    triedOutputs: list[Hash] = Field(default_factory=list, max_length=4)
    receiptKey: Hash
    phaseReceipt: PhaseReceipt | None = None
    outputs: list[EvidenceReference] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def agrees(self):
        snapshot = self.snapshot
        evidence_id(self.admissionKey)
        if self.workerId is not None:
            evidence_id(self.workerId)
        if (
            self.event.investigationId != snapshot.id
            or self.event.sequence != snapshot.lastEventSequence
            or self.event.data.revision != snapshot.revision
            or self.event.data.status != snapshot.status
            or snapshot.phase != snapshot.status
            or self.inputRef.owner != snapshot.id + "/runtime"
            or self.inputRef.path != "input.json"
            or (
                self.previous is not None
                and self.previous.owner != snapshot.id + "/runtime"
            )
            or len(set(self.triedOutputs)) != len(self.triedOutputs)
            or len(self.triedOutputs) != snapshot.budget.reservedProbes
            or (
                self.reservation is not None
                and self.reservation.sequence != snapshot.probeSequence
            )
        ):
            raise ValueError("Saved investigation control and evidence do not agree.")
        return self


class ObservationSummary(Contract):
    engineVersionId: str
    status: Literal["result", "error", "timeout", "crash"]
    rowCount: int | None
    columns: list[str] = Field(max_length=32)
    errorCategory: str | None
    detail: str | None = Field(max_length=256)


class PairedSummary(Contract):
    baseline: ObservationSummary
    target: ObservationSummary


class EvidenceItem(Contract):
    sequence: int = Field(ge=0, le=4)
    kind: Literal["seed", "selection", "result"]
    references: list[EvidenceReference] = Field(max_length=10)
    decision: str | None = Field(default=None, max_length=131072)
    observations: PairedSummary | None = None
    query: str | None = Field(default=None, max_length=16384)


class EvidencePage(Contract):
    revision: int
    items: list[EvidenceItem] = Field(max_length=25)
    nextCursor: int | None
