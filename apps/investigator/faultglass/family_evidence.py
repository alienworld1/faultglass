from .analysis_models import ClassificationEvidence, FamilyProfile, ProbeEvidence
from .canonicalize import case_identity
from .comparison import material
from .context_artifacts import load_evidence, read_reference
from .context_errors import EvidenceIntegrity
from .context_models import EvidenceReference, VersionScope
from .context_phase import engine_identity
from .family_classifier import score_profile
from .fingerprint import extract_fingerprint
from .graph_repository import read_ref
from .jsonio import loads
from .models import read_case
from .planner_models import Decision, ProbeResult
from .reduction_artifacts import ReductionStore
from .reduction_models import ReductionAttempt


def report_ref(evidence):
    _, report, refs, _, _ = evidence
    ref = next(r for r in refs if r.kind == "report")
    return EvidenceReference(**ref.model_dump(), owner=report.runId)


def collect_probes(store, record):
    pairs = {}
    for receipt in store.history(record):
        for ref in receipt.outputs:
            if ref.path in {"plan.json", "result.json"}:
                sequence = int(ref.owner.rsplit("/", 1)[1])
                pairs.setdefault(sequence, {})[ref.path] = ref
    probes = []
    for sequence, refs in sorted(pairs.items()):
        if set(refs) != {"plan.json", "result.json"}:
            raise EvidenceIntegrity()
        plan = Decision.model_validate(
            loads(read_reference(store.root, refs["plan.json"]))
        )
        result = ProbeResult.model_validate(
            loads(read_reference(store.root, refs["result.json"]))
        )
        evidence = load_evidence(store.root, result.child_evidence_id)
        if (
            result.selection_id != plan.selection_id
            or result.output_case_id != case_identity(evidence[0])[0]
            or result.child_signature
            != (evidence[1].divergence.signature if evidence[1].divergence else None)
        ):
            raise EvidenceIntegrity()
        probes.append(
            ProbeEvidence(
                selectionId=plan.selection_id,
                sequence=sequence,
                probeId=plan.selected_probe_id,
                templateVersion=plan.candidates[0].template_version,
                definitionSha256=plan.candidates[0].definition_sha256,
                inputCaseId=result.input_case_id,
                outputCaseId=result.output_case_id,
                relationship=result.relationship,
                signature=result.child_signature,
                pairedStatuses=result.paired_statuses,
                durationMs=result.duration_ms,
                observedAt=result.finished_at,
                planRef=refs["plan.json"],
                resultRef=refs["result.json"],
                reportRef=report_ref(evidence),
            )
        )
    return probes


