from .canonicalize import case_identity
from .context_artifacts import load_evidence, read_reference
from .context_errors import EvidenceIntegrity
from .context_models import EvidenceReference
from .context_phase import build_phase
from .jsonio import digest, encode
from .models import RunLimits
from .planner import rank_candidates
from .planner_models import Decision, SourceSnapshot
from .planning_artifacts import PlanningStore
from .probe_graph import catalog, now
from .probe_phase import selection_phase
from .probe_registry import REGISTRY_SHA256
from .probe_service import load_plan, seed_state


def plan_next(repository, record):
    job_id = record.snapshot.id
    sequence = record.snapshot.probeSequence + 1
    store = PlanningStore(repository.config.artifact_root, job_id, sequence)
    context, case, _report, scope, engines, manifest = seed_state(repository, job_id)
    if store.optional("plan.json"):
        plan, _, refs = load_plan(repository, store)
        return plan, selection_phase(plan, refs)
    snapshot = SourceSnapshot(
        catalog=catalog(repository, bootstrap=True),
        history=repository.get_fingerprint_history(
            context.fingerprint.properties["id"],
            scope,
            100,
            exclude_id=job_id,
            overflow_check=True,
        ).candidates,
        feature_ids=context.features,
        scope=scope,
        lineages=[e.lineage for e in engines],
    )
    data = encode(snapshot.model_dump())
    source_ref = store.put("source-snapshot.json", data)
    documents = {"source-snapshot.json": data}

    def save_output(definition, output):
        filename = (
            "case-" + definition.type.lower().replace("_", "-") + ".faultglass.json"
        )
        documents[filename] = encode(output.model_dump())
        return store.put(filename, documents[filename])

    candidates, rejections = rank_candidates(
        case, snapshot, save_output, tried_outputs=record.triedOutputs
    )
    plan = Decision(
        selection_id=digest(
            {
                "seed": job_id,
                "manifest": manifest,
                "registry": REGISTRY_SHA256,
                "planner": "planner-v1",
                "sequence": sequence,
            }
        ),
        investigation_id=job_id,
        sequence=sequence,
        registry_sha256=REGISTRY_SHA256,
        seed_case_id=case_identity(case)[0],
        fingerprint_id=context.fingerprint.properties["id"],
        seed_manifest_sha256=manifest,
        scope=scope,
        created_at=now(),
        novel=not any(c.source == "history" for c in candidates),
        candidates=candidates,
        rejections=rejections,
        selected_probe_id=candidates[0].probe_id if candidates else None,
        outcome="selected" if candidates else "unresolved",
        terminal_reason=None if candidates else "no_applicable_probe",
        limits=RunLimits(),
        source_snapshot_ref=source_ref,
        transformed_case_ref=candidates[0].transformed_case_ref if candidates else None,
    )
    documents["plan.json"] = encode(plan.model_dump())
    refs = store.seal("selection", documents)
    return plan, selection_phase(plan, refs)


def seed_phase(repository, record):
    phase = build_phase(repository.config.artifact_root, record.snapshot.id)
    _, report, refs, _, _ = load_evidence(
        repository.config.artifact_root, record.snapshot.id
    )
    originals = [
        EvidenceReference(**ref.model_dump(), owner=record.snapshot.id) for ref in refs
    ]
    return phase, report, originals


def verify_selection(repository, record):
    store = PlanningStore(
        repository.config.artifact_root,
        record.snapshot.id,
        record.snapshot.probeSequence,
    )
    plan, _, _ = load_plan(repository, store)
    from .probe_transforms import transform

    case, _, _, _, _ = load_evidence(
        repository.config.artifact_root, record.snapshot.id
    )
    current = next(
        (
            entry
            for entry in catalog(repository)
            if entry.definition.id == plan.selected_probe_id
        ),
        None,
    )
    if (
        not current
        or not current.enabled
        or current.definition.definition_sha256 != plan.candidates[0].definition_sha256
    ):
        raise EvidenceIntegrity()
    output, _, reason = transform(case, current.definition)
    data = read_reference(store.root, plan.transformed_case_ref)
    if (
        reason != "applicable"
        or encode(output.model_dump()) != data
        or record.reservation.inputSha256 != digest_bytes(data)
    ):
        raise EvidenceIntegrity()
    return store, plan, data


def digest_bytes(data):
    import hashlib

    return hashlib.sha256(data).hexdigest()


