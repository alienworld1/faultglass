import sys

import pytest

from faultglass import probe


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["plan"],
        ["execute", "--evidence-id", "../escape"],
        ["inspect", "--evidence-id", "invalid"],
        ["commit"],
    ],
)
def test_invalid_probe_arguments_exit_before_configuration_or_io(
    arguments, monkeypatch, capsys
):
    def forbidden():
        pytest.fail("Invalid arguments must fail before configuration or engines.")

    monkeypatch.setattr(probe.ContextConfig, "from_environment", forbidden)
    monkeypatch.setattr(sys, "argv", ["probe", *arguments])
    with pytest.raises(SystemExit) as error:
        probe.main()
    assert error.value.code == 2
    output = capsys.readouterr()
    assert not output.out and "usage:" in output.err and "Traceback" not in output.err
