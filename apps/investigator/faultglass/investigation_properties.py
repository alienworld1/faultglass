from typing import Annotated, Literal

from pydantic import Field

from .graph_properties import BaseProperties, Text
from .investigation_models import RuntimeStatus
from .models import Hash


class RuntimeProperties(BaseProperties):
    runtime_version: Literal["runtime-v1"]
    workspace_id: Literal["falkordb-core"]
    context_schema_version: Literal["context-v1"]
    canonicalization_version: Literal["case-v1"]
    fingerprint_version: Literal["fingerprint-v1"]
    status: RuntimeStatus
    revision: Annotated[int, Field(ge=1)]
    updated_at: Text
    admission_key: Text
    payload_sha256: Hash
    runtime_artifact_ref: Text
    runtime_receipt_key: Hash
    context_phase_key: Hash | None = None
    context_payload_sha256: Hash | None = None
    context_recorded_at: Text | None = None
    fault_case_id: Hash | None = None
    seed_evidence_id: Text | None = None
    seed_status: Literal["REPRODUCED", "NOT_REPRODUCED"] | None = None
    raw_case_sha256: Hash | None = None
    report_artifact_ref: Text | None = None
