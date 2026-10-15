from uuid import UUID, uuid5

from .canonicalize import CANONICALIZATION_VERSION, case_identity
from .context_artifacts import (
    load_evidence,
    read_reference,
    verify_sidecar,
    write_sidecar,
)
from .context_models import (
    CONTEXT_SCHEMA_VERSION,
    Edge,
    EvidenceReference,
    FingerprintRecord,
    Node,
    Phase,
)
from .fingerprint import FINGERPRINT_VERSION, extract_fingerprint
from .jsonio import digest, encode

CHILD_NAMESPACE = UUID("4f5b18d4-6a59-54d0-8773-312a0772eb44")


def child_id(run_id, role):
    return str(uuid5(CHILD_NAMESPACE, run_id + ":" + role))


def engine_identity(engine):
    return digest(
        {
            "repository": engine.repository,
            "commit_sha": engine.commitSha,
            "image_digest": engine.imageDigest,
        }
    )


def build_phase(root, run_id, *, persist=True):
    case, report, source_refs, engines, manifest_hash = load_evidence(root, run_id)
    case_id, canonical = case_identity(case)
    fingerprint = FingerprintRecord.model_validate(extract_fingerprint(case))
    context_refs = (write_sidecar if persist else verified_documents)(
        root,
        run_id,
        {
            "case.faultglass.json": encode(case.model_dump()),
            "identity.json": encode(canonical),
            "fingerprint.json": encode(fingerprint.model_dump()),
        },
    )
    refs = {ref.path: ref for ref in context_refs}
    originals = {
        ref.kind: EvidenceReference(**ref.model_dump(), owner=run_id)
        for ref in source_refs
        if ref.kind in ("report", "normalized-pair")
    }
    phase_key = digest(
        {
            "seed_evidence_id": run_id,
            "context_schema_version": CONTEXT_SCHEMA_VERSION,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "fingerprint_version": FINGERPRINT_VERSION,
        }
    )
    nodes, edges = [], []
    created = report.startedAt

    def node(label, identity, **props):
        nodes.append(
            Node(
                label=label, properties={"id": identity, "created_at": created, **props}
            )
        )

    def edge(kind, source, target, source_id=None, **props):
        from .context_models import ENDPOINTS

        source_label, target_label = ENDPOINTS[kind]
        edges.append(
            Edge(
                type=kind,
                source_label=source_label,
                source_id=source,
                target_label=target_label,
                target_id=target,
                properties={
                    "id": digest(
                        {"type": kind, "source": source, "target": target, **props}
                    ),
                    "created_at": created,
                    "source_kind": "deterministic_extraction"
                    if kind in ("HAS_FINGERPRINT", "USES_FEATURE")
                    else "execution",
                    "source_id": source_id or run_id,
                    **props,
                },
            )
        )

    node(
        "Investigation",
        run_id,
        workspace_id="falkordb-core",
        status=report.outcome.upper(),
        updated_at=report.finishedAt,
        fault_case_id=case_id,
        fingerprint_version=FINGERPRINT_VERSION,
        canonicalization_version=CANONICALIZATION_VERSION,
        context_schema_version=CONTEXT_SCHEMA_VERSION,
        seed_evidence_id=run_id,
        raw_case_sha256=report.caseContentHash,
        report_artifact_ref=encode(originals["report"].model_dump()).decode(),
        context_phase_key=phase_key,
        **(
            {"terminal_reason": "No difference observed for this case and engine pair."}
            if report.outcome == "not_reproduced"
            else {}
        ),
    )
    node(
        "FaultCase",
        case_id,
        schema_version=case.schemaVersion,
        canonicalization_version=CANONICALIZATION_VERSION,
        content_sha256=case_id,
        setup_sha256=digest(canonical["case_content"]["setup"]),
        query_sha256=digest(canonical["case_content"]["query"]),
        artifact_ref=encode(refs["case.faultglass.json"].model_dump()).decode(),
        title=case.title,
    )
    node(
        "Fingerprint",
        fingerprint.id,
        version=fingerprint.version,
        shape_hash=fingerprint.shape_hash,
        clause_signature=fingerprint.clause_signature,
        analysis_support=fingerprint.analysis_support,
        artifact_ref=encode(refs["fingerprint.json"].model_dump()).decode(),
    )
    edge("STARTED_FROM", run_id, case_id)
    edge(
        "HAS_FINGERPRINT",
        case_id,
        fingerprint.id,
        fingerprint_version=FINGERPRINT_VERSION,
    )
    for feature in fingerprint.feature_ids:
        edge("USES_FEATURE", fingerprint.id, feature)
    for role, engine in zip(("baseline", "target"), engines, strict=True):
        engine_id = engine_identity(engine)
        node(
            "EngineVersion",
            engine_id,
            repository=engine.repository,
            commit_sha=engine.commitSha,
            image_digest=engine.imageDigest,
            lineage=engine.lineage,
            image_ref=engine.imageRef,
            catalog_id=engine.id,
        )
        observation = getattr(report.observations, role)
        run = child_id(run_id, role)
        node(
            "Run",
            run,
            investigation_id=run_id,
            role=role,
            status=observation.status,
            started_at=report.startedAt,
            finished_at=report.finishedAt,
            timing_basis="paired_bounds",
            duration_ms=round(observation.timing.durationMs, 6),
            observation_sha256=digest(observation.model_dump()),
            artifact_ref=encode(originals["normalized-pair"].model_dump()).decode(),
        )
        edge("EXECUTED_AS", run_id, run, sequence=0)
        edge("ON_VERSION", run, engine_id)
        if report.divergence:
            edge("PRODUCED", run, child_id(run_id, "divergence"))
    if report.divergence:
        node(
            "Divergence",
            child_id(run_id, "divergence"),
            investigation_id=run_id,
            signature=report.divergence.signature,
            kind=report.divergence.kind,
            stable=False,
            comparison_version=report.divergence.comparisonVersion,
            artifact_ref=encode(originals["report"].model_dump()).decode(),
        )
    stable_payload = {
        "phase_key": phase_key,
        "source_manifest_sha256": manifest_hash,
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
        "artifacts": [r.model_dump() for r in [*context_refs, *originals.values()]],
    }
    return Phase(
        investigation_id=run_id,
        fault_case_id=case_id,
        fingerprint_id=fingerprint.id,
        phase_key=phase_key,
        payload_sha256=digest(stable_payload),
        nodes=nodes,
        edges=edges,
        artifacts=[*context_refs, *originals.values()],
    )


def verified_documents(root, run_id, documents):
    refs = verify_sidecar(root, run_id)
    for ref in refs:
        if read_reference(root, ref) != documents[ref.path]:
            from .context_errors import EvidenceIntegrity

            raise EvidenceIntegrity()
    return refs
