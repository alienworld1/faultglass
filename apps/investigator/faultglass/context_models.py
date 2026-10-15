import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from .feature_catalog import FEATURE_IDS
from .jsonio import encode
from .models import ArtifactRef, Contract, Hash

CONTEXT_SCHEMA_VERSION = "context-v1"
BoundedText = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
NodeLabel = Literal[
    "EngineVersion",
    "Investigation",
    "FaultCase",
    "Fingerprint",
    "Feature",
    "Probe",
    "Run",
    "Divergence",
    "FaultFamily",
    "RegressionTest",
]
ENDPOINTS = {
    "STARTED_FROM": ("Investigation", "FaultCase"),
    "HAS_FINGERPRINT": ("FaultCase", "Fingerprint"),
    "USES_FEATURE": ("Fingerprint", "Feature"),
    "TARGETS_FEATURE": ("Probe", "Feature"),
    "SELECTED_PROBE": ("Investigation", "Probe"),
    "EXECUTED_AS": ("Investigation", "Run"),
    "ON_VERSION": ("Run", "EngineVersion"),
    "PRODUCED": ("Run", "Divergence"),
    "REDUCED_TO": ("Divergence", "FaultCase"),
    "MATCHES_FAMILY": ("Divergence", "FaultFamily"),
    "INVOLVES_FEATURE": ("FaultFamily", "Feature"),
    "EFFECTIVE_FOR": ("Probe", "FaultFamily"),
    "DERIVED_TEST": ("FaultCase", "RegressionTest"),
}


def evidence_id(value):
    try:
        if str(UUID(value)) == value:
            return value
    except (ValueError, TypeError, AttributeError):
        pass
    raise ValueError("Choose a valid saved comparison ID.")


def fingerprint_id(value):
    if isinstance(value, str) and re.fullmatch("[a-f0-9]{64}", value):
        return value
    raise ValueError("Choose a valid fingerprint ID.")


class EvidenceReference(ArtifactRef):
    owner: BoundedText

    @model_validator(mode="after")
    def safe(self):
        for path in (self.owner, self.path):
            parts = PurePosixPath(path)
            if (
                parts.is_absolute()
                or any(part in (".", "..") for part in path.split("/"))
                or "\\" in path
            ):
                raise ValueError(
                    "Evidence references must stay inside their owner folder."
                )
        evidence_id(self.owner.split("/")[0])
        if self.owner not in (
            self.owner.split("/")[0],
            self.owner.split("/")[0] + "/context",
            self.owner.split("/")[0] + "/planning",
            self.owner.split("/")[0] + "/runtime",
            self.owner.split("/")[0] + "/reduction",
            *[
                self.owner.split("/")[0] + f"/planning/{sequence}"
                for sequence in range(1, 5)
            ],
        ):
            raise ValueError("Choose a saved evidence owner folder.")
        if (
            PurePosixPath(self.path).name != self.path
            or not self.path.endswith(".json")
            or self.mediaType != "application/json"
        ):
            raise ValueError("Use a bounded JSON evidence reference.")
        if (
            self.bytes
            > (
                262144
                if self.owner.endswith("/runtime")
                else (1048576 if "/" in self.owner else 8388608)
            )
            or len(encode(self.model_dump())) > 2048
            or len(self.id) > 160
            or len(self.kind) > 160
        ):
            raise ValueError("Case context exceeds its storage limit.")
        return self


class FingerprintRecord(Contract):
    id: Hash
    version: Literal["fingerprint-v1"]
    catalog_version: Literal["features-v1"]
    normalized_shape: dict
    shape_hash: Hash
    clause_signature: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    feature_ids: list[str] = Field(max_length=len(FEATURE_IDS))
    analysis_support: Literal["supported", "conservative"]
    unsupported_reasons: list[
        Literal[
            "LEXICAL_FALLBACK",
            "UNCERTAIN_SCOPE",
            "EXACT_LITERAL_CONTEXT",
            "UNSUPPORTED_STATEMENT",
        ]
    ] = Field(max_length=4)

    @model_validator(mode="after")
    def identities(self):
        from .jsonio import digest

        if self.shape_hash != digest(self.normalized_shape) or self.id != digest(
            {
                "fingerprint_version": self.version,
                "normalized_shape": self.normalized_shape,
                "feature_ids": self.feature_ids,
            }
        ):
            raise ValueError("Saved fingerprint details do not agree.")
        if bool(self.unsupported_reasons) != (
            self.analysis_support == "conservative"
        ) or self.unsupported_reasons != sorted(set(self.unsupported_reasons)):
            raise ValueError("Saved fingerprint diagnostics do not agree.")
        if len(encode(self.normalized_shape)) > 1048576:
            raise ValueError("Case context exceeds its storage limit.")
        return self

    @field_validator("feature_ids")
    @classmethod
    def controlled(cls, value):
        if value != sorted(set(value)) or any(
            feature not in FEATURE_IDS for feature in value
        ):
            raise ValueError(
                "This case context uses an unsupported feature definition."
            )
        return value


