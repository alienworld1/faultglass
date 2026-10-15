from math import sqrt
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from faultglass.canonicalize import case_identity
from faultglass.context_models import EvidenceReference, VersionScope
from faultglass.jsonio import digest, encode
from faultglass.models import read_case
from faultglass.planner import affinity, factors, rank_candidates
from faultglass.planner_models import CatalogProbe, ExecutionJournal, SourceSnapshot
from faultglass.probe_phase import link
from faultglass.probe_registry import REGISTRY

SCOPE = VersionScope(
    baseline="a" * 64, target="b" * 64, comparison_version="comparison-v1"
)
NOW = "2026-10-15T00:00:00+00:00"


def test_independent_score_expectations_cover_smoothing_exploration_cost_and_fit():
    score = factors(["CALL", "MATCH", "YIELD"], ["CALL", "MATCH", "YIELD"])
    assert score == dict(
        feature_fit=1.0,
        historical_yield=0.5,
        version_affinity=0.0,
        novelty=1.0,
        normalized_cost=0.25,
        utility=0.5875,
    )
    history = SimpleNamespace(
        attempts=4, successes=3, avg_cost_ms=30000.0, feature_ids=["CALL"]
    )
    scored = factors(
        ["CALL", "MATCH", "YIELD"], ["CALL", "MATCH", "YIELD"], history, 0.5
    )
    assert scored["feature_fit"] == pytest.approx(2 / 3)
    assert scored["historical_yield"] == pytest.approx(2 / 3)
    assert scored["novelty"] == pytest.approx(1 / sqrt(5))
    assert scored["normalized_cost"] == 0.375
    assert scored["utility"] == pytest.approx(
        0.35 * (2 / 3) + 0.30 * (2 / 3) + 0.20 * 0.5 + 0.10 / sqrt(5) - 0.05 * 0.375
    )
    for cost, expected in [("small", 0.25), ("medium", 0.5), ("large", 1.0)]:
        assert (
            factors(["CALL"], ["CALL"], cost_class=cost)["normalized_cost"] == expected
        )
    history.attempts, history.successes, history.avg_cost_ms = 0, 0, 0.0
    empty = factors(["CALL"], ["CALL"], history, 1.0)
    assert (
        empty["historical_yield"] == 0.5
        and empty["novelty"] == 1.0
        and empty["normalized_cost"] == 0.25
    )
    history.attempts, history.avg_cost_ms = 1, 90000.0
    assert factors(["CALL"], ["CALL"], history)["normalized_cost"] == 0.625


@pytest.mark.parametrize(
    "scope,lineages,expected",
    [
        (SCOPE, ["legacy-c", "rust"], 1.0),
        (
            SCOPE.model_copy(update={"baseline": "b" * 64, "target": "a" * 64}),
            ["legacy-c", "rust"],
            None,
        ),
        (
            SCOPE.model_copy(update={"comparison_version": "other"}),
            ["legacy-c", "rust"],
            None,
        ),
        (SCOPE.model_copy(update={"baseline": "c" * 64}), ["legacy-c", "rust"], 0.5),
        (SCOPE.model_copy(update={"baseline": "c" * 64}), ["rust", "legacy-c"], None),
    ],
)
def test_ordered_identity_lineage_and_comparator_affinity(scope, lineages, expected):
    row = SimpleNamespace(
        version_scope=scope,
        supporting_episodes=[
            SimpleNamespace(
                runs=[
                    SimpleNamespace(
                        engine=SimpleNamespace(properties={"lineage": lineage})
                    )
                    for lineage in lineages
                ]
            )
        ],
    )
    assert affinity(row, SCOPE, ["legacy-c", "rust"]) == expected


def snapshot():
    ref = EvidenceReference(
        id="ref",
        kind="source",
        owner=str(uuid4()),
        path="source.json",
        mediaType="application/json",
        sha256="0" * 64,
        bytes=1,
    )
    return SourceSnapshot(
        catalog=[
            CatalogProbe(
                definition=definition,
                enabled=True,
                targets=[
                    link("TARGETS_FEATURE", definition.id, feature, NOW, ref)
                    for feature in definition.target_feature_ids
                ],
            )
            for definition in reversed(REGISTRY)
        ],
        history=[],
        feature_ids=["CALL", "MATCH", "YIELD"],
        scope=SCOPE,
        lineages=["legacy-c", "rust"],
    )


def output_reference(definition, output):
    return EvidenceReference(
        id=case_identity(output)[0],
        kind="case",
        owner="11111111-1111-4111-8111-111111111111/planning",
        path=definition.type.lower() + ".json",
        mediaType="application/json",
        sha256=digest(output.model_dump()),
        bytes=len(encode(output.model_dump())),
    )


