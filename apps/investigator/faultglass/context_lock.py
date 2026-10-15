import fcntl
import os
import time
from pathlib import Path

from .artifacts import open_private_root
from .context_errors import ContextError


class ContextLease:
    def __enter__(self):
        _, root_fd = open_private_root(Path("/tmp") / f"faultglass-{os.getuid()}")
        try:
            self.fd = os.open(
                "context.lock",
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                0o600,
                dir_fd=root_fd,
            )
        finally:
            os.close(root_fd)
        deadline = time.monotonic() + 10
        try:
            while True:
                try:
                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return self
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise ContextError(
                            "Investigation memory is busy. Try saving again shortly."
                        ) from None
                    time.sleep(0.05)
        except BaseException:
            os.close(self.fd)
            raise

    def __exit__(self, *args):
        os.close(self.fd)
