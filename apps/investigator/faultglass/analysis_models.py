from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from .agent_models import AgentInterpretation, AgentRun
from .context_models import (
    EvidenceReference,
    VersionScope,
    evidence_id,
    validate_timestamp,
)
from .feature_catalog import FEATURE_IDS
from .models import ArtifactRef, Contract, Hash

Text = Annotated[str, StringConstraints(min_length=1, max_length=1200)]
Score = Annotated[float, Field(ge=0, le=1)]


class DownloadReference(ArtifactRef):
    owner: str
    key: Literal["case", "regression-test", "report"]

    @model_validator(mode="after")
    def safe(self):
        import re

        job_id, separator, area = self.owner.partition("/")
        evidence_id(job_id)
        types = {
            "case": ("application/json", ".faultglass.json"),
            "regression-test": ("text/x-python", "_regression_test.py"),
            "report": ("text/markdown", ".md"),
        }
        media, suffix = types[self.key]
        if (
            not separator
            or area != "export"
            or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,100}", self.path)
            or not self.path.endswith(suffix)
            or self.mediaType != media
            or self.bytes > 262144
        ):
            raise ValueError("Use a verified investigation download.")
        from .jsonio import encode

        if (
            len(encode(self.model_dump())) > 2048
            or len(self.id) > 160
            or len(self.kind) > 160
        ):
            raise ValueError("Use a bounded investigation download reference.")
        if self.key == "report" and self.path != "report.md":
            raise ValueError("Use the saved evidence report.")
        return self


class ProbeEvidence(Contract):
    selectionId: Hash
    sequence: int = Field(ge=1, le=4)
    probeId: str = Field(max_length=160)
    templateVersion: str = Field(max_length=160)
    definitionSha256: Hash
    inputCaseId: Hash
    outputCaseId: Hash
    relationship: Literal["preserved", "eliminated", "changed"]
    signature: Hash | None
    pairedStatuses: dict[
        Literal["baseline", "target"], Literal["result", "error", "timeout", "crash"]
    ]
    durationMs: float = Field(ge=0)
    observedAt: str
    planRef: EvidenceReference
    resultRef: EvidenceReference
    reportRef: EvidenceReference
    contribution: Literal["repeated_source", "semantic_contrast"] | None = None

    _time = field_validator("observedAt")(validate_timestamp)


class FamilyProfile(Contract):
    investigationId: str
    scope: VersionScope
    features: list[str] = Field(max_length=64)
    reducedShape: Hash
    sourceKind: str = Field(max_length=40)
    sourceStatuses: list[Literal["result", "error", "timeout", "crash"]] = Field(
        min_length=2, max_length=2
    )
    probes: list[ProbeEvidence] = Field(max_length=4)

    _id = field_validator("investigationId")(evidence_id)

    @field_validator("features")
    @classmethod
    def controlled_features(cls, value):
        if value != sorted(set(value)) or set(value) - set(FEATURE_IDS):
            raise ValueError("Use sorted controlled behavioral features.")
        return value


class FamilyCandidate(Contract):
    familyId: str = Field(max_length=160)
    familyStatus: Literal["provisional", "confirmed"]
    familyEvidenceRef: EvidenceReference
    sourceInvestigationId: str
    pathRefs: list[str] = Field(max_length=64)
    feature: Score
    behavior: Score
    reducedShape: Score
    version: Score
    score: Score
    compatible: bool
    eligible: bool
    supportingProbeIds: list[str] = Field(max_length=4)
    contradictoryProbeIds: list[str] = Field(max_length=4)
    reasons: list[str] = Field(max_length=12)


class ClassificationEvidence(Contract):
    schemaVersion: Literal[1] = 1
    classifierVersion: Literal["family-evidence-v1"] = "family-evidence-v1"
    investigationId: str
    seedCaseId: Hash
    fingerprintId: Hash
    retainedCaseId: Hash
    referenceSignature: Hash
    profile: FamilyProfile
    sourceRef: EvidenceReference
    stabilityRef: EvidenceReference
    retainedCaseRef: EvidenceReference
    retainedVerificationRef: EvidenceReference
    candidates: list[FamilyCandidate] = Field(max_length=100)
    unknowns: list[Text] = Field(max_length=12)
    contradictions: list[Text] = Field(max_length=12)
    createdAt: str

    _time = field_validator("createdAt")(validate_timestamp)
    _id = field_validator("investigationId")(evidence_id)


