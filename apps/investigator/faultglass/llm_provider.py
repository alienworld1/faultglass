import re
from typing import Protocol

from .agent_models import (
    AgentInterpretation,
    AgentToolRequest,
    FamilyExplanation,
    FingerprintEnrichment,
    InvestigationNarrative,
    ReductionSuggestion,
)

OPERATIONS = {
    "request_tool": AgentToolRequest,
    "enrich_fingerprint": FingerprintEnrichment,
    "explain_family": FamilyExplanation,
    "narrate_investigation": InvestigationNarrative,
    "suggest_reduction": ReductionSuggestion,
    "interpretation": AgentInterpretation,
}


class ProviderFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class LLMProvider(Protocol):
    model: str

    def generate(self, operation: str, context: dict) -> object: ...


def validate_citations(value, evidence_ids):
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "evidenceIds" and (not child or set(child) - set(evidence_ids)):
                raise ProviderFailure("invalid_citation")
            if key == "proposedName" and any(
                term in child.lower()
                for term in ("root cause", "confirmed", "proven", "vulnerability")
            ):
                raise ProviderFailure("unsupported_claim")
            if key == "text" and re.search(
                r"\b(?:confirmed|proven|definitive)\s+(?:root\s+)?cause\b|\broot cause\s+(?:is|has been)\s+(?:confirmed|proven)\b|\bAI confidence\b|\b(?:bug|fault) probability\b",
                child,
                re.I,
            ):
                raise ProviderFailure("unsupported_claim")
            validate_citations(child, evidence_ids)
    elif isinstance(value, list):
        for child in value:
            validate_citations(child, evidence_ids)
