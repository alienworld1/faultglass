import io
import urllib.error
from contextlib import contextmanager

import pytest

from faultglass.gemini import GeminiProvider
from faultglass.jsonio import encode
from faultglass.llm_provider import ProviderFailure

CITATION = {"text": "Observed a version-scoped difference.", "evidenceIds": ["a" * 64]}


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "private-unit-credential")
    monkeypatch.setenv("FAULTGLASS_GEMINI_MODEL", "gemini-2.5-flash-lite")
    monkeypatch.setenv("FAULTGLASS_INVESTIGATION_MODE", "agent")
    return GeminiProvider()


@pytest.mark.parametrize(
    "operation,value",
    [
        (
            "enrich_fingerprint",
            dict(observed=CITATION, interpretation=CITATION, unknown=CITATION),
        ),
        (
            "explain_family",
            dict(
                proposedName="Trailing required match",
                observed=CITATION,
                interpretation=CITATION,
                unknown=CITATION,
            ),
        ),
        (
            "narrate_investigation",
            dict(observed=CITATION, interpretation=CITATION, unknown=CITATION),
        ),
        (
            "suggest_reduction",
            dict(query="CALL db.labels() YIELD label MATCH (n)", reason=CITATION),
        ),
    ],
)
def test_structured_operations_validate_schema_citations_and_transport(
    provider, monkeypatch, operation, value
):
    @contextmanager
    def response(request, timeout):
        assert timeout == 5
        assert request.full_url.startswith("https://generativelanguage.googleapis.com/")
        assert b"private-unit-credential" not in request.data
        yield io.BytesIO(
            encode(
                {
                    "candidates": [
                        {"content": {"parts": [{"text": encode(value).decode()}]}}
                    ]
                }
            )
        )

    monkeypatch.setattr("urllib.request.urlopen", response)
    result = provider.generate(operation, {"evidenceIds": ["a" * 64]})
    assert result.model_dump() == value


@pytest.mark.parametrize(
    "failure,code",
    [
        (TimeoutError(), "provider_timeout"),
        (
            urllib.error.HTTPError("url", 429, "private detail", {}, None),
            "rate_limited",
        ),
        (ValueError("private detail"), "invalid_or_unavailable_output"),
    ],
)
def test_provider_failures_never_expose_raw_errors(
    provider, monkeypatch, failure, code
):
    def unavailable(*args, **kwargs):
        raise failure

    monkeypatch.setattr("urllib.request.urlopen", unavailable)
    with pytest.raises(ProviderFailure) as caught:
        provider.generate("enrich_fingerprint", {"evidenceIds": ["a" * 64]})
    assert str(caught.value) == code and "private" not in str(caught.value)


def test_application_and_response_caps_fail_closed(provider, monkeypatch):
    with pytest.raises(ProviderFailure, match="input_limit"):
        provider.generate("enrich_fingerprint", {"content": "x" * 32769})

    @contextmanager
    def response(*args, **kwargs):
        yield io.BytesIO(b" " * 8193)

    monkeypatch.setattr("urllib.request.urlopen", response)
    with pytest.raises(ProviderFailure, match="response_limit"):
        provider.generate("enrich_fingerprint", {"evidenceIds": ["a" * 64]})
