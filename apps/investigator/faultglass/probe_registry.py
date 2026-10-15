from typing import Literal

from pydantic import field_validator, model_validator

from .feature_catalog import FEATURE_IDS
from .graph_properties import Short, Text
from .jsonio import digest
from .models import Contract, Hash


class ProbeDefinition(Contract):
    id: Short
    type: Short
    template_version: Short
    description: Text
    target_feature_ids: list[str]
    cost_class: Literal["small", "medium", "large"]
    enabled: bool
    rule_identity: Short
    definition_sha256: Hash

    @field_validator("target_feature_ids")
    @classmethod
    def features(cls, value):
        if not value or value != sorted(set(value)) or set(value) - set(FEATURE_IDS):
            raise ValueError("Use sorted supported target features.")
        return value

    @model_validator(mode="after")
    def identity(self):
        content = self.model_dump(exclude={"definition_sha256"})
        if (
            self.id != self.type + ":" + self.template_version
            or digest(content) != self.definition_sha256
        ):
            raise ValueError("The experiment definition does not match its identity.")
        return self


def definition(kind, description):
    content = dict(
        id=kind + ":v1",
        type=kind,
        template_version="v1",
        description=description,
        target_feature_ids=["CALL", "MATCH", "YIELD"],
        cost_class="small",
        enabled=True,
        rule_identity="terminal-call-yield-node-v1:" + kind,
    )
    return ProbeDefinition(**content, definition_sha256=digest(content))


REGISTRY = tuple(
    sorted(
        [
            definition(
                "REPLACE_TERMINAL_MATCH_WITH_OPTIONAL",
                "Replace the terminal required match with an optional match.",
            ),
            definition(
                "INSERT_WITH_BEFORE_TERMINAL_MATCH",
                "Carry the yielded binding through a projection before the terminal match.",
            ),
        ],
        key=lambda item: item.id,
    )
)
REGISTRY_SHA256 = digest([item.model_dump() for item in REGISTRY])
