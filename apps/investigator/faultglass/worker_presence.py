import fcntl
import os
import threading
import time
from pathlib import Path

from .artifacts import atomic_write, open_private_root
from .context_artifacts import read_file
from .context_errors import ContextError
from .gemini import agent_readiness
from .jsonio import digest, encode, loads


class WorkerPresence:
    def __init__(self, config):
        self.scope = digest(
            {
                "root": str(Path(config.artifact_root).absolute()),
                "host": config.host,
                "port": config.port,
                "graph": config.graph,
            }
        )
        self.stop = threading.Event()
        self.ready = False

    def __enter__(self):
        _, self.fd = open_private_root(Path("/tmp") / f"faultglass-{os.getuid()}")
        self.lock = os.open(
            "worker.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=self.fd
        )
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.lock)
            os.close(self.fd)
            raise ContextError(
                "An investigation worker is already running for this account."
            ) from None
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)
        self.thread.start()
        return self

    def _heartbeat(self):
        while not self.stop.is_set():
            atomic_write(
                self.fd,
                "worker.json",
                encode(
                    {
                        "scope": self.scope,
                        "at": time.time(),
                        "ready": self.ready,
                        "agent": agent_readiness(),
                    }
                ),
            )
            self.stop.wait(2)

    def __exit__(self, *args):
        self.ready = False
        self.stop.set()
        self.thread.join(3)
        atomic_write(
            self.fd,
            "worker.json",
            encode({"scope": self.scope, "at": time.time(), "ready": False}),
        )
        os.close(self.lock)
        os.close(self.fd)


def worker_ready(config):
    presence = WorkerPresence(config)
    _, fd = open_private_root(Path("/tmp") / f"faultglass-{os.getuid()}")
    try:
        data = loads(read_file(fd, "worker.json", 4096))
        return (
            data["scope"] == presence.scope
            and data["ready"] is True
            and 0 <= time.time() - data["at"] < 8
        )
    except (OSError, ValueError, KeyError):
        return False
    finally:
        os.close(fd)


def worker_agent_readiness(config):
    presence = WorkerPresence(config)
    _, fd = open_private_root(Path("/tmp") / f"faultglass-{os.getuid()}")
    try:
        data = loads(read_file(fd, "worker.json", 4096))
        if (
            data["scope"] == presence.scope
            and data["ready"] is True
            and 0 <= time.time() - data["at"] < 8
        ):
            agent = data.get("agent")
            if isinstance(agent, dict) and set(agent) == {
                "agentReady",
                "agentMode",
                "agentReason",
                "agentModel",
            }:
                return agent
    except (OSError, ValueError, KeyError):
        pass
    finally:
        os.close(fd)
    return {
        "agentReady": False,
        "agentMode": "agent",
        "agentReason": "worker_unavailable",
        "agentModel": None,
    }
