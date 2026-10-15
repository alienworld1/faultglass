from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .context_models import (
    Edge,
    EvidenceReference,
    FingerprintRecord,
    HistoryCandidate,
    VersionScope,
    evidence_id,
    validate_timestamp,
)
from .graph_properties import Short, Text
from .models import Contract, Hash, RunLimits
from .probe_registry import ProbeDefinition
from .probe_transforms import SourceEdit

Factor = Annotated[float, Field(ge=0, le=1)]


class CatalogProbe(Contract):
    definition: ProbeDefinition
    enabled: bool
    targets: list[Edge] = Field(min_length=1, max_length=24)


def known_features(value):
    return FingerprintRecord.controlled(value)


class SourceSnapshot(Contract):
    catalog: list[CatalogProbe] = Field(max_length=2)
    history: list[HistoryCandidate] = Field(max_length=100)
    feature_ids: list[str] = Field(max_length=24)
    scope: VersionScope
    lineages: list[Literal["legacy-c", "rust"]] = Field(min_length=2, max_length=2)

    _features = field_validator("feature_ids")(known_features)


class Rejection(Contract):
    input_case_id: Hash
    applicable: Literal[False] = False
    output_case_id: None = None
    transformed_case_ref: None = None
    probe_id: Short
    reason_code: Literal[
        "unsupported_shape",
        "unmet_precondition",
        "disabled",
        "invalid_output",
        "unchanged_output",
        "duplicate_output",
        "unknown_definition",
        "incompatible_scope",
    ]
    history_key: Text | None = None


class ProbeEligibility(Contract):
    probe_id: Short
    applicable: bool
    reason_code: Literal[
        "applicable",
        "unsupported_shape",
        "unmet_precondition",
        "disabled",
        "invalid_output",
        "unchanged_output",
    ]
    input_case_id: Hash
    output_case_id: Hash | None = None
    transformed_case_ref: EvidenceReference | None = None

    @model_validator(mode="after")
    def output(self):
        if self.applicable:
            if (
                self.reason_code != "applicable"
                or self.output_case_id is None
                or self.transformed_case_ref is None
                or self.output_case_id == self.input_case_id
            ):
                raise ValueError(
                    "An applicable experiment requires a verified changed case."
                )
        elif (
            self.reason_code == "applicable"
            or self.output_case_id is not None
            or self.transformed_case_ref is not None
        ):
            raise ValueError(
                "An ineligible experiment cannot supply an executable case."
            )
        return self


class RankedCandidate(Contract):
    eligibility: ProbeEligibility
    probe_id: Short
    template_version: Short
    definition_sha256: Hash
    input_case_id: Hash
    output_case_id: Hash
    target_feature_ids: list[str]
    matched_feature_ids: list[str]
    source: Literal["history", "structural"]
    chosen_history_key: Text | None
    attempts: Annotated[int, Field(ge=0)]
    successes: Annotated[int, Field(ge=0)]
    avg_cost_ms: Annotated[float, Field(ge=0)]
    cost_class: Literal["small", "medium", "large"]
    reason: Text
    pair_cap_ms: Literal[60000] = 60000
    feature_fit: Factor
    historical_yield: Factor
    version_affinity: Factor
    novelty: Factor
    normalized_cost: Factor
    utility: float
    rank: Annotated[int, Field(ge=1)]
    edit: SourceEdit
    transformed_case_ref: EvidenceReference

    _features = field_validator("target_feature_ids", "matched_feature_ids")(
        known_features
    )

    @model_validator(mode="after")
    def score(self):
        expected = (
            0.35 * self.feature_fit
            + 0.30 * self.historical_yield
            + 0.20 * self.version_affinity
            + 0.10 * self.novelty
            - 0.05 * self.normalized_cost
        )
        if (
            not self.target_feature_ids
            or not self.eligibility.applicable
            or self.eligibility.probe_id != self.probe_id
            or self.eligibility.input_case_id != self.input_case_id
            or self.eligibility.output_case_id != self.output_case_id
            or self.eligibility.transformed_case_ref != self.transformed_case_ref
            or self.utility != expected
            or self.successes > self.attempts
            or (self.source == "history") != (self.chosen_history_key is not None)
        ):
            raise ValueError("Saved score inputs do not agree.")
        return self


