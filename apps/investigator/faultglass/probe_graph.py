from datetime import UTC, datetime

from .context_errors import (
    ContextError,
    ContextUnavailable,
    EvidenceIntegrity,
    IdentityConflict,
)
from .context_models import Edge, Node
from .jsonio import digest, encode
from .planner_models import CatalogProbe, CommitReceipt
from .probe_registry import REGISTRY, REGISTRY_SHA256


def now():
    return datetime.now(UTC).isoformat()


def catalog(repository, *, bootstrap=False):
    repository._assert_ready()
    ids = [definition.id for definition in REGISTRY]
    rows = repository._query("probe-catalog-read", {"ids": ids})
    entries = {}
    for props, edge, target in rows:
        props = dict(props)
        Node(label="Probe", properties=props)
        entry = entries.setdefault(props["id"], [props, []])
        if entry[0] != props:
            raise IdentityConflict()
        if edge:
            entry[1].append(
                Edge(
                    type="TARGETS_FEATURE",
                    source_label="Probe",
                    source_id=props["id"],
                    target_label="Feature",
                    target_id=target,
                    properties=dict(edge),
                )
            )
    expected, parameters = [], []
    for definition in REGISTRY:
        existing = entries.get(definition.id)
        created = existing[0]["created_at"] if existing else now()
        node = Node(
            label="Probe",
            properties={
                "id": definition.id,
                "created_at": created,
                "type": definition.type,
                "template_version": definition.template_version,
                "description": definition.description,
                "cost_class": definition.cost_class,
                "enabled": existing[0]["enabled"] if existing else definition.enabled,
                "definition_sha256": definition.definition_sha256,
            },
        )
        targets = [
            Edge(
                type="TARGETS_FEATURE",
                source_label="Probe",
                source_id=definition.id,
                target_label="Feature",
                target_id=feature,
                properties={
                    "id": digest({"probe": definition.id, "target": feature}),
                    "created_at": created,
                    "source_kind": "catalog",
                    "source_id": REGISTRY_SHA256,
                },
            )
            for feature in definition.target_feature_ids
        ]
        if existing and (existing[0] != node.properties or existing[1] != targets):
            raise IdentityConflict()
        if not existing and not bootstrap:
            raise EvidenceIntegrity()
        expected.append(
            CatalogProbe(
                definition=definition,
                enabled=node.properties["enabled"],
                targets=targets,
            )
        )
        parameters.append(
            {
                "node": node.properties,
                "targets": [edge.model_dump() for edge in targets],
            }
        )
    if bootstrap:
        repository._query("probe-catalog", {"probes": parameters}, write=True)
        return catalog(repository)
    return expected


def phase_receipt(repository, phase, name, selection_id, child_id=None):
    props = repository._lookup(phase.investigation_id)
    if props is None:
        raise EvidenceIntegrity()
    key = props.get(name + "_phase_key")
    if key is None:
        if props.get(name + "_payload_sha256") or props.get(name + "_committed_at"):
            raise EvidenceIntegrity()
        return None
    if (
        not props.get(name + "_committed_at")
        or key != phase.phase_key
        or props.get(name + "_payload_sha256") != phase.payload_sha256
        or props.get(name + "_artifact_ref")
        != encode(phase.artifacts[0].model_dump()).decode()
    ):
        raise IdentityConflict()
    repository._check_immutable(phase, require_complete=True)
    actual = repository._query("probe-evidence", {"id": phase.investigation_id})
    kinds = (
        {"SELECTED_PROBE"}
        if name == "selection"
        else {"EXECUTED_AS", "ON_VERSION", "PRODUCED"}
    )
    actual = {row[3]["id"] for row in actual if row[0] in kinds}
    if actual != {edge.properties["id"] for edge in phase.edges}:
        raise EvidenceIntegrity()
    receipt = CommitReceipt(
        selection_id=selection_id,
        phase=name,
        phase_key=key,
        payload_sha256=phase.payload_sha256,
        committed_at=props[name + "_committed_at"],
        reused=True,
        artifacts=phase.artifacts,
        child_evidence_id=child_id,
    )

    from .planning_artifacts import PlanningStore

    store = PlanningStore(repository.config.artifact_root, phase.investigation_id)
    store.put(
        name + "-receipt.json",
        encode(receipt.model_copy(update={"reused": False}).model_dump()),
    )
    return receipt


def commit_phase(repository, phase, name, selection_id, child_id=None):
    repository._assert_ready()
    saved = phase_receipt(repository, phase, name, selection_id, child_id)
    if saved:
        return saved
    repository._check_immutable(phase)
    params = dict(
        investigation_id=phase.investigation_id,
        phase_key=phase.phase_key,
        payload_sha256=phase.payload_sha256,
        committed_at=now(),
        artifact_ref=encode(phase.artifacts[0].model_dump()).decode(),
    )
    if name == "selection":
        params["selections"] = [edge.model_dump() for edge in phase.edges]
        params["probe_id"] = phase.edges[0].target_id if phase.edges else ""
    else:
        nodes = {
            node.properties.get("role", "divergence"): node.properties
            for node in phase.nodes
        }
        params.update(
            baseline_run=nodes["baseline"],
            target_run=nodes["target"],
            divergences=[nodes["divergence"]] if "divergence" in nodes else [],
        )
        for edge in phase.edges:
            role = (
                "baseline"
                if edge.source_id == nodes["baseline"]["id"]
                or edge.target_id == nodes["baseline"]["id"]
                else "target"
            )
            key = {
                "EXECUTED_AS": "executed",
                "ON_VERSION": "on",
                "PRODUCED": "produced",
            }[edge.type]
            params[key + "_" + role] = edge.properties
            if edge.type == "ON_VERSION":
                params[role + "_engine_id"] = edge.target_id
        params.setdefault("produced_baseline", {})
        params.setdefault("produced_target", {})
    if len(encode(params)) > 262144:
        raise ContextError("Experiment evidence exceeds the supported context limit.")
    try:
        repository._query("probe-" + name, params, write=True)
    except ContextUnavailable:
        repository.close()
        saved = phase_receipt(repository, phase, name, selection_id, child_id)
        if saved:
            return saved
        raise
    saved = phase_receipt(repository, phase, name, selection_id, child_id)
    if saved is None:
        raise EvidenceIntegrity()
    return saved.model_copy(update={"reused": False})
