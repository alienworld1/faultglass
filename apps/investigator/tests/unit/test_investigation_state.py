import pytest

from faultglass.investigation_models import TERMINAL, Status, transition


def test_unavailable_analysis_cannot_finish():
    for before, after in (
        (Status.PROBING, Status.REDUCING),
        (Status.EXPORTING, Status.COMPLETE),
    ):
        with pytest.raises(ValueError, match="unavailable"):
            transition(before, after)
        transition(before, after, downstream=True)


def test_terminal_states_are_read_only():
    for before in TERMINAL:
        for after in Status:
            with pytest.raises(ValueError):
                transition(before, after, downstream=True)


def test_reproduced_is_evidence_not_lifecycle():
    with pytest.raises(ValueError):
        Status("REPRODUCED")
    transition(Status.REPRODUCING, Status.PLANNING)
    transition(Status.PROBING, Status.PLANNING)
    transition(Status.PLANNING, Status.UNRESOLVED)
