from .analysis_models import FamilyCandidate


def probe_key(probe):
    return probe.probeId, probe.templateVersion, probe.definitionSha256


def score_profile(current, previous, family, reference, paths):
    a, b = set(current.features), set(previous.features)
    feature = len(a & b) / len(a | b) if a | b else 0.0
    left = {probe_key(p): p for p in current.probes}
    right = {probe_key(p): p for p in previous.probes}
    common = left.keys() & right.keys()
    supporting, contradictory = [], []
    for key in sorted(common):
        first, second = left[key], right[key]
        if (first.relationship, first.pairedStatuses) == (
            second.relationship,
            second.pairedStatuses,
        ):
            supporting.append(first.probeId)
        else:
            contradictory.append(first.probeId)
    behavior = (
        len(supporting) / len(left.keys() | right.keys()) if left or right else 0.0
    )
    shape = float(current.reducedShape == previous.reducedShape)
    version = float(current.scope == previous.scope)
    compatible = bool(
        version
        and current.sourceKind == previous.sourceKind
        and current.sourceStatuses == previous.sourceStatuses
    )
    reasons = []
    if not common:
        reasons.append("no_common_probe")
    if not compatible:
        reasons.append("incompatible_source_or_scope")
    if contradictory:
        reasons.append("contradictory_probe_outcome")
    if not feature:
        reasons.append("no_feature_overlap")
    return FamilyCandidate(
        familyId=family["id"],
        familyStatus=family["status"],
        familyEvidenceRef=reference,
        sourceInvestigationId=previous.investigationId,
        pathRefs=paths,
        feature=feature,
        behavior=behavior,
        reducedShape=shape,
        version=version,
        score=round(
            0.30 * feature + 0.35 * behavior + 0.20 * shape + 0.15 * version, 12
        ),
        compatible=compatible,
        eligible=bool(compatible and feature and supporting and not contradictory),
        supportingProbeIds=supporting,
        contradictoryProbeIds=contradictory,
        reasons=reasons,
    )


def decide(candidates, *, provisional_eligible):
    by_family = {}
    for candidate in candidates:
        previous = by_family.get(candidate.familyId)
        if previous is None or (candidate.eligible, candidate.score) > (
            previous.eligible,
            previous.score,
        ):
            by_family[candidate.familyId] = candidate
    ranked = sorted(by_family.values(), key=lambda c: (-c.score, c.familyId))
    eligible = [c for c in ranked if c.eligible and c.score >= 0.80]
    if eligible:
        winner = eligible[0]
        competing = [
            c.score for c in ranked if c.familyId != winner.familyId and c.compatible
        ]
        if not competing or winner.score - max(competing) >= 0.15 - 1e-12:
            return "matched", winner
    plausible = any(
        c.compatible and not c.contradictoryProbeIds and c.score >= 0.65 for c in ranked
    )
    return (
        ("provisional", None)
        if provisional_eligible and not plausible
        else ("unresolved", None)
    )
