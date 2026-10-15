from pathlib import Path

import pytest

from faultglass.jsonio import encode, loads
from faultglass.models import read_case
from faultglass.probe_registry import REGISTRY
from faultglass.probe_transforms import transform

BASE = loads(
    (Path(__file__).parents[1] / "fixtures/call-yield.faultglass.json").read_bytes()
)


@pytest.mark.parametrize(
    "query",
    [
        "CALL db.labels() YIELD label\nMATCH (n)",
        "/* MATCH */ CALL other.proc() // YIELD\nYIELD value /* comment */ MATCH (node); // end",
        "CALL `other`.`proc`('MATCH (n)', 2) YIELD `a``b` MATCH (`node`)",
        "call foo() yield x match (y)",
    ],
)
def test_bounded_edits_preserve_every_other_field_and_source_byte(query):
    case = read_case(encode({**BASE, "query": query}))
    for definition in REGISTRY:
        output, edit, reason = transform(case, definition)
        assert reason == "applicable"
        assert output.model_dump(exclude={"query"}) == case.model_dump(
            exclude={"query"}
        )
        assert output.query == query[: edit.start] + edit.after + query[edit.end :]
        assert query[edit.start : edit.end] == edit.before
        assert transform(case, definition) == (output, edit, reason)


@pytest.mark.parametrize(
    "query",
    [
        "CALL db.labels() YIELD * MATCH (n)",
        "CALL db.labels() YIELD x, y MATCH (n)",
        "CALL db.labels() YIELD x AS y MATCH (n)",
        "CALL { RETURN 1 } YIELD x MATCH (n)",
        "CALL db.labels() YIELD x MATCH (n:N)",
        "CALL db.labels() YIELD x MATCH (n {a:1})",
        "CALL db.labels() YIELD x MATCH (n)-[]->(m)",
        "CALL db.labels() YIELD x MATCH (n) WHERE true",
        "CALL db.labels() YIELD x MATCH (n) RETURN n",
        "CALL db.labels() YIELD x MATCH ($n)",
        "CALL db.labels() YIELD x MATCH (n) UNION MATCH (m)",
        "CALL foo(') YIELD x MATCH (n)') YIELD x MATCH (n) RETURN x",
        "CALL foo(bar()) YIELD x MATCH (n)",
    ],
)
def test_unsupported_shapes_never_produce_an_executable_case(query):
    case = read_case(encode({**BASE, "query": query}))
    for definition in REGISTRY:
        assert transform(case, definition) == (None, None, "unsupported_shape")