def test_rank_order_is_independent_of_registration_order_and_disabled_tools_are_rejected():
    case = read_case(
        (Path(__file__).parents[1] / "fixtures/call-yield.faultglass.json").read_bytes()
    )
    source = snapshot()
    ranked, rejected = rank_candidates(case, source, output_reference)
    assert not rejected and [item.probe_id for item in ranked] == [
        item.id for item in REGISTRY
    ]
    assert [item.rank for item in ranked] == [1, 2]
    assert ranked == rank_candidates(case, source, output_reference)[0]
    source.catalog[0].enabled = False
    ranked, rejected = rank_candidates(case, source, output_reference)
    assert len(ranked) == 1 and rejected[0].reason_code == "disabled"


def test_journal_and_score_contracts_reject_nonfinite_unknown_and_inconsistent_fields():
    with pytest.raises(ValidationError):
        ExecutionJournal(
            selection_id="0" * 64,
            child_evidence_id=str(uuid4()),
            state="evidence_complete",
            reserved_at=NOW,
        )
    case = read_case(
        (Path(__file__).parents[1] / "fixtures/call-yield.faultglass.json").read_bytes()
    )
    winner = rank_candidates(case, snapshot(), output_reference)[0][0]
    for changed in [
        {"utility": float("nan")},
        {"novelty": 1.1},
        {"utility": 0.1},
        {"successes": 2},
        {"extra": True},
    ]:
        with pytest.raises(ValidationError):
            type(winner).model_validate({**winner.model_dump(), **changed})


def history_row(
    probe=REGISTRY[1], family="family-b", attempts=4, successes=3, scope=SCOPE
):
    return SimpleNamespace(
        probe_id=probe.id,
        probe_type=probe.type,
        template_version=probe.template_version,
        family_id=family,
        attempts=attempts,
        successes=successes,
        avg_cost_ms=0.0,
        feature_ids=["CALL", "YIELD"],
        version_scope=scope,
        supporting_episodes=[
            SimpleNamespace(
                runs=[
                    SimpleNamespace(
                        engine=SimpleNamespace(properties={"lineage": lineage})
                    )
                    for lineage in ("legacy-c", "rust")
                ]
            )
        ],
    )


def test_representative_uses_highest_utility_with_family_scope_ties_without_summing_paths():
    case = read_case(
        (Path(__file__).parents[1] / "fixtures/call-yield.faultglass.json").read_bytes()
    )
    source = snapshot()
    source.history = [
        history_row(family="family-b"),
        history_row(family="family-a"),
        history_row(family="weak", attempts=100, successes=0),
    ]
    ranked, _ = rank_candidates(case, source, output_reference)
    winner = ranked[0]
    assert (
        winner.probe_id == REGISTRY[1].id
        and winner.attempts == 4
        and winner.successes == 3
    )
    assert winner.chosen_history_key.startswith("family-a:")
    assert winner.feature_fit == pytest.approx(5 / 6)
    assert winner.utility == pytest.approx(
        0.35 * (5 / 6) + 0.30 * (2 / 3) + 0.20 + 0.10 / sqrt(5) - 0.05 * 0.125
    )
    source.history = [*reversed(source.history), source.history[0]]
    assert rank_candidates(case, source, output_reference)[0] == ranked
    source.history = [
        history_row(
            scope=SCOPE.model_copy(
                update={"baseline": SCOPE.target, "target": SCOPE.baseline}
            )
        )
    ]
    ranked, rejected = rank_candidates(case, source, output_reference)
    assert ranked[0].probe_id == REGISTRY[0].id
    assert rejected[0].reason_code == "incompatible_scope"
    unknown = history_row()
    unknown.probe_id = "unknown:v1"
    source.history = [unknown]
    ranked, rejected = rank_candidates(case, source, output_reference)
    assert (
        ranked[0].source == "structural"
        and rejected[0].reason_code == "unknown_definition"
    )


def test_duplicate_outputs_keep_lexical_definition_and_preserve_rejection(monkeypatch):
    from faultglass import planner

    case = read_case(
        (Path(__file__).parents[1] / "fixtures/call-yield.faultglass.json").read_bytes()
    )
    output, edit, _ = planner.transform(case, REGISTRY[0])
    monkeypatch.setattr(planner, "transform", lambda *_: (output, edit, "applicable"))
    ranked, rejected = rank_candidates(case, snapshot(), output_reference)
    assert len(ranked) == 1 and ranked[0].probe_id == REGISTRY[0].id
    assert (
        rejected[0].probe_id == REGISTRY[1].id
        and rejected[0].reason_code == "duplicate_output"
    )
