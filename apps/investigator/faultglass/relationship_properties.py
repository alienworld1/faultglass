from typing import Annotated, Literal

from pydantic import Field, model_validator

from .graph_properties import Short, Text
from .models import Contract, Hash


class ProvenanceProperties(Contract):
    id: Text
    source_kind: Literal[
        "deterministic_extraction",
        "execution",
        "catalog",
        "verified_classification",
        "deterministic_planning",
    ]
    source_id: Text
    created_at: Text


class FingerprintLinkProperties(ProvenanceProperties):
    fingerprint_version: Literal["fingerprint-v1"]


class ExecutionLinkProperties(ProvenanceProperties):
    sequence: Annotated[int, Field(ge=0)]
    probe_id: Short | None = None
    purpose: Literal["stability", "reduction"] | None = None
    ordinal: Annotated[int, Field(ge=1, le=4)] | None = None


class SelectionProperties(ProvenanceProperties):
    selection_id: Hash | None = None
    planner_version: Short | None = None
    plan_artifact_ref: Text | None = None
    snapshot_artifact_ref: Text | None = None
    sequence: Annotated[int, Field(ge=0)]
    score: float
    reason_code: Short


class ClassificationProperties(ProvenanceProperties):
    status: Literal["provisional", "confirmed", "superseded"]
    evidence_weight: Annotated[float, Field(ge=0)]
    version_scope: Text


class EffectivenessProperties(ProvenanceProperties):
    attempts: Annotated[int, Field(ge=0)]
    successes: Annotated[int, Field(ge=0)]
    avg_cost_ms: Annotated[float, Field(ge=0)]
    last_seen_at: Text
    version_scope: Text

    @model_validator(mode="after")
    def valid_statistics(self):
        if self.successes > self.attempts:
            raise ValueError("Related evidence could not be verified.")
        return self


class ReductionLinkProperties(ProvenanceProperties):
    investigation_id: Short
    attempt_id: Hash
    ordinal: Annotated[int, Field(ge=1, le=32)]
    parent_case_id: Hash
    verification_evidence_id: Short
    reference_signature: Hash


PROPERTY_MODELS = {
    "REDUCED_TO": ReductionLinkProperties,
    "HAS_FINGERPRINT": FingerprintLinkProperties,
    "EXECUTED_AS": ExecutionLinkProperties,
    "SELECTED_PROBE": SelectionProperties,
    "MATCHES_FAMILY": ClassificationProperties,
    "EFFECTIVE_FOR": EffectivenessProperties,
}
