import pytest
from falkordb.edge import Edge
from falkordb.node import Node
from falkordb.path import Path

from faultglass.comparison import compare
from faultglass.matrix import engines_for
from faultglass.models import (
    EngineError,
    EngineObservation,
    ObservationSpec,
    PairedObservation,
    RunLimits,
    Timing,
)
from faultglass.normalize import normalize, result


def observed(rows, ordered=False):
    return EngineObservation(
        engineVersionId="sample",
        status="result",
        result=result(["value"], rows, ordered, RunLimits()),
        timing=Timing(durationMs=1.0),
    )


def difference(left, right, compare_result=True):
    return compare(
        PairedObservation(baseline=left, target=right),
        engines_for("call-yield-c-rust"),
        ObservationSpec(compareResult=compare_result, ordering="unordered"),
    )


def test_unordered_rows_preserve_multiplicity():
    assert difference(observed([[1], [2], [1]]), observed([[1], [1], [2]])) is None
    assert difference(observed([[1], [2], [1]]), observed([[1], [2]]))
    assert difference(observed([[1], [2]], True), observed([[2], [1]], True))


def test_types_maps_and_large_integers():
    assert (
        difference(observed([[{"b": 2, "a": 1}]]), observed([[{"a": 1, "b": 2}]]))
        is None
    )
    for left, right in [(True, 1), (1, 1.0), (None, "null"), (2**60, 2**60 + 1)]:
        assert difference(observed([[left]]), observed([[right]]))
    assert difference(observed([[1]]), observed([[2]]), False) is None


def test_graph_ids_are_diagnostic_and_path_direction_is_semantic():
    a, b = (
        Node(node_id=1, labels=["N"], properties={"v": 1}),
        Node(node_id=2, labels=["N"]),
    )
    c, d = (
        Node(node_id=9, labels=["N"], properties={"v": 1}),
        Node(node_id=10, labels=["N"]),
    )
    assert normalize(a) == normalize(c)
    assert normalize(Path([a, b], [Edge(1, "R", 2)])) == normalize(
        Path([c, d], [Edge(9, "R", 10)])
    )
    assert normalize(Path([a, b], [Edge(1, "R", 2)])) != normalize(
        Path([a, b], [Edge(2, "R", 1)])
    )


def test_signature_excludes_wording_timing_and_disabled_results():
    left = EngineObservation(
        engineVersionId="sample",
        status="error",
        error=EngineError(category="SEMANTIC", detail="first wording"),
        timing=Timing(durationMs=1.0),
    )
    right = left.model_copy(
        update={
            "error": EngineError(category="CRASH", detail="stopped"),
            "status": "crash",
        }
    )
    original = difference(left, right)
    left.error.detail = "another wording"
    left.timing.durationMs = 100.0
    assert difference(left, right).signature == original.signature
    right.error.category = "UNKNOWN"
    right.status = "error"
    assert difference(left, right).signature != original.signature


def test_unsupported_and_incomplete_values_fail():
    for value in (float("inf"), float("nan"), object()):
        with pytest.raises(ValueError):
            normalize(value)
    with pytest.raises(ValueError):
        result(["v"], [[1, 2]], False, RunLimits())
    with pytest.raises(ValueError):
        result(["v"], [[1]] * 1001, False, RunLimits())


def test_postcondition_differences_and_error_wording_are_material_only_when_semantic():
    from faultglass.models import CheckObservation

    left, right = observed([[1]]), observed([[1]])
    left.postconditions = [
        CheckObservation(
            name="state",
            status="result",
            value=result(["count"], [[1]], False, RunLimits()),
        )
    ]
    right.postconditions = [
        CheckObservation(
            name="state",
            status="result",
            value=result(["count"], [[2]], False, RunLimits()),
        )
    ]
    changed = difference(left, right)
    assert (
        changed.changedDimensions == ["postcondition.state"]
        and changed.kind == "postcondition"
    )
    left.postconditions = [
        CheckObservation(
            name="state",
            status="error",
            value=EngineError(category="UNKNOWN", detail="wording A"),
        )
    ]
    right.postconditions = [
        CheckObservation(
            name="state",
            status="error",
            value=EngineError(category="UNKNOWN", detail="wording B"),
        )
    ]
    assert difference(left, right) is None
    right.postconditions[0].value.category = "TYPE"
    assert difference(left, right)


def test_oracle_annotation_does_not_change_pair_divergence():
    from faultglass.comparison import assess_oracle
    from faultglass.models import Expectation, ExpectedResult, FaultCase

    case = FaultCase(
        schemaVersion=1,
        title="Expectation",
        setup=[],
        query="RETURN 1",
        observation=ObservationSpec(compareResult=True, ordering="unordered"),
    )
    pair = PairedObservation(baseline=observed([[1]]), target=observed([[2]]))
    original = difference(pair.baseline, pair.target).signature
    case.expectation = Expectation(
        kind="explicit_result", value=ExpectedResult(columns=["value"], rows=[[1]])
    )
    assert assess_oracle(case, pair) == {"baseline": "match", "target": "mismatch"}
    assert (
        compare(pair, engines_for("call-yield-c-rust"), case.observation).signature
        == original
    )
