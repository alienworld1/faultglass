from pathlib import Path

import pytest

from faultglass.jsonio import encode
from faultglass.models import read_case
from faultglass.reduction_candidates import (
    candidates,
    case_size,
    query_cuts,
    smaller,
    validate_candidate,
)


def seed():
    return read_case(
        (Path(__file__).parents[1] / "fixtures/call-yield.faultglass.json").read_bytes()
    )


def test_frozen_observation_and_whitespace_cannot_shrink():
    parent = seed()
    for changes in (
        {"query": parent.query + "   "},
        {"observation": {"compareResult": False, "ordering": "unordered"}},
    ):
        with pytest.raises(ValueError):
            validate_candidate(parent, encode({**parent.model_dump(), **changes}))
    assert not smaller(case_size(parent), case_size(parent))


def test_query_then_whole_fixture_deletions_preserve_frozen_fields():
    parent = seed().model_copy(
        update={"query": "CALL db.labels() YIELD label WITH label OPTIONAL MATCH (n)"}
    )
    proposals = list(candidates(parent))
    assert [p[1] for p in proposals] == [
        "remove-with-v1",
        "remove-optional-v1",
        "remove-match-v1",
        "remove-setup-v1",
    ]
    for _, _, data, _ in proposals:
        candidate = validate_candidate(parent, data)
        assert smaller(case_size(parent), case_size(candidate))
        assert candidate.observation == parent.observation
        assert candidate.metadata == parent.metadata


def test_token_boundaries_fail_closed_and_ignore_comments():
    assert not query_cuts("CALL db.labels() YIELD label WITH other MATCH (n)")
    assert not query_cuts("CALL db.labels() YIELD label MATCH (n) RETURN n")
    assert not query_cuts("CALL { RETURN 'MATCH (n)' } YIELD label MATCH (n)")
    assert query_cuts(
        "CALL db.labels() /* WITH fake */ YIELD label WITH label MATCH (`WITH`);"
    )
    case = seed()
    assert case_size(case) == case_size(
        case.model_copy(update={"query": case.query + " /* ignored */;"})
    ).model_copy(update={"executableBytes": case_size(case).executableBytes})


def test_size_order_rejects_trades_between_query_and_fixture():
    parent = seed()
    candidate = parent.model_copy(
        update={"query": "RETURN 1", "setup": [*parent.setup, "CREATE (:Extra)"]}
    )
    assert not smaller(case_size(parent), case_size(candidate))
    with pytest.raises(ValueError, match="not smaller"):
        validate_candidate(parent, encode(candidate.model_dump()))


def test_exact_reference_and_engine_scope_are_required():
    from types import SimpleNamespace

    from faultglass.reduction_service import preserving

    source = SimpleNamespace(
        referenceDivergence="fixed-signature", engines=["baseline", "target"]
    )
    assert preserving(
        source,
        SimpleNamespace(outcome="reproduced", divergence="fixed-signature"),
        ("baseline", "target"),
    )
    for outcome, signature, engines in [
        ("failed", "fixed-signature", source.engines),
        ("not_reproduced", None, source.engines),
        ("reproduced", "changed-signature", source.engines),
        ("reproduced", "fixed-signature", ["target", "baseline"]),
    ]:
        assert not preserving(
            source, SimpleNamespace(outcome=outcome, divergence=signature), engines
        )
