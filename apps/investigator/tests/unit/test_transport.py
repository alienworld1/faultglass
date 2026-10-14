import socket
import struct
from types import SimpleNamespace

import pytest

from faultglass.adapter import checked_result
from faultglass.errors import ExecutionFailure
from faultglass.models import RunLimits
from faultglass.transport import ExecTransport


def test_wire_capture_rejects_oversized_frames_before_reading_body():
    channel, producer = socket.socketpair()
    try:
        producer.sendall(b"\x01\x00\x00\x00" + struct.pack(">I", 100000000))
        api = SimpleNamespace(
            exec_create=lambda *args, **kwargs: {"Id": "exec"},
            exec_start=lambda *args, **kwargs: channel,
        )
        transport = ExecTransport(
            SimpleNamespace(api=api),
            SimpleNamespace(id="engine"),
            RunLimits(),
            float("inf"),
        )
        with pytest.raises(ExecutionFailure, match="output exceeded"):
            transport.command("PING")
        assert transport.raw[0]["captureComplete"] is False
        assert transport.total == 0
    finally:
        producer.close()
        channel.close()


@pytest.mark.parametrize(
    "cell",
    [[0, 1], [12, [1.0]], [3, 1.5], [4, 1], [8, []], [10, ["a", [3, 1], "a", [3, 2]]]],
)
def test_unsupported_or_ambiguous_engine_values_fail_normalization(cell):
    with pytest.raises(ValueError):
        checked_result(None, [[[1, "v"]], [[cell]], []], False, RunLimits())