class Conclusion(Contract):
    state: Literal["matched", "provisional", "unresolved"]
    familyId: str | None = None
    familyStatus: Literal["provisional", "confirmed"] | None = None
    familyName: str | None = Field(default=None, max_length=160)
    evidenceRef: EvidenceReference
    interpretationRef: EvidenceReference | None = None
    observed: list[Text] = Field(max_length=12)
    unknowns: list[Text] = Field(max_length=12)
    reasonCode: str = Field(max_length=80)
    createdAt: str

    @model_validator(mode="after")
    def family(self):
        if (self.state == "unresolved") != (self.familyId is None) or (
            self.familyId is None
        ) != (self.familyStatus is None):
            raise ValueError("The behavioral family outcome does not agree.")
        return self


class ExportManifest(Contract):
    schemaVersion: Literal[1] = 1
    investigationId: str
    regressionTestId: str
    sourceCaseId: Hash
    classificationEvidenceRef: EvidenceReference
    files: list[DownloadReference] = Field(min_length=3, max_length=3)
    expectationBasis: Literal[
        "explicit_result", "explicit_error", "baseline_observation", "unasserted"
    ]
    createdAt: str

    @model_validator(mode="after")
    def files_agree(self):
        evidence_id(self.investigationId)
        evidence_id(self.regressionTestId)
        if {f.key for f in self.files} != {"case", "regression-test", "report"} or any(
            f.owner != self.investigationId + "/export" for f in self.files
        ):
            raise ValueError("The export bundle does not agree.")
        return self


class MemoryStatistics(Contract):
    attempts: int = Field(ge=0)
    successes: int = Field(ge=0)
    avgCostMs: float = Field(ge=0)
    lastSeenAt: str

    @model_validator(mode="after")
    def counts(self):
        validate_timestamp(self.lastSeenAt)
        if self.successes > self.attempts:
            raise ValueError("Investigation memory could not be verified.")
        return self


class MemoryEntry(Contract):
    edgeId: Hash
    probeId: str
    familyId: str
    selectionId: Hash
    evidenceRefs: list[EvidenceReference] = Field(max_length=4)
    successIncrement: Literal[0, 1]
    reason: Literal["repeated_source", "semantic_contrast", "observed_only"]
    costMs: float = Field(ge=0)
    before: MemoryStatistics
    after: MemoryStatistics


class MemoryDelta(Contract):
    costPrecision: Literal["milliseconds-6dp"] = "milliseconds-6dp"
    schemaVersion: Literal[1] = 1
    investigationId: str
    commitKey: Hash
    classificationRef: EvidenceReference
    exportManifestRef: EvidenceReference
    scope: VersionScope
    entries: list[MemoryEntry] = Field(max_length=4)
    state: Literal["recorded", "ineligible"]
    reason: str | None = None


class InfluenceRank(Contract):
    probeId: str
    rank: int = Field(ge=1, le=2)
    score: float


class HistoricalInfluence(Contract):
    decisionRef: EvidenceReference
    selectedProbeId: str | None
    priorInvestigationIds: list[str] = Field(max_length=100)
    pathRefs: list[str] = Field(max_length=256)
    withoutHistory: list[InfluenceRank] = Field(max_length=2)
    withHistory: list[InfluenceRank] = Field(max_length=2)
    changed: bool


class ClassificationSummary(Contract):
    features: list[str] = Field(max_length=64)
    scope: VersionScope
    referenceSignature: Hash
    retainedCaseId: Hash
    retainedIsRepeatedSource: bool
    sourceRef: EvidenceReference
    stabilityRef: EvidenceReference
    retainedVerificationRef: EvidenceReference
    probes: list[ProbeEvidence] = Field(max_length=4)
    contradictions: list[Text] = Field(max_length=12)


class ConclusionPage(Contract):
    revision: int
    conclusion: Conclusion | None
    classification: ClassificationSummary | None
    exports: ExportManifest | None
    memory: MemoryDelta | None
    influence: HistoricalInfluence | None
    candidates: list[FamilyCandidate] = Field(max_length=10)
    nextCursor: int | None
    agent: "AgentRun | None"
    interpretation: "AgentInterpretation | None"


ConclusionPage.model_rebuild()