class Node(Contract):
    label: NodeLabel
    properties: dict[str, str | bool | int | float | list[str]]

    @model_validator(mode="after")
    def bounded(self):
        from .graph_properties import PROPERTY_MODELS

        properties = self.properties
        if self.label == "Investigation" and "runtime_version" in properties:
            from .investigation_properties import RuntimeProperties

            RuntimeProperties.model_validate(properties)
        else:
            PROPERTY_MODELS[self.label].model_validate(properties)
        for key, value in properties.items():
            if key.endswith("artifact_ref"):
                from .jsonio import loads

                EvidenceReference.model_validate(loads(value))
        if not properties.get("id") or not properties.get("created_at"):
            raise ValueError("Context nodes require identity and creation time.")
        validate_timestamp(properties["created_at"])
        if any(
            isinstance(v, str) and (not v or len(v.encode()) > 4096)
            for v in properties.values()
        ):
            raise ValueError("Case context exceeds its storage limit.")
        if self.label == "Feature" and properties["id"] not in FEATURE_IDS:
            raise ValueError(
                "This case context uses an unsupported feature definition."
            )
        return self


class Edge(Contract):
    type: Literal[
        "STARTED_FROM",
        "HAS_FINGERPRINT",
        "USES_FEATURE",
        "TARGETS_FEATURE",
        "SELECTED_PROBE",
        "EXECUTED_AS",
        "ON_VERSION",
        "PRODUCED",
        "REDUCED_TO",
        "MATCHES_FAMILY",
        "INVOLVES_FEATURE",
        "EFFECTIVE_FOR",
        "DERIVED_TEST",
    ]
    source_label: NodeLabel
    source_id: BoundedText
    target_label: NodeLabel
    target_id: BoundedText
    properties: dict[str, str | bool | int | float]

    @model_validator(mode="after")
    def typed(self):
        from .relationship_properties import PROPERTY_MODELS, ProvenanceProperties

        PROPERTY_MODELS.get(self.type, ProvenanceProperties).model_validate(
            self.properties
        )
        if "version_scope" in self.properties:
            from .jsonio import loads

            scope = VersionScope.model_validate(loads(self.properties["version_scope"]))
            if encode(scope.model_dump()).decode() != self.properties["version_scope"]:
                raise ValueError("Use a canonical ordered engine scope.")
        if ENDPOINTS[self.type] != (self.source_label, self.target_label):
            raise ValueError("This case context uses an unsupported relationship.")
        if not all(
            self.properties.get(key)
            for key in ("id", "source_kind", "source_id", "created_at")
        ):
            raise ValueError("Context relationships require provenance.")
        if self.properties["source_kind"] not in (
            "deterministic_extraction",
            "execution",
            "catalog",
            "verified_classification",
            "deterministic_planning",
        ):
            raise ValueError("Context relationships require verified provenance.")
        validate_timestamp(self.properties["created_at"])
        if any(
            isinstance(v, str) and len(v.encode()) > 4096
            for v in self.properties.values()
        ):
            raise ValueError("Case context exceeds its storage limit.")
        return self


def validate_timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("Use UTC evidence timestamps.")
    return value


class Phase(Contract):
    investigation_id: str
    fault_case_id: Hash
    fingerprint_id: Hash
    phase_key: Hash
    payload_sha256: Hash
    nodes: list[Node] = Field(max_length=40)
    edges: list[Edge] = Field(max_length=48)
    artifacts: list[EvidenceReference] = Field(max_length=10)

    _id = field_validator("investigation_id")(evidence_id)

    @model_validator(mode="after")
    def bounded(self):
        if len(encode(self.model_dump())) > 262144:
            raise ValueError("Case context exceeds its storage limit.")
        return self


class SavedContext(Contract):
    investigation_id: str
    fault_case_id: Hash
    fingerprint_id: Hash
    context_phase_key: Hash
    context_payload_sha256: Hash
    reused: bool


class SchemaReady(Contract):
    schema_version: Literal["context-v1"] = CONTEXT_SCHEMA_VERSION
    fingerprint_version: Literal["fingerprint-v1"] = "fingerprint-v1"
    canonicalization_version: Literal["case-v1"] = "case-v1"
    indexes: Annotated[int, Field(ge=12)]
    features: Annotated[int, Field(ge=0)]


class VersionScope(Contract):
    baseline: Hash
    target: Hash
    comparison_version: BoundedText


class PairedRunContext(Contract):
    run: Node
    engine: Node


class InvestigationContext(Contract):
    investigation: Node
    case: Node
    fingerprint: Node
    features: list[str] = Field(max_length=len(FEATURE_IDS))
    runs: list[PairedRunContext] = Field(min_length=2, max_length=2)
    divergence: Node | None
    artifacts: list[EvidenceReference] = Field(max_length=10)


class HistoryCandidate(Contract):
    family_id: BoundedText
    family_status: Literal["provisional", "confirmed"]
    probe_id: BoundedText
    probe_type: BoundedText
    template_version: BoundedText
    feature_ids: list[str] = Field(min_length=1, max_length=len(FEATURE_IDS))
    feature_overlap: Annotated[int, Field(gt=0, le=len(FEATURE_IDS))]
    attempts: Annotated[int, Field(ge=0)]
    successes: Annotated[int, Field(ge=0)]
    avg_cost_ms: Annotated[float, Field(ge=0)]
    version_scope: VersionScope
    exact_pair_match: bool
    supporting_episodes: list[InvestigationContext] = Field(min_length=1, max_length=5)

    path_edges: list[Edge] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def statistics(self):
        if (
            self.successes > self.attempts
            or self.feature_ids != sorted(set(self.feature_ids))
            or self.feature_overlap != len(self.feature_ids)
            or any(f not in FEATURE_IDS for f in self.feature_ids)
        ):
            raise ValueError("Related evidence could not be verified.")
        return self


class FingerprintHistory(Contract):
    fingerprint_id: Hash
    candidates: list[HistoryCandidate] = Field(max_length=100)
