from .agent_models import AgentInterpretation
from .analysis_models import (
    ClassificationEvidence,
    ClassificationSummary,
    ConclusionPage,
    ExportManifest,
    HistoricalInfluence,
    MemoryDelta,
)
from .context_artifacts import read_reference
from .context_errors import EvidenceIntegrity
from .explorer import load_run
from .investigation_store import RuntimeErrorResponse
from .jsonio import loads


def owned_document(store, record, ref, area, model):
    if ref.owner != record.snapshot.id + "/" + area:
        raise EvidenceIntegrity()
    return model.model_validate(loads(read_reference(store.root, ref)))


def manifest_for(store, record):
    if not record.exportRef:
        return None
    manifest = owned_document(store, record, record.exportRef, "export", ExportManifest)
    if (
        manifest.investigationId != record.snapshot.id
        or manifest.classificationEvidenceRef != record.classificationRef
    ):
        raise EvidenceIntegrity()
    for file in manifest.files:
        read_reference(store.root, file)
    return manifest


def conclusion_page(store, record, cursor=0):
    if type(cursor) is not int or not 0 <= cursor <= 100:
        raise RuntimeErrorResponse(
            "invalid_cursor", "Choose a valid evidence cursor.", 422
        )
    evidence = (
        owned_document(
            store,
            record,
            record.classificationRef,
            "classification",
            ClassificationEvidence,
        )
        if record.classificationRef
        else None
    )
    candidates = evidence.candidates if evidence else []
    manifest = manifest_for(store, record)
    memory = (
        owned_document(store, record, record.memoryRef, "classification", MemoryDelta)
        if record.memoryRef
        else None
    )
    interpretation = (
        owned_document(
            store,
            record,
            record.snapshot.conclusion.interpretationRef,
            "agent",
            AgentInterpretation,
        )
        if record.snapshot.conclusion and record.snapshot.conclusion.interpretationRef
        else None
    )
    influence = (
        HistoricalInfluence.model_validate(
            loads(read_reference(store.root, record.influenceRef))
        )
        if record.influenceRef
        else None
    )
    return ConclusionPage(
        revision=record.snapshot.revision,
        conclusion=record.snapshot.conclusion,
        classification=ClassificationSummary(
            features=evidence.profile.features,
            scope=evidence.profile.scope,
            referenceSignature=evidence.referenceSignature,
            retainedCaseId=evidence.retainedCaseId,
            retainedIsRepeatedSource=evidence.sourceRef
            == evidence.retainedVerificationRef,
            sourceRef=evidence.sourceRef,
            stabilityRef=evidence.stabilityRef,
            retainedVerificationRef=evidence.retainedVerificationRef,
            probes=evidence.profile.probes,
            contradictions=evidence.contradictions,
        )
        if evidence
        else None,
        exports=manifest,
        memory=memory,
        influence=influence,
        candidates=candidates[cursor : cursor + 10],
        nextCursor=cursor + 10 if cursor + 10 < len(candidates) else None,
        agent=load_run(store, record),
        interpretation=interpretation,
    )


def download(store, record, key):
    if key not in {"case", "regression-test", "report"}:
        raise RuntimeErrorResponse(
            "invalid_artifact",
            "Choose a case, regression test, or report download.",
            422,
        )
    manifest = manifest_for(store, record)
    if manifest is None:
        raise RuntimeErrorResponse(
            "download_unavailable", "This download is not available.", 404
        )
    ref = next(file for file in manifest.files if file.key == key)
    return ref, read_reference(store.root, ref)
