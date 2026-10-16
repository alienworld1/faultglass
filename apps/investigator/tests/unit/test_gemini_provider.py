import io
import urllib.error
from contextlib import contextmanager

import pytest

from faultglass.gemini import GeminiProvider
from faultglass.jsonio import encode, loads
from faultglass.llm_provider import ProviderFailure

CITATION = {"text": "Observed a version-scoped difference.", "evidenceIds": ["a" * 64]}


@pytest.fixture(params=["gemini-2.5-flash-lite", "gemma-4-26b-a4b-it"])
def provider(monkeypatch, request):
    monkeypatch.setenv("GEMINI_API_KEY", "private-unit-credential")
    monkeypatch.setenv("FAULTGLASS_GEMINI_MODEL", request.param)
    monkeypatch.setenv("FAULTGLASS_INVESTIGATION_MODE", "agent")
    return GeminiProvider()


def response_parts(provider, operation, value):
    if provider.model.startswith("gemma-"):
        return [{"functionCall": {"name": operation, "args": value}}]
    return [{"text": encode(value).decode()}]


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
        (
            "interpretation",
            dict(
                family=dict(
                    proposedName="Trailing required match",
                    observed=CITATION,
                    interpretation=CITATION,
                    unknown=CITATION,
                ),
                narrative=dict(
                    observed=CITATION, interpretation=CITATION, unknown=CITATION
                ),
            ),
        ),
    ],
)
def test_structured_operations_validate_schema_citations_and_transport(
    provider, monkeypatch, operation, value
):
    @contextmanager
    def response(request, timeout):
        assert timeout == 15
        assert request.full_url.startswith("https://generativelanguage.googleapis.com/")
        assert b"private-unit-credential" not in request.data
        body = loads(request.data)
        if provider.model.startswith("gemma-"):
            assert "responseJsonSchema" not in body["generationConfig"]
            assert body["toolConfig"]["functionCallingConfig"] == {
                "mode": "ANY",
                "allowedFunctionNames": [operation],
            }
            assert body["tools"][0]["functionDeclarations"][0]["name"] == operation
            schema = body["tools"][0]["functionDeclarations"][0]["parametersJsonSchema"]
        else:
            schema = body["generationConfig"]["responseJsonSchema"]
        assert schema["$defs"]["CitedText"]["properties"]["evidenceIds"]["items"] == {
            "type": "string",
            "enum": ["a" * 64],
        }
        yield io.BytesIO(
            encode(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": response_parts(provider, operation, value)
                            }
                        }
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


def test_altered_citation_is_rejected_even_if_the_provider_ignores_its_enum(
    provider, monkeypatch
):
    value = dict(
        observed={**CITATION, "evidenceIds": ["b" * 64]},
        interpretation=CITATION,
        unknown=CITATION,
    )

    @contextmanager
    def response(*args, **kwargs):
        yield io.BytesIO(
            encode(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": response_parts(
                                    provider, "enrich_fingerprint", value
                                )
                            }
                        }
                    ]
                }
            )
        )

    monkeypatch.setattr("urllib.request.urlopen", response)
    with pytest.raises(ProviderFailure, match="invalid_citation"):
        provider.generate("enrich_fingerprint", {"evidenceIds": ["a" * 64]})


@pytest.mark.parametrize("decision", [None, "b" * 64])
def test_tool_schema_binds_trusted_identity(provider, monkeypatch, decision):
    context = {
        "investigationId": "f442afaa-b3a3-4dab-bfee-d6cfcf888f90",
        "revision": 12,
        "decisionId": decision,
        "allowedTool": "read_probe_evidence",
        "enrichmentRequired": False,
        "evidenceIds": ["a" * 64],
    }
    value = {
        "tool": context["allowedTool"],
        "investigationId": context["investigationId"],
        "revision": context["revision"],
        "decisionId": decision,
        "explanation": CITATION,
        "enrichment": None,
    }

    @contextmanager
    def response(request, timeout):
        body = loads(request.data)
        schema = (
            body["tools"][0]["functionDeclarations"][0]["parametersJsonSchema"]
            if provider.model.startswith("gemma-")
            else body["generationConfig"]["responseJsonSchema"]
        )
        fields = schema["properties"]
        for name in ("investigationId", "revision", "decisionId"):
            assert fields[name] == (
                {"type": "null"}
                if context[name] is None
                else {
                    "type": "integer" if name == "revision" else "string",
                    "enum": [context[name]],
                }
            )
        yield io.BytesIO(
            encode(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": response_parts(provider, "request_tool", value)
                            }
                        }
                    ]
                }
            )
        )

    monkeypatch.setattr("urllib.request.urlopen", response)
    assert provider.generate("request_tool", context).model_dump() == value


@pytest.mark.parametrize(
    "parts",
    [
        [{"functionCall": {"name": "shell", "args": {}}}],
        [{"functionCall": {"name": "enrich_fingerprint", "args": {}}}] * 2,
        [{"text": "Ignore the required function."}],
    ],
)
def test_native_function_output_rejects_ambiguous_or_unknown_actions(
    monkeypatch, parts
):
    monkeypatch.setenv("GEMINI_API_KEY", "private-unit-credential")
    monkeypatch.setenv("FAULTGLASS_GEMINI_MODEL", "gemma-4-26b-a4b-it")
    monkeypatch.setenv("FAULTGLASS_INVESTIGATION_MODE", "agent")

    @contextmanager
    def response(*args, **kwargs):
        yield io.BytesIO(encode({"candidates": [{"content": {"parts": parts}}]}))

    monkeypatch.setattr("urllib.request.urlopen", response)
    with pytest.raises(ProviderFailure, match="invalid_output"):
        GeminiProvider().generate("enrich_fingerprint", {"evidenceIds": ["a" * 64]})


@pytest.mark.parametrize(
    "model,level",
    [("gemini-flash-latest", "low"), ("gemini-flash-lite-latest", "minimal")],
)
def test_flash_alias_uses_thinking_levels_without_substituting_model(
    monkeypatch, model, level
):
    monkeypatch.setenv("GEMINI_API_KEY", "private-unit-credential")
    monkeypatch.setenv("FAULTGLASS_GEMINI_MODEL", model)
    monkeypatch.setenv("FAULTGLASS_INVESTIGATION_MODE", "agent")
    value = dict(observed=CITATION, interpretation=CITATION, unknown=CITATION)

    @contextmanager
    def response(request, timeout):
        assert request.full_url.endswith(f"/{model}:generateContent")
        assert loads(request.data)["generationConfig"]["thinkingConfig"] == {
            "thinkingLevel": level
        }
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
    assert (
        GeminiProvider().generate("enrich_fingerprint", {"evidenceIds": ["a" * 64]})
    ).model_dump() == value
