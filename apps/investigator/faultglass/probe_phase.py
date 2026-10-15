from .context_models import ENDPOINTS, Edge, Node, Phase
from .context_phase import child_id
from .jsonio import digest, encode


def link(kind, source, target, created, reference, **properties):
    source_label, target_label = ENDPOINTS[kind]
    return Edge(
        type=kind,
        source_label=source_label,
        source_id=source,
        target_label=target_label,
        target_id=target,
        properties={
            "id": digest(
                {
                    "kind": kind,
                    "source": source,
                    "target": target,
                    "properties": properties,
                }
            ),
            "created_at": created,
            "source_kind": "deterministic_planning"
            if kind == "SELECTED_PROBE"
            else "execution",
            "source_id": encode(reference.model_dump()).decode(),
            **properties,
        },
    )


def make_phase(plan, name, nodes, edges, refs):
    key = digest({"selection_id": plan.selection_id, "phase": name})
    content = {
        "phase_key": key,
        "nodes": [node.model_dump() for node in nodes],
        "edges": [edge.model_dump() for edge in edges],
        "artifacts": [ref.model_dump() for ref in refs],
    }
    return Phase(
        investigation_id=plan.investigation_id,
        fault_case_id=plan.seed_case_id,
        fingerprint_id=plan.fingerprint_id,
        phase_key=key,
        payload_sha256=digest(content),
        nodes=nodes,
        edges=edges,
        artifacts=refs,
    )


def selection_phase(plan, refs):
    by_path = {ref.path: ref for ref in refs}
    plan_ref = by_path["plan.json"]
    edges = []
    if plan.selected_probe_id:
        edges.append(
            link(
                "SELECTED_PROBE",
                plan.investigation_id,
                plan.selected_probe_id,
                plan.created_at,
                plan_ref,
                sequence=1,
                score=round(plan.candidates[0].utility, 6),
                reason_code="historical_evidence"
                if not plan.novel
                else "structural_evidence",
                selection_id=plan.selection_id,
                planner_version=plan.planner_version,
                plan_artifact_ref=encode(plan_ref.model_dump()).decode(),
                snapshot_artifact_ref=encode(
                    plan.source_snapshot_ref.model_dump()
                ).decode(),
            )
        )
    ordered_refs = [plan_ref, *[ref for ref in refs if ref != plan_ref]]
    return make_phase(plan, "selection", [], edges, ordered_refs)


def observation_phase(plan, result, report, result_ref):
    refs = {ref.kind: ref for ref in result.child_artifacts}
    nodes, edges = [], []
    created = report.startedAt
    for role in ("baseline", "target"):
        identity = child_id(result.child_evidence_id, role)
        observation = getattr(report.observations, role)
        nodes.append(
            Node(
                label="Run",
                properties={
                    "id": identity,
                    "created_at": created,
                    "investigation_id": plan.investigation_id,
                    "probe_id": plan.selected_probe_id,
                    "child_evidence_id": result.child_evidence_id,
                    "role": role,
                    "status": observation.status,
                    "started_at": report.startedAt,
                    "finished_at": report.finishedAt,
                    "timing_basis": "paired_bounds",
                    "duration_ms": round(observation.timing.durationMs, 6),
                    "observation_sha256": digest(observation.model_dump()),
                    "artifact_ref": encode(
                        refs["normalized-pair"].model_dump()
                    ).decode(),
                },
            )
        )
        edges.append(
            link(
                "EXECUTED_AS",
                plan.investigation_id,
                identity,
                created,
                result_ref,
                sequence=1,
                probe_id=plan.selected_probe_id,
            )
        )
        edges.append(
            link("ON_VERSION", identity, getattr(plan.scope, role), created, result_ref)
        )
        if report.divergence:
            edges.append(
                link(
                    "PRODUCED",
                    identity,
                    child_id(result.child_evidence_id, "divergence"),
                    created,
                    result_ref,
                )
            )
    if report.divergence:
        nodes.append(
            Node(
                label="Divergence",
                properties={
                    "id": child_id(result.child_evidence_id, "divergence"),
                    "created_at": created,
                    "investigation_id": plan.investigation_id,
                    "signature": report.divergence.signature,
                    "kind": report.divergence.kind,
                    "stable": False,
                    "comparison_version": report.divergence.comparisonVersion,
                    "artifact_ref": encode(refs["report"].model_dump()).decode(),
                },
            )
        )
    return make_phase(
        plan, "observation", nodes, edges, [result_ref, *result.child_artifacts]
    )