class Decision(Contract):
    selection_id: Hash
    investigation_id: str
    sequence: Annotated[int, Field(ge=1, le=4)] = 1
    planner_version: Literal["planner-v1"] = "planner-v1"
    registry_sha256: Hash
    seed_case_id: Hash
    fingerprint_id: Hash
    seed_manifest_sha256: Hash
    scope: VersionScope
    created_at: str
    novel: bool
    candidates: list[RankedCandidate] = Field(max_length=2)
    rejections: list[Rejection] = Field(max_length=202)
    selected_probe_id: Short | None
    outcome: Literal["selected", "not_reproduced", "unresolved"]
    terminal_reason: Literal["no_applicable_probe", "budget_exhausted"] | None = None
    limits: RunLimits
    admission_seconds: Annotated[int, Field(ge=1, le=120)] = 120
    source_snapshot_ref: EvidenceReference
    transformed_case_ref: EvidenceReference | None

    _id = field_validator("investigation_id")(evidence_id)
    _time = field_validator("created_at")(validate_timestamp)

    @model_validator(mode="after")
    def selected(self):
        owner = self.investigation_id + "/planning"
        if self.source_snapshot_ref.owner.endswith(f"/planning/{self.sequence}"):
            owner += f"/{self.sequence}"
        if self.source_snapshot_ref.owner != owner or any(
            c.input_case_id != self.seed_case_id
            or c.transformed_case_ref.owner != owner
            for c in self.candidates
        ):
            raise ValueError("Saved experiment evidence belongs to another case.")
        if self.novel != (not any(c.source == "history" for c in self.candidates)):
            raise ValueError("Saved novelty does not match the related evidence.")
        if [c.rank for c in self.candidates] != list(
            range(1, len(self.candidates) + 1)
        ):
            raise ValueError("Saved ranks do not agree.")
        if self.candidates != sorted(
            self.candidates, key=lambda c: (-c.utility, c.probe_id)
        ):
            raise ValueError("Saved ranking is out of order.")
        if self.outcome == "selected":
            if (
                not self.candidates
                or self.selected_probe_id != self.candidates[0].probe_id
                or self.transformed_case_ref != self.candidates[0].transformed_case_ref
                or self.terminal_reason is not None
            ):
                raise ValueError("Saved selection does not agree with its ranking.")
        elif (
            self.selected_probe_id is not None
            or self.transformed_case_ref is not None
            or ((self.outcome == "unresolved") != (self.terminal_reason is not None))
        ):
            raise ValueError("Saved terminal outcome does not agree.")
        return self


class ExecutionJournal(Contract):
    selection_id: Hash
    child_evidence_id: str
    state: Literal["reserved", "started", "evidence_complete", "incomplete"]
    reserved_at: str
    started_at: str | None = None
    finished_at: str | None = None
    failure_code: Short | None = None

    _id = field_validator("child_evidence_id")(evidence_id)

    @model_validator(mode="after")
    def states(self):
        for value in (self.reserved_at, self.started_at, self.finished_at):
            if value is not None:
                validate_timestamp(value)
        if self.state in ("started", "evidence_complete") and not self.started_at:
            raise ValueError("Execution start time is required.")
        if self.state in ("evidence_complete", "incomplete") and not self.finished_at:
            raise ValueError("Execution finish time is required.")
        return self


class ProbeResult(Contract):
    selection_id: Hash
    child_evidence_id: str
    probe_id: Short
    sequence: Annotated[int, Field(ge=1, le=4)] = 1
    input_case_id: Hash
    output_case_id: Hash
    scope: VersionScope
    child_manifest_sha256: Hash
    child_artifacts: list[EvidenceReference] = Field(min_length=6, max_length=6)
    child_signature: Hash | None
    seed_signature: Hash
    relationship: Literal["preserved", "eliminated", "changed"]
    paired_statuses: dict[
        Literal["baseline", "target"], Literal["result", "error", "timeout", "crash"]
    ]
    stable: Literal[False] = False
    paired_run_ids: list[str] = Field(min_length=2, max_length=2)
    started_at: str
    finished_at: str
    duration_ms: Annotated[float, Field(ge=0)]

    _id = field_validator("child_evidence_id")(evidence_id)
    _start = field_validator("started_at")(validate_timestamp)
    _finish = field_validator("finished_at")(validate_timestamp)

    @model_validator(mode="after")
    def observed(self):
        expected = (
            "eliminated"
            if self.child_signature is None
            else (
                "preserved"
                if self.child_signature == self.seed_signature
                else "changed"
            )
        )
        if (
            self.relationship != expected
            or self.finished_at < self.started_at
            or set(self.paired_statuses) != {"baseline", "target"}
            or len(set(self.paired_run_ids)) != 2
        ):
            raise ValueError("Saved experiment observations do not agree.")
        for value in self.paired_run_ids:
            evidence_id(value)
        if any(ref.owner != self.child_evidence_id for ref in self.child_artifacts):
            raise ValueError("Child evidence belongs to another comparison.")
        return self


class CommitReceipt(Contract):
    selection_id: Hash
    phase: Literal["selection", "observation"]
    phase_key: Hash
    payload_sha256: Hash
    committed_at: str
    reused: bool
    artifacts: list[EvidenceReference] = Field(min_length=2, max_length=10)
    child_evidence_id: str | None = None

    _time = field_validator("committed_at")(validate_timestamp)

    @model_validator(mode="after")
    def child(self):
        if (self.phase == "observation") != (self.child_evidence_id is not None):
            raise ValueError("Only observation receipts identify child evidence.")
        if self.child_evidence_id:
            evidence_id(self.child_evidence_id)
        return self
