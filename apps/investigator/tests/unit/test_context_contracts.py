from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from faultglass.context_config import ContextConfig
from faultglass.context_models import (
    Edge,
    EvidenceReference,
    Node,
    VersionScope,
    evidence_id,
    fingerprint_id,
)
from faultglass.jsonio import encode


def test_identifiers_configuration_and_relative_references_fail_closed():
    for value in ("../escape", "", "0", "ABCDEFAB-1234-4234-8234-123456789ABC"):
        with pytest.raises(ValueError):
            evidence_id(value)
    for value in ("../escape", "A" * 64, "a" * 63):
        with pytest.raises(ValueError):
            fingerprint_id(value)
    for name in (
        "other-workspace",
        "faultglass__test_;MATCH",
        "faultglass__test_../escape",
    ):
        with pytest.raises(ValidationError):
            ContextConfig(graph=name)
    ref = {
        "id": "artifact",
        "kind": "report",
        "path": "report.json",
        "owner": str(uuid4()),
        "mediaType": "application/json",
        "sha256": "0" * 64,
        "bytes": 1,
    }
    assert EvidenceReference.model_validate(ref)
    for change in (
        {"owner": "../escape"},
        {"path": "../report.json"},
        {"path": "/report.json"},
        {"path": "a\\report.json"},
        {"sha256": "x"},
        {"mediaType": "text/plain"},
        {"bytes": -1},
    ):
        with pytest.raises(ValidationError):
            EvidenceReference.model_validate({**ref, **change})


def test_reserved_nodes_and_relationships_require_strict_provenance():
    now = datetime.now(UTC).isoformat()
    with pytest.raises(ValidationError):
        Node(label="Probe", properties={"id": "probe", "created_at": now})
    properties = {
        "id": "edge",
        "source_kind": "execution",
        "source_id": str(uuid4()),
        "created_at": now,
    }
    edge = {
        "type": "EXECUTED_AS",
        "source_label": "Investigation",
        "source_id": str(uuid4()),
        "target_label": "Run",
        "target_id": str(uuid4()),
        "properties": {**properties, "sequence": 0},
    }
    assert Edge.model_validate(edge)
    for changed in (
        {"target_label": "Probe"},
        {"type": "RELATES"},
        {"properties": properties},
        {"properties": {**properties, "sequence": -1}},
    ):
        with pytest.raises(ValidationError):
            Edge.model_validate({**edge, **changed})
    scope = VersionScope(
        baseline="0" * 64,
        target="1" * 64,
        comparison_version="paired-evidence-v1/typed-values-v1",
    )
    learned = {
        "type": "EFFECTIVE_FOR",
        "source_label": "Probe",
        "source_id": "probe",
        "target_label": "FaultFamily",
        "target_id": "family",
        "properties": {
            **properties,
            "attempts": 2,
            "successes": 1,
            "avg_cost_ms": 10.0,
            "last_seen_at": now,
            "version_scope": encode(scope.model_dump()).decode(),
        },
    }
    assert Edge.model_validate(learned)
    for change in (
        {"successes": 3},
        {"attempts": -1},
        {"avg_cost_ms": float("nan")},
        {"avg_cost_ms": -1.0},
        {"version_scope": "{}"},
    ):
        with pytest.raises(ValidationError):
            Edge.model_validate(
                {**learned, "properties": {**learned["properties"], **change}}
            )
