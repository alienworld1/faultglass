import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from faultglass.investigation_models import Status
from faultglass.jsonio import encode
from faultglass.matrix import engines_for
from faultglass.models import read_case
from faultglass.reduction_service import ReductionHandler


@pytest.mark.parametrize("divergence", [None, "changed-signature"])
def test_unstable_repeat_stops_before_any_candidate(monkeypatch, divergence):
    case = read_case(
        (Path(__file__).parents[1] / "fixtures/call-yield.faultglass.json").read_bytes()
    )
    engines = list(engines_for("call-yield-c-rust"))
    source = SimpleNamespace(
        engines=engines, referenceDivergence="original-signature", stable=False
    )
    checkpoint = SimpleNamespace(summary=SimpleNamespace(source=source))
    record = SimpleNamespace(
        reservation=SimpleNamespace(
            childId="repeat",
            purpose="stability",
            inputSha256=hashlib.sha256(encode(case.model_dump())).hexdigest(),
        ),
        snapshot=SimpleNamespace(status=Status.REDUCING),
    )
    handler = ReductionHandler(SimpleNamespace(store=SimpleNamespace(root=None)))
    monkeypatch.setattr(handler, "checkpoint", lambda _: checkpoint)
    monkeypatch.setattr(handler, "execution_data", lambda *_: encode(case.model_dump()))
    report = SimpleNamespace(
        outcome="reproduced" if divergence else "not_reproduced",
        divergence=divergence,
        caseContentHash=hashlib.sha256(encode(case.model_dump())).hexdigest(),
    )
    monkeypatch.setattr(
        "faultglass.reduction_service.load_evidence",
        lambda *_: (case, report, [], engines, "manifest"),
    )
    monkeypatch.setattr(handler, "graph_phase", lambda *_: None)
    publish = Mock(return_value=record)
    finish = Mock(return_value="stopped")
    monkeypatch.setattr(handler, "publish", publish)
    monkeypatch.setattr(handler, "finish", finish)
    assert handler.complete(record) == "stopped"
    assert not source.stable
    finish.assert_called_once_with(record, checkpoint, "unstable_source")
    assert publish.call_count == 1
