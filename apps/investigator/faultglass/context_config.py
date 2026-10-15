import os
import re
from pathlib import Path

from pydantic import Field, field_validator

from .models import Contract


class ContextConfig(Contract):
    host: str = Field(default="127.0.0.1", min_length=1, max_length=253)
    port: int = Field(default=6380, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=512, repr=False)
    password: str | None = Field(default=None, max_length=4096, repr=False)
    graph: str = "faultglass__falkordb_core"
    artifact_root: Path = Path("./evidence")

    @field_validator("graph")
    @classmethod
    def workspace_graph(cls, value):
        if value != "faultglass__falkordb_core" and not re.fullmatch(
            r"faultglass__test_[a-z0-9_]{1,64}", value
        ):
            raise ValueError("Choose the configured investigation memory workspace.")
        return value

    @classmethod
    def from_environment(cls):
        return cls(
            host=os.environ.get("FAULTGLASS_CONTEXT_HOST", "127.0.0.1"),
            port=int(os.environ.get("FAULTGLASS_CONTEXT_PORT", "6380")),
            username=os.environ.get("FAULTGLASS_CONTEXT_USERNAME"),
            password=os.environ.get("FAULTGLASS_CONTEXT_PASSWORD"),
            graph=os.environ.get(
                "FAULTGLASS_CONTEXT_GRAPH", "faultglass__falkordb_core"
            ),
            artifact_root=Path(
                os.environ.get("FAULTGLASS_ARTIFACT_ROOT", "./evidence")
            ),
        )
