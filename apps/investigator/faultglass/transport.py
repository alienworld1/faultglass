import select
import struct
import time

from falkordb.graph import Graph
from redis.exceptions import ResponseError

from .errors import DeadlineExceeded, ExecutionFailure
from .jsonio import loads


class ExecTransport:
    def __init__(self, client, container, limits, pair_deadline):
        self.client, self.container, self.limits = client, container, limits
        self.pair_deadline = pair_deadline
        self.raw = []
        self.total = 0

    def command(self, *args, seconds=None):
        deadline = min(
            self.pair_deadline, time.monotonic() + (seconds or self.limits.querySeconds)
        )
        created = self.client.api.exec_create(
            self.container.id,
            ["redis-cli", "--json", "-h", "127.0.0.1", "-p", "6379", *map(str, args)],
            stdout=True,
            stderr=True,
        )
        attached = self.client.api.exec_start(created["Id"], socket=True)
        channel = getattr(attached, "_sock", attached)
        data = bytearray()
        wire = bytearray()
        complete = False
        try:
            channel.settimeout(max(0.01, deadline - time.monotonic()))
            while True:
                remaining = deadline - time.monotonic()
                if (
                    remaining <= 0
                    or not select.select([channel], [], [], max(0, remaining))[0]
                ):
                    raise DeadlineExceeded()
                chunk = channel.recv(4096)
                if not chunk:
                    complete = not wire
                    break
                wire.extend(chunk)
                if len(wire) + len(data) > self.limits.outputBytes + 4096:
                    raise ExecutionFailure(
                        "output_limit",
                        "capture",
                        "The output exceeded the comparison limit.",
                    )
                while len(wire) >= 8:
                    length = struct.unpack(">I", wire[4:8])[0]
                    if (
                        length > self.limits.outputBytes
                        or len(data) + length > self.limits.outputBytes
                    ):
                        raise ExecutionFailure(
                            "output_limit",
                            "capture",
                            "The output exceeded the comparison limit.",
                        )
                    if len(wire) < 8 + length:
                        break
                    data.extend(wire[8 : 8 + length])
                    del wire[: 8 + length]
        except TimeoutError as error:
            raise DeadlineExceeded() from error
        finally:
            attached.close()
            text = bytes(data).decode("utf-8", errors="strict")
            self.total += len(data)
            if self.total <= 2 * self.limits.outputBytes:
                self.raw.append(
                    {"command": list(args), "output": text, "captureComplete": complete}
                )
        if self.total > 2 * self.limits.outputBytes:
            raise ExecutionFailure(
                "output_limit",
                "capture",
                "The paired evidence exceeded its capture limit.",
            )
        status = self.client.api.exec_inspect(created["Id"])
        if status["ExitCode"] != 0:
            raise ExecutionFailure(
                "transport", "query", "The engine connection stopped unexpectedly."
            )
        if wire:
            raise ExecutionFailure(
                "transport", "capture", "The engine response was incomplete."
            )
        if text.startswith("error:"):
            detail = loads(text[6:])
            raise ResponseError(detail)
        return loads(text)

    def execute_command(self, *args):
        return self.command(*args)

    def graph(self):
        return Graph(self, "evidence")
