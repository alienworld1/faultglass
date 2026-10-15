import sys

import pytest

from faultglass import context


@pytest.mark.parametrize(
    "arguments,message",
    [
        (
            ["record", "--evidence-id", "../evidence"],
            "Choose a valid saved comparison ID.",
        ),
        (["inspect", "--evidence-id", "broken"], "Choose a valid saved comparison ID."),
        (["history", "--fingerprint", "INVALID"], "Choose a valid fingerprint ID."),
        (
            ["history", "--fingerprint", "a" * 64, "--limit", "101"],
            "Choose a history limit from 1 to 100.",
        ),
    ],
)
def test_invalid_arguments_fail_before_configuration_or_repository_io(
    monkeypatch, capsys, arguments, message
):
    def forbidden():
        pytest.fail(
            "Invalid arguments must fail before accessing memory configuration."
        )

    monkeypatch.setattr(context.ContextConfig, "from_environment", forbidden)
    monkeypatch.setattr(sys, "argv", ["context", *arguments])
    with pytest.raises(SystemExit) as error:
        context.main()
    assert error.value.code == 2
    output = capsys.readouterr()
    assert message in output.err and not output.out and "Traceback" not in output.err
