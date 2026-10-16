import pytest

from faultglass.agent_models import FingerprintEnrichment
from faultglass.citations import reference_context, resolve_citations
from faultglass.llm_provider import ProviderFailure


def test_reference_handles_preserve_exact_evidence_and_model_text():
    context = {"evidenceIds": ["a" * 64, "b" * 64, "a" * 64], "facts": {"value": 1}}
    wire = reference_context(context)
    assert wire["evidenceIds"] == ["r1", "r2"]
    assert wire["evidenceReferences"] == {"r1": "a" * 64, "r2": "b" * 64}
    assert context == {
        "evidenceIds": ["a" * 64, "b" * 64, "a" * 64],
        "facts": {"value": 1},
    }
    citation = {"text": "r1 is also a variable name.", "evidenceIds": ["r1"]}
    output = FingerprintEnrichment(
        observed=citation,
        interpretation={**citation, "evidenceIds": ["r2"]},
        unknown=citation,
    )
    resolved = resolve_citations(output, wire["evidenceReferences"])
    assert resolved.observed.evidenceIds == ["a" * 64]
    assert resolved.interpretation.evidenceIds == ["b" * 64]
    assert resolved.unknown.evidenceIds == ["a" * 64]
    assert resolved.observed.text == citation["text"]
    assert output.observed.evidenceIds == ["r1"]


@pytest.mark.parametrize("identity", ["r01", "r3", "a" * 64])
def test_unknown_or_altered_handles_are_never_repaired(identity):
    citation = {"text": "Inspect the recorded evidence.", "evidenceIds": [identity]}
    output = FingerprintEnrichment(
        observed=citation, interpretation=citation, unknown=citation
    )
    with pytest.raises(ProviderFailure, match="invalid_citation"):
        resolve_citations(output, {"r1": "a" * 64})
