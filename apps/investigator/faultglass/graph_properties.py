from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from .models import Contract, Hash

Text = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
Short = Annotated[str, StringConstraints(min_length=1, max_length=160)]
Timestamp = Text


class BaseProperties(Contract):
    id: Text
    created_at: Timestamp

    @model_validator(mode="after")
    def timestamps(self):
        from .context_models import validate_timestamp

        for name, value in self.model_dump().items():
            if name.endswith("_at") and value is not None:
                validate_timestamp(value)
        return self

    @field_validator("created_at")
    @classmethod
    def utc(cls, value):
        from .context_models import validate_timestamp

        return validate_timestamp(value)


class EngineProperties(BaseProperties):
    id: Hash
    repository: Literal["FalkorDB/FalkorDB"]
    commit_sha: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{40}$")]
    image_digest: Annotated[str, StringConstraints(pattern=r"^sha256:[a-f0-9]{64}$")]
    image_ref: Text
    lineage: Literal["legacy-c", "rust"]
    catalog_id: Short

    @model_validator(mode="after")
    def immutable_image(self):
        if not self.image_ref.endswith("@" + self.image_digest):
            raise ValueError("Use the approved immutable image reference.")
        return self


class InvestigationProperties(BaseProperties):
    workspace_id: Literal["falkordb-core"]
    status: Literal["REPRODUCED", "NOT_REPRODUCED"]
    updated_at: Timestamp
    fault_case_id: Hash
    fingerprint_version: Literal["fingerprint-v1"]
    canonicalization_version: Literal["case-v1"]
    context_schema_version: Literal["context-v1"]
    seed_evidence_id: Short
    raw_case_sha256: Hash
    report_artifact_ref: Text
    context_phase_key: Hash
    context_payload_sha256: Hash | None = None
    context_recorded_at: Timestamp | None = None
    terminal_reason: Text | None = None
    selection_phase_key: Hash | None = None
    selection_payload_sha256: Hash | None = None
    selection_committed_at: Timestamp | None = None
    selection_artifact_ref: Text | None = None
    observation_phase_key: Hash | None = None
    observation_payload_sha256: Hash | None = None
    observation_committed_at: Timestamp | None = None
    observation_artifact_ref: Text | None = None


class CaseProperties(BaseProperties):
    id: Hash
    schema_version: Literal[1]
    canonicalization_version: Literal["case-v1"]
    content_sha256: Hash
    setup_sha256: Hash
    query_sha256: Hash
    artifact_ref: Text
    title: Short


class FingerprintProperties(BaseProperties):
    id: Hash
    version: Literal["fingerprint-v1"]
    shape_hash: Hash
    clause_signature: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    analysis_support: Literal["supported", "conservative"]
    artifact_ref: Text


class FeatureProperties(BaseProperties):
    label: Short
    description: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    catalog_version: Literal["features-v1"]


class RunProperties(BaseProperties):
    probe_id: Short | None = None
    child_evidence_id: Short | None = None
    investigation_id: Short
    role: Literal["baseline", "target"]
    status: Literal["result", "error", "timeout", "crash"]
    started_at: Timestamp
    finished_at: Timestamp
    timing_basis: Literal["paired_bounds"]
    duration_ms: Annotated[float, Field(ge=0)]
    observation_sha256: Hash
    artifact_ref: Text


class DivergenceProperties(BaseProperties):
    investigation_id: Short
    signature: Hash
    kind: Literal["status", "error", "result", "postcondition", "mixed"]
    stable: Literal[False]
    comparison_version: Text
    artifact_ref: Text


class ProbeProperties(BaseProperties):
    definition_sha256: Hash | None = None
    type: Short
    template_version: Short
    description: Text
    cost_class: Short
    enabled: bool


class FamilyProperties(BaseProperties):
    slug: Short
    name: Short
    status: Literal["provisional", "confirmed", "superseded"]
    updated_at: Timestamp
    superseded_by_id: Short | None = None

    @model_validator(mode="after")
    def supersession(self):
        if (self.status == "superseded") != (self.superseded_by_id is not None):
            raise ValueError("A superseded family requires its replacement identity.")
        return self


class RegressionProperties(BaseProperties):
    investigation_id: Short
    case_sha256: Hash
    pytest_sha256: Hash
    case_artifact_ref: Text
    pytest_artifact_ref: Text


PROPERTY_MODELS = {
    "EngineVersion": EngineProperties,
    "Investigation": InvestigationProperties,
    "FaultCase": CaseProperties,
    "Fingerprint": FingerprintProperties,
    "Feature": FeatureProperties,
    "Run": RunProperties,
    "Divergence": DivergenceProperties,
    "Probe": ProbeProperties,
    "FaultFamily": FamilyProperties,
    "RegressionTest": RegressionProperties,
}