def fingerprint_phase(store, record):
    from .context_models import Edge, FingerprintRecord, Node, Phase
    from .fingerprint import extract_fingerprint
    from .models import read_case

    case = read_case(read_reference(store.root, record.inputRef))
    case_id, canonical = case_identity(case)
    fp = FingerprintRecord.model_validate(extract_fingerprint(case))
    refs = [
        store.put(record.snapshot.id, name, encode(data))
        for name, data in [
            ("case.json", case.model_dump()),
            ("identity.json", canonical),
            ("fingerprint.json", fp.model_dump()),
        ]
    ]
    created = record.snapshot.createdAt
    nodes = [
        Node(
            label="FaultCase",
            properties=dict(
                id=case_id,
                created_at=created,
                schema_version=1,
                canonicalization_version="case-v1",
                content_sha256=case_id,
                setup_sha256=digest(canonical["case_content"]["setup"]),
                query_sha256=digest(canonical["case_content"]["query"]),
                artifact_ref=encode(refs[0].model_dump()).decode(),
                title=case.title,
            ),
        ),
        Node(
            label="Fingerprint",
            properties=dict(
                id=fp.id,
                created_at=created,
                version=fp.version,
                shape_hash=fp.shape_hash,
                clause_signature=fp.clause_signature,
                analysis_support=fp.analysis_support,
                artifact_ref=encode(refs[2].model_dump()).decode(),
            ),
        ),
    ]
    edges = []
    for kind, source, target, source_label, target_label, props in [
        (
            "HAS_FINGERPRINT",
            case_id,
            fp.id,
            "FaultCase",
            "Fingerprint",
            {"fingerprint_version": "fingerprint-v1"},
        ),
        *[
            ("USES_FEATURE", fp.id, feature, "Fingerprint", "Feature", {})
            for feature in fp.feature_ids
        ],
    ]:
        edges.append(
            Edge(
                type=kind,
                source_label=source_label,
                source_id=source,
                target_label=target_label,
                target_id=target,
                properties=dict(
                    id=digest(
                        {"type": kind, "source": source, "target": target, **props}
                    ),
                    created_at=created,
                    source_kind="deterministic_extraction"
                    if kind != "STARTED_FROM"
                    else "execution",
                    source_id=record.snapshot.id,
                    **props,
                ),
            )
        )
    key = digest(
        {
            "investigation": record.snapshot.id,
            "phase": "fingerprint",
            "handler": "runtime-v1",
        }
    )
    return Phase(
        investigation_id=record.snapshot.id,
        fault_case_id=case_id,
        fingerprint_id=fp.id,
        phase_key=key,
        payload_sha256=digest(
            {
                "nodes": [n.model_dump() for n in nodes],
                "edges": [e.model_dump() for e in edges],
            }
        ),
        nodes=nodes,
        edges=edges,
        artifacts=refs,
    )


def historical_influence(repository, record, plan, phase):
    from .analysis_models import HistoricalInfluence, InfluenceRank
    from .jsonio import loads

    snapshot = SourceSnapshot.model_validate(
        loads(read_reference(repository.config.artifact_root, plan.source_snapshot_ref))
    )
    case = load_evidence(repository.config.artifact_root, record.snapshot.id)[0]
    by_probe = {c.probe_id: c.transformed_case_ref for c in plan.candidates}
    counterfactual, _ = rank_candidates(
        case,
        snapshot.model_copy(update={"history": []}),
        lambda definition, _output: by_probe[definition.id],
        tried_outputs=record.triedOutputs,
    )
    ids = sorted(
        {
            e.investigation.properties["id"]
            for c in snapshot.history
            for e in c.supporting_episodes
        }
    )
    result = HistoricalInfluence(
        decisionRef=next(ref for ref in phase.artifacts if ref.path == "plan.json"),
        selectedProbeId=plan.selected_probe_id,
        priorInvestigationIds=ids,
        pathRefs=sorted(
            {e.properties["id"] for c in snapshot.history for e in c.path_edges}
        ),
        withoutHistory=[
            InfluenceRank(probeId=c.probe_id, rank=c.rank, score=c.utility)
            for c in counterfactual
        ],
        withHistory=[
            InfluenceRank(probeId=c.probe_id, rank=c.rank, score=c.utility)
            for c in plan.candidates
        ],
        changed=[c.probe_id for c in counterfactual]
        != [c.probe_id for c in plan.candidates],
    )
    storage = PlanningStore(
        repository.config.artifact_root, record.snapshot.id, plan.sequence
    )
    return storage.put("influence.json", encode(result.model_dump()))
