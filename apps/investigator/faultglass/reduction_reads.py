import re

from .canonicalize import case_identity
from .context_artifacts import load_evidence, read_reference
from .context_errors import EvidenceIntegrity
from .evidence_summaries import summarize
from .investigation_store import RuntimeErrorResponse
from .jsonio import encode, loads
from .models import read_case
from .reduction_artifacts import ReductionStore
from .reduction_candidates import case_size, validate_candidate
from .reduction_models import (
    ReductionAttempt,
    ReductionAttemptView,
    ReductionCaseView,
    ReductionPage,
)


def case_view(root, ref, setup_cursor=0, *, count=8):
    case = read_case(read_reference(root, ref))
    end = min(len(case.setup), setup_cursor + count)
    return ReductionCaseView(
        caseId=case_identity(case)[0],
        query=case.query,
        setup=case.setup[setup_cursor:end],
        setupTotal=len(case.setup),
        nextSetupCursor=end if end < len(case.setup) else None,
        caseRef=ref,
    )


def reduction_page(store, record, cursor=0, case_id=None, setup_cursor=0):
    if (
        not 0 <= cursor <= 32
        or not 0 <= setup_cursor <= 32
        or (case_id is not None and not re.fullmatch("[a-f0-9]{64}", case_id))
    ):
        raise RuntimeErrorResponse(
            "invalid_cursor", "Choose a valid reduction page and case.", 422
        )
    if record.reductionRef is None:
        if case_id:
            raise RuntimeErrorResponse(
                "not_found", "This case is not part of the saved reduction.", 404
            )
        return ReductionPage(
            revision=record.snapshot.revision,
            summary=None,
            attempts=[],
            nextCursor=None,
            case=None,
        )
    checkpoint = ReductionStore(store.root, record.snapshot.id).checkpoint(record)
    summary = checkpoint.summary
    source = summary.source
    source_case, source_report, _, engines, _ = load_evidence(
        store.root, source.sourceEvidenceId
    )
    if (
        case_identity(source_case)[0] != source.sourceCaseId
        or source.referenceDivergence != source_report.divergence
        or list(engines) != source.engines
    ):
        raise EvidenceIntegrity()
    if read_case(read_reference(store.root, source.sourceCaseRef)) != source_case:
        raise EvidenceIntegrity()
    cases = {source.sourceCaseId: source.sourceCaseRef}
    retained = source.sourceCaseId
    attempts = []
    for ref in checkpoint.attempts:
        attempt = ReductionAttempt.model_validate(
            loads(read_reference(store.root, ref))
        )
        if (
            attempt.candidateRef.owner != record.snapshot.id + "/reduction"
            or attempt.parentCaseId != retained
        ):
            raise EvidenceIntegrity()
        if attempt.candidatePayloadSha256 != attempt.candidateRef.sha256:
            raise EvidenceIntegrity()
        for artifact in attempt.artifactRefs:
            read_reference(store.root, artifact)
        observations = None
        if attempt.candidateCaseId:
            proposed = read_case(read_reference(store.root, attempt.candidateRef))
            if case_identity(proposed)[0] != attempt.candidateCaseId:
                raise EvidenceIntegrity()
            cases.setdefault(attempt.candidateCaseId, attempt.candidateRef)
        if attempt.verificationEvidenceId and attempt.state in {"accepted", "rejected"}:
            case, report, _, scope, _ = load_evidence(
                store.root, attempt.verificationEvidenceId
            )
            if (
                case_identity(case)[0] != attempt.candidateCaseId
                or list(scope) != source.engines
                or report.divergence != attempt.observedDivergence
            ):
                raise EvidenceIntegrity()
            observations = summarize(report)
        if attempt.state == "accepted":
            if (
                not source.stable
                or attempt.observedDivergence != source.referenceDivergence
            ):
                raise EvidenceIntegrity()
            parent = read_case(read_reference(store.root, cases[retained]))
            validate_candidate(parent, read_reference(store.root, attempt.candidateRef))
            if attempt.beforeSize != case_size(
                parent
            ) or attempt.afterSize != case_size(case):
                raise EvidenceIntegrity()
            retained = attempt.candidateCaseId
        attempts.append((attempt, observations))
    if checkpoint.activeAttempt:
        active = checkpoint.activeAttempt
        if active.parentCaseId != retained:
            raise EvidenceIntegrity()
        if active.candidateCaseId:
            cases.setdefault(active.candidateCaseId, active.candidateRef)
        attempts.append((active, None))
    if retained != summary.currentCaseId or cases[retained] != summary.currentCaseRef:
        raise EvidenceIntegrity()
    if summary.finalCaseRef and read_reference(
        store.root, summary.finalCaseRef
    ) != read_reference(store.root, summary.currentCaseRef):
        raise EvidenceIntegrity()
    repeat = None
    if source.stabilityEvidenceId:
        # Only a published phase makes a completed repeat publicly inspectable.
        completed = any(
            r.phaseReceipt and r.phaseReceipt.purpose == "stability"
            for r in store.history(record)
        )
        if completed:
            repeated_case, repeated, _, repeated_engines, _ = load_evidence(
                store.root, source.stabilityEvidenceId
            )
            if (
                case_identity(repeated_case)[0] != source.sourceCaseId
                or list(repeated_engines) != source.engines
                or (source.stable and repeated.divergence != source.referenceDivergence)
            ):
                raise EvidenceIntegrity()
            repeat = summarize(repeated)
    selected = case_id or retained
    if selected not in cases:
        raise RuntimeErrorResponse(
            "not_found", "This case is not part of the saved reduction.", 404
        )
    page = ReductionPage(
        revision=record.snapshot.revision,
        summary=summary,
        attempts=[],
        nextCursor=None,
        case=case_view(store.root, cases[selected], setup_cursor),
        sourceCase=case_view(store.root, source.sourceCaseRef, count=0),
        sourceObservations=summarize(source_report),
        stabilityObservations=repeat,
    )
    while len(encode(page.model_dump())) > 180000 and page.case.setup:
        page.case.setup.pop()
        page.case.nextSetupCursor = setup_cursor + len(page.case.setup)
    if (
        page.case.nextSetupCursor == setup_cursor
        and not page.case.setup
        and page.case.setupTotal > setup_cursor
    ):
        page.case = case_view(store.root, cases[selected], setup_cursor, count=1)
    index = cursor
    while index < len(attempts) and len(page.attempts) < 10:
        attempt, observations = attempts[index]
        item = ReductionAttemptView(
            attempt=attempt,
            observations=observations,
            parent=case_view(store.root, cases[attempt.parentCaseId], count=0),
            candidate=case_view(store.root, attempt.candidateRef, count=0)
            if attempt.candidateCaseId
            else None,
        )
        page.attempts.append(item)
        page.nextCursor = index + 1 if index + 1 < len(attempts) else None
        if len(encode(page.model_dump())) > 245760:
            if index == cursor:
                item.parent = None
                item.candidate = None
                page.sourceCase = None
                if len(encode(page.model_dump())) > 245760:
                    raise EvidenceIntegrity()
            else:
                page.attempts.pop()
                break
        index += 1
    page.nextCursor = index if index < len(attempts) else None
    return page
