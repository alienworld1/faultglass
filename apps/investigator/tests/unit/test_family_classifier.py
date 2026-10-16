from faultglass.analysis_models import FamilyCandidate
from faultglass.context_models import EvidenceReference
from faultglass.family_classifier import decide


def candidate(identity, score, *, eligible=True, compatible=True, contradictions=()):
    return FamilyCandidate(
        familyId=identity,
        familyStatus="provisional",
        familyEvidenceRef=EvidenceReference(
            id="a",
            kind="classification",
            owner="00000000-0000-0000-0000-000000000001/classification",
            path="profile.json",
            mediaType="application/json",
            bytes=1,
            sha256="a" * 64,
        ),
        sourceInvestigationId="00000000-0000-0000-0000-000000000001",
        pathRefs=[],
        feature=1.0,
        behavior=1.0,
        reducedShape=1.0,
        version=1.0,
        score=score,
        compatible=compatible,
        eligible=eligible,
        supportingProbeIds=["probe"],
        contradictoryProbeIds=list(contradictions),
        reasons=[],
    )


def test_margin_and_ties_abstain_without_creating_duplicate_family():
    a, b = candidate("first", 0.9), candidate("second", 0.9)
    assert decide([a, b], provisional_eligible=True) == ("unresolved", None)
    b.score = 0.76
    assert decide([a, b], provisional_eligible=True) == ("unresolved", None)
    b.score = 0.75
    assert decide([a, b], provisional_eligible=True) == ("matched", a)


def test_only_supported_observations_can_create_a_provisional_family():
    assert decide([], provisional_eligible=False) == ("unresolved", None)
    assert decide([], provisional_eligible=True) == ("provisional", None)
    assert decide([candidate("near", 0.79)], provisional_eligible=True) == (
        "unresolved",
        None,
    )
    assert decide(
        [candidate("foreign", 1.0, eligible=False, compatible=False)],
        provisional_eligible=False,
    ) == ("unresolved", None)


def test_exact_eighty_percent_boundary_is_not_lost_to_binary_rounding():
    from types import SimpleNamespace

    from faultglass.family_classifier import score_profile

    probe = SimpleNamespace(
        probeId="observed",
        templateVersion="v1",
        definitionSha256="a" * 64,
        relationship="preserved",
        pairedStatuses={"baseline": "error", "target": "crash"},
    )
    current = SimpleNamespace(
        features=["CALL", "MATCH", "YIELD"],
        probes=[probe],
        reducedShape="a" * 64,
        scope="exact",
        sourceKind="mixed",
        sourceStatuses=["error", "crash"],
    )
    previous = SimpleNamespace(
        **{
            **vars(current),
            "investigationId": "00000000-0000-0000-0000-000000000001",
            "reducedShape": "b" * 64,
        }
    )
    reference = candidate("family", 1.0).familyEvidenceRef
    scored = score_profile(
        current, previous, {"id": "family", "status": "provisional"}, reference, []
    )
    assert scored.score == 0.8
    assert decide([scored], provisional_eligible=True) == ("matched", scored)
