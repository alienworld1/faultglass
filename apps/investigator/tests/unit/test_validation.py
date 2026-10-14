import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from faultglass.execution import main
from faultglass.models import read_case

BASE = json.loads(
    (Path(__file__).parents[1] / "fixtures/matching.faultglass.json").read_text()
)


@pytest.mark.parametrize(
    "change",
    [
        {"query": ""},
        {"schemaVersion": True},
        {"schemaVersion": 2},
        {"query": "RETURN 1; RETURN 2"},
        {"image": "unapproved"},
        {"setup": [""]},
        {"parameters": {"v": float("inf")}},
        {"query": "RETURN 'unterminated"},
        {"query": "RETURN 1 /* unterminated"},
        {"observation": {"compareResult": True, "ordering": "auto"}},
        {"expectation": {"kind": "explicit_error"}},
        {"expectation": {"kind": "none", "value": {"columns": [], "rows": []}}},
        {"observation": {"compareResult": False, "ordering": "unordered"}},
        {
            "observation": {
                "compareResult": True,
                "ordering": "unordered",
                "postconditions": [{"name": "state", "query": "CREATE (:N)"}],
            }
        },
        {
            "observation": {
                "compareResult": True,
                "ordering": "unordered",
                "postconditions": [{"name": "state", "query": "CALL db.labels()"}],
            }
        },
    ],
)
def test_unsafe_or_inconsistent_cases_fail(change):
    with pytest.raises((ValueError, ValidationError)):
        read_case(json.dumps({**BASE, **change}).encode())


@pytest.mark.parametrize(
    "query",
    [
        "RETURN 'a;b' AS value;",
        "RETURN `semi;colon`;",
        "RETURN 1 /* ; CREATE */",
        'RETURN "escaped\\";"',
        "RETURN 1 // ; second statement",
        "CALL db.labels() YIELD label MATCH (n)",
    ],
)
def test_statement_boundary_preserves_executable_bytes(query):
    value = read_case(json.dumps({**BASE, "query": query}).encode())
    assert value.query == query


def test_duplicate_json_fields_and_limits_fail():
    for data in [
        b'{"query":"RETURN 1","query":"RETURN 2"}',
        b'{"v":NaN}',
        b"x" * 262145,
    ]:
        with pytest.raises(ValueError):
            read_case(data)
    for change in [
        {"setup": ["RETURN 1"] * 33},
        {"query": 'RETURN "' + "x" * 16384 + '"'},
    ]:
        with pytest.raises(ValidationError):
            read_case(json.dumps({**BASE, **change}).encode())


def test_cli_invalid_input_and_unknown_pair_never_connect(monkeypatch, tmp_path):
    from faultglass import execution

    calls = []
    monkeypatch.setattr(execution, "docker_client", lambda: calls.append("connected"))
    case = tmp_path / "case.json"
    case.write_text(
        json.dumps({key: value for key, value in BASE.items() if key != "query"})
    )
    monkeypatch.setattr(
        "sys.argv", ["compare", "--case", str(case), "--pair", "call-yield-c-rust"]
    )
    assert main() == 2
    case.write_text(json.dumps(BASE))
    monkeypatch.setattr(
        "sys.argv", ["compare", "--case", str(case), "--pair", "unknown"]
    )
    assert main() == 2
    assert not calls
