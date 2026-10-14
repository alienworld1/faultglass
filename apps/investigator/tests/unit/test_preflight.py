from types import SimpleNamespace

import pytest

from faultglass.errors import ExecutionFailure
from faultglass.matrix import engines_for
from faultglass.runner import verify_images


def test_mismatched_digest_is_rejected_before_container_creation():
    def forbidden_creation(*args, **kwargs):
        pytest.fail("Image preflight must not start an engine.")

    image = SimpleNamespace(
        attrs={
            "RepoDigests": ["falkordb/falkordb@sha256:" + "0" * 64],
            "Architecture": "amd64",
            "Os": "linux",
        }
    )
    client = SimpleNamespace(
        info=lambda: {"OSType": "linux", "Architecture": "amd64"},
        images=SimpleNamespace(get=lambda ref: image),
        containers=SimpleNamespace(create=forbidden_creation),
    )
    with pytest.raises(ExecutionFailure) as failure:
        verify_images(client, engines_for("call-yield-c-rust"))
    assert failure.value.code == "image_mismatch"
