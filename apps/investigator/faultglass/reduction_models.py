from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .context_models import EvidenceReference, evidence_id, validate_timestamp
from .evidence_summaries import PairedSummary
from .models import Contract, Divergence, EngineSpec, Hash


class ReductionContract(Contract):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class CaseSize(ReductionContract):
    queryTokens: int = Field(ge=0)
    setupStatements: int = Field(ge=0)
    setupTokens: int = Field(ge=0)
    executableBytes: int = Field(ge=0)


class ReductionSource(ReductionContract):
    sourceKind: Literal["seed", "probe"]
    sourceEvidenceId: str
    sourceProbeSequence: int | None = Field(default=None, ge=1, le=4)
    sourceCaseId: Hash
    sourceCaseRef: EvidenceReference
    referenceDivergence: Divergence
    engines: list[EngineSpec] = Field(min_length=2, max_length=2)
    stabilityEvidenceId: str | None = None
    stable: bool = False
    reducerVersion: Literal["reducer-v1"] = "reducer-v1"

    _id = field_validator("sourceEvidenceId")(evidence_id)

    @model_validator(mode="after")
    def scope(self):
        if (self.sourceKind == "probe") != (self.sourceProbeSequence is not None):
            raise ValueError("The reduction source does not agree.")
        if self.stabilityEvidenceId is not None:
            evidence_id(self.stabilityEvidenceId)
        if self.stable and self.stabilityEvidenceId is None:
            raise ValueError("Repeat evidence is required.")
        return self


class ReductionChange(ReductionContract):
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    setupIndex: int | None = Field(default=None, ge=0, le=31)
    originalTextSha256: Hash
    description: str = Field(min_length=1, max_length=160)


class ReductionAttempt(ReductionContract):
    id: Hash
    ordinal: int = Field(ge=1, le=32)
    phase: Literal["query", "fixture"]
    transformId: Literal[
        "remove-with-v1", "remove-optional-v1", "remove-match-v1", "remove-setup-v1"
    ]
    parentCaseId: Hash
    candidateCaseId: Hash | None
    candidatePayloadSha256: Hash
    candidateRef: EvidenceReference
    change: ReductionChange
    beforeSize: CaseSize
    afterSize: CaseSize | None
    state: Literal["proposed", "verifying", "accepted", "rejected", "failed"]
    reason: (
        Literal[
            "invalid_candidate",
            "unsupported_shape",
            "not_smaller",
            "duplicate",
            "difference_eliminated",
            "signature_changed",
            "verified",
            "execution_failure",
            "integrity_failure",
        ]
        | None
    ) = None
    verificationEvidenceId: str | None = None
    observedDivergence: Divergence | None = None
    createdAt: str
    resolvedAt: str | None = None
    artifactRefs: list[EvidenceReference] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def coherent(self):
        validate_timestamp(self.createdAt)
        if self.resolvedAt:
            validate_timestamp(self.resolvedAt)
        if self.verificationEvidenceId:
            evidence_id(self.verificationEvidenceId)
        if self.state == "accepted" and (
            self.reason != "verified"
            or not self.verificationEvidenceId
            or not self.observedDivergence
        ):
            raise ValueError("Accepted changes require complete verification.")
        return self


StopReason = Literal[
    "supported_passes_exhausted",
    "unsupported_shape",
    "candidate_limit",
    "consideration_limit",
    "time_limit",
    "storage_limit",
    "event_limit",
    "unstable_source",
    "cancelled",
    "verification_failed",
]


class ReductionSummary(ReductionContract):
    source: ReductionSource
    state: Literal[
        "checking", "proposing", "verifying", "finished", "cancelled", "failed"
    ]
    originalSize: CaseSize
    sourceSize: CaseSize
    currentSize: CaseSize
    currentCaseId: Hash
    currentCaseRef: EvidenceReference
    acceptedCount: int = Field(default=0, ge=0, le=4)
    rejectedCount: int = Field(default=0, ge=0, le=32)
    verificationFailures: int = Field(default=0, ge=0, le=5)
    consideredCount: int = Field(default=0, ge=0, le=32)
    reservedCandidates: int = Field(default=0, ge=0, le=4)
    stopReason: StopReason | None = None
    finalCaseRef: EvidenceReference | None = None

    @model_validator(mode="after")
    def counts(self):
        if (
            self.acceptedCount > self.reservedCandidates
            or self.acceptedCount + self.rejectedCount + self.verificationFailures
            > self.consideredCount + 1
        ):
            raise ValueError("Reduction counters do not agree.")
        return self


class ReductionCheckpoint(ReductionContract):
    summary: ReductionSummary
    attempts: list[EvidenceReference] = Field(default_factory=list, max_length=32)
    seen: list[Hash] = Field(max_length=33)
    cursor: int = Field(default=0, ge=0, le=35)
    activeAttempt: ReductionAttempt | None = None
    stabilityReserved: bool = False


class ReductionCaseView(ReductionContract):
    caseId: Hash
    query: str = Field(max_length=16384)
    setup: list[str] = Field(max_length=8)
    setupTotal: int = Field(ge=0, le=32)
    nextSetupCursor: int | None
    caseRef: EvidenceReference


class ReductionAttemptView(ReductionContract):
    attempt: ReductionAttempt
    observations: PairedSummary | None = None
    parent: ReductionCaseView | None
    candidate: ReductionCaseView | None


class ReductionPage(ReductionContract):
    revision: int = Field(ge=1)
    summary: ReductionSummary | None
    attempts: list[ReductionAttemptView] = Field(max_length=10)
    nextCursor: int | None
    case: ReductionCaseView | None
    sourceCase: ReductionCaseView | None = None
    sourceObservations: PairedSummary | None = None
    stabilityObservations: PairedSummary | None = None
