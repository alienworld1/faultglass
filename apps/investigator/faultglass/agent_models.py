from typing import Literal

from pydantic import Field, field_validator, model_validator

from .context_models import EvidenceReference, evidence_id, validate_timestamp
from .models import Contract, Hash
from .provider_budget import CALL_SECONDS, MAX_CALLS, TOTAL_MILLISECONDS


class CitedText(Contract):
    text: str = Field(min_length=1, max_length=240)
    evidenceIds: list[str] = Field(min_length=1, max_length=1)


class FingerprintEnrichment(Contract):
    observed: CitedText
    interpretation: CitedText
    unknown: CitedText


class FamilyExplanation(Contract):
    proposedName: str = Field(min_length=1, max_length=160)
    observed: CitedText
    interpretation: CitedText
    unknown: CitedText


class InvestigationNarrative(Contract):
    observed: CitedText
    interpretation: CitedText
    unknown: CitedText


class ReductionSuggestion(Contract):
    query: str = Field(min_length=1, max_length=16384)
    reason: CitedText


ToolName = Literal[
    "read_investigation_context",
    "rank_supported_probes",
    "execute_ranked_probe",
    "read_probe_evidence",
    "continue_verified_analysis",
    "read_classification_evidence",
]


class AgentToolRequest(Contract):
    tool: ToolName
    investigationId: str
    revision: int = Field(ge=1)
    decisionId: Hash | None
    explanation: CitedText
    enrichment: FingerprintEnrichment | None

    _id = field_validator("investigationId")(evidence_id)


class AgentToolResult(Contract):
    requestId: Hash
    tool: ToolName
    references: list[EvidenceReference] = Field(max_length=12)
    resultHash: Hash


class AgentTurn(Contract):
    id: Hash
    revision: int = Field(ge=1)
    operation: Literal[
        "request_tool",
        "explain_family",
        "narrate_investigation",
        "enrich_fingerprint",
        "suggest_reduction",
    ]
    inputHash: Hash
    inputRef: EvidenceReference | None = None
    reservedAt: str
    responseRef: EvidenceReference | None = None
    providerResponseRef: EvidenceReference | None = None
    failure: str | None = None
    elapsedMs: float = Field(default=0, ge=0, le=CALL_SECONDS * 1000)

    _time = field_validator("reservedAt")(validate_timestamp)


class AgentRun(Contract):
    investigationId: str
    mode: Literal["agent", "deterministic_diagnostic"]
    status: Literal["pending", "running", "completed", "degraded", "data_excluded"]
    reasonCode: str | None = None
    provider: Literal["gemini"] | None = None
    model: str | None = Field(default=None, max_length=160)
    promptVersion: Literal["explorer-v1", "explorer-v2"] = "explorer-v2"
    schemaVersion: Literal[1] = 1
    createdAt: str
    updatedAt: str
    calls: int = Field(default=0, ge=0, le=MAX_CALLS)
    elapsedMs: float = Field(default=0, ge=0, le=TOTAL_MILLISECONDS)
    inputArtifactHashes: list[Hash] = Field(default_factory=list, max_length=80)
    turns: list[AgentTurn] = Field(default_factory=list, max_length=MAX_CALLS)
    results: list[AgentToolResult] = Field(default_factory=list, max_length=MAX_CALLS)
    outputRefs: list[EvidenceReference] = Field(default_factory=list, max_length=4)
    stage: Literal[
        "context",
        "rank",
        "execute",
        "evidence",
        "continue",
        "classification",
        "interpretation",
        "done",
    ] = "context"

    _id = field_validator("investigationId")(evidence_id)
    _created = field_validator("createdAt")(validate_timestamp)
    _updated = field_validator("updatedAt")(validate_timestamp)

    @model_validator(mode="after")
    def counts(self):
        if self.calls != len(self.turns) or (
            self.calls and (not self.provider or not self.model)
        ):
            raise ValueError("The AI investigation receipt does not agree.")
        turns = {turn.id for turn in self.turns}
        results = {result.requestId for result in self.results}
        if (
            len(turns) != len(self.turns)
            or len(results) != len(self.results)
            or results - turns
        ):
            raise ValueError("The AI tool receipt identities do not agree.")
        if abs(sum(turn.elapsedMs for turn in self.turns) - self.elapsedMs) > 1e-6:
            raise ValueError("The AI time budget does not agree.")
        if self.status == "completed" and not (
            self.mode == "agent"
            and self.stage == "done"
            and len(self.outputRefs) >= 2
            and all(t.responseRef for t in self.turns)
            and (
                self.promptVersion == "explorer-v1"
                or all(t.inputRef and t.providerResponseRef for t in self.turns)
            )
        ):
            raise ValueError(
                "A completed AI investigation requires validated cited outputs."
            )
        if self.status in {"degraded", "data_excluded"} and not self.reasonCode:
            raise ValueError("Unavailable AI investigation requires a saved reason.")
        return self


class AgentInterpretation(Contract):
    family: FamilyExplanation
    narrative: InvestigationNarrative


class AgentSummary(Contract):
    mode: Literal["agent", "deterministic_diagnostic"]
    status: Literal["pending", "running", "completed", "degraded", "data_excluded"]
    reasonCode: str | None
    model: str | None
    calls: int = Field(ge=0, le=12)