def classification_inputs(store, record):
    checkpoint = ReductionStore(store.root, record.snapshot.id).checkpoint(record)
    summary, source = checkpoint.summary, checkpoint.summary.source
    if (
        summary.state != "finished"
        or not source.stable
        or summary.verificationFailures
        or record.reservation
    ):
        raise EvidenceIntegrity()
    original = load_evidence(store.root, record.snapshot.id)
    first = load_evidence(store.root, source.sourceEvidenceId)
    repeated = load_evidence(store.root, source.stabilityEvidenceId)
    if (
        case_identity(first[0])[0] != source.sourceCaseId
        or case_identity(repeated[0])[0] != source.sourceCaseId
        or first[1].divergence != source.referenceDivergence
        or repeated[1].divergence != source.referenceDivergence
        or list(first[3]) != source.engines
        or list(repeated[3]) != source.engines
    ):
        raise EvidenceIntegrity()
    retained = first
    parent = source.sourceCaseId
    from .reduction_candidates import validate_candidate

    parent_case = first[0]
    for ref in checkpoint.attempts:
        attempt = ReductionAttempt.model_validate(
            loads(read_reference(store.root, ref))
        )
        if attempt.state == "accepted":
            evidence = load_evidence(store.root, attempt.verificationEvidenceId)
            validate_candidate(
                parent_case, read_reference(store.root, attempt.candidateRef)
            )
            if (
                attempt.parentCaseId != parent
                or case_identity(evidence[0])[0] != attempt.candidateCaseId
                or evidence[1].divergence != source.referenceDivergence
                or list(evidence[3]) != source.engines
            ):
                raise EvidenceIntegrity()
            parent, parent_case, retained = (
                attempt.candidateCaseId,
                evidence[0],
                evidence,
            )
    case = read_case(read_reference(store.root, summary.finalCaseRef))
    if (
        parent != summary.currentCaseId
        or case_identity(case)[0] != parent
        or case.model_dump() != retained[0].model_dump()
    ):
        raise EvidenceIntegrity()
    probes = collect_probes(store, record)
    for probe in probes:
        if probe.sequence == source.sourceProbeSequence:
            probe.contribution = "repeated_source"
        elif (
            material(
                load_evidence(store.root, probe.reportRef.owner)[
                    1
                ].observations.baseline,
                first[0].observation,
            )
            == material(first[1].observations.baseline, first[0].observation)
            and probe.pairedStatuses["baseline"]
            == first[1].observations.baseline.status
            and first[1].observations.target.status == "crash"
            and probe.pairedStatuses["target"] == "result"
        ):
            # The observed required/optional contrast bounds the family independently of a preserving source.
            probe.contribution = "semantic_contrast"
    profile = FamilyProfile(
        investigationId=record.snapshot.id,
        scope=VersionScope(
            baseline=engine_identity(first[3][0]),
            target=engine_identity(first[3][1]),
            comparison_version=source.referenceDivergence.comparisonVersion,
        ),
        features=extract_fingerprint(first[0])["feature_ids"],
        reducedShape=extract_fingerprint(case)["shape_hash"],
        sourceKind=source.referenceDivergence.kind,
        sourceStatuses=[
            first[1].observations.baseline.status,
            first[1].observations.target.status,
        ],
        probes=probes,
    )
    candidates = []
    rows = store.repository._query(
        "family-candidates",
        {
            "fingerprint": record.snapshot.fingerprintId,
            "exclude_id": record.snapshot.id,
        },
    )
    if len(rows) > 100:
        raise EvidenceIntegrity()
    for family, edge, paths in rows:
        from .context_models import Edge, Node

        Node(label="FaultFamily", properties=dict(family))
        Edge(
            type="MATCHES_FAMILY",
            source_label="Divergence",
            source_id="profile",
            target_label="FaultFamily",
            target_id=family["id"],
            properties=dict(edge),
        )
        reference = read_ref(edge["source_id"])
        previous = ClassificationEvidence.model_validate(
            loads(read_reference(store.root, reference))
        )
        verify_profile(store.root, previous)
        if previous.investigationId == record.snapshot.id:
            continue
        for required in [
            previous.sourceRef,
            previous.stabilityRef,
            previous.retainedCaseRef,
            previous.retainedVerificationRef,
        ]:
            read_reference(store.root, required)
        candidates.append(
            score_profile(
                profile, previous.profile, family, reference, [edge["id"], *paths]
            )
        )
    return ClassificationEvidence(
        investigationId=record.snapshot.id,
        seedCaseId=case_identity(original[0])[0],
        fingerprintId=record.snapshot.fingerprintId,
        retainedCaseId=parent,
        referenceSignature=source.referenceDivergence.signature,
        profile=profile,
        sourceRef=report_ref(first),
        stabilityRef=report_ref(repeated),
        retainedCaseRef=summary.finalCaseRef,
        retainedVerificationRef=report_ref(retained),
        candidates=candidates,
        unknowns=[
            "The underlying source-code cause is not confirmed.",
            "The source case was checked twice. The retained descendant was verified once unless it is the unchanged source.",
        ],
        contradictions=[]
        if not original[1].oracleAssessment
        or "mismatch" not in original[1].oracleAssessment.values()
        else ["The explicit expectation was not met."],
        createdAt=record.snapshot.updatedAt,
    )


def verify_profile(root, evidence):
    first = load_evidence(root, evidence.sourceRef.owner)
    repeated = load_evidence(root, evidence.stabilityRef.owner)
    retained = load_evidence(root, evidence.retainedVerificationRef.owner)
    seed = load_evidence(root, evidence.investigationId)
    profile = evidence.profile
    if (
        evidence.profile.investigationId != evidence.investigationId
        or first[0] != repeated[0]
        or first[1].divergence != repeated[1].divergence
        or not first[1].divergence
        or first[1].divergence.signature != evidence.referenceSignature
        or retained[1].divergence != first[1].divergence
        or first[3] != repeated[3]
        or first[3] != retained[3]
        or report_ref(first) != evidence.sourceRef
        or report_ref(repeated) != evidence.stabilityRef
        or report_ref(retained) != evidence.retainedVerificationRef
        or case_identity(seed[0])[0] != evidence.seedCaseId
        or case_identity(retained[0])[0] != evidence.retainedCaseId
        or extract_fingerprint(first[0])["feature_ids"] != profile.features
        or extract_fingerprint(retained[0])["shape_hash"] != profile.reducedShape
        or profile.sourceStatuses
        != [first[1].observations.baseline.status, first[1].observations.target.status]
        or profile.sourceKind != first[1].divergence.kind
        or profile.scope
        != VersionScope(
            baseline=engine_identity(first[3][0]),
            target=engine_identity(first[3][1]),
            comparison_version=first[1].divergence.comparisonVersion,
        )
    ):
        raise EvidenceIntegrity()
    for probe in profile.probes:
        plan = Decision.model_validate(loads(read_reference(root, probe.planRef)))
        result = ProbeResult.model_validate(
            loads(read_reference(root, probe.resultRef))
        )
        actual = load_evidence(root, result.child_evidence_id)
        if (
            probe.selectionId != plan.selection_id
            or result.selection_id != plan.selection_id
            or probe.inputCaseId != result.input_case_id
            or probe.outputCaseId != result.output_case_id
            or probe.probeId != result.probe_id
            or probe.relationship != result.relationship
            or probe.pairedStatuses != result.paired_statuses
            or probe.signature != result.child_signature
            or probe.reportRef != report_ref(actual)
            or probe.durationMs != result.duration_ms
            or probe.definitionSha256 != plan.candidates[0].definition_sha256
            or probe.templateVersion != plan.candidates[0].template_version
        ):
            raise EvidenceIntegrity()
