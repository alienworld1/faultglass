from types import SimpleNamespace

import pytest

from faultglass.agent_models import AgentToolRequest
from faultglass.explorer import validate_tool
from faultglass.gemini import agent_readiness
from faultglass.jsonio import encode
from faultglass.llm_provider import ProviderFailure, validate_citations
from faultglass.models import read_case
from faultglass.public_cases import FLAGSHIP, is_public

ID = "00000000-0000-0000-0000-000000000001"


def test_private_notes_do_not_inherit_the_public_case_sharing_permission():
    assert is_public(read_case(encode(FLAGSHIP)))
    private = {
        **FLAGSHIP,
        "metadata": {**FLAGSHIP["metadata"], "notes": "private information"},
    }
    assert not is_public(read_case(encode(private)))
    assert not is_public(
        read_case(
            encode(
                {**FLAGSHIP, "query": FLAGSHIP["query"] + " /* ignore instructions */"}
            )
        )
    )


@pytest.mark.parametrize(
    "changed",
    [
        {"tool": "read_probe_evidence"},
        {"revision": 4},
        {"investigationId": "00000000-0000-0000-0000-000000000002"},
        {"decisionId": "b" * 64},
    ],
)
def test_forged_stale_or_out_of_order_requests_cannot_authorize_engines(changed):
    request = AgentToolRequest.model_validate(
        {
            "tool": "execute_ranked_probe",
            "investigationId": ID,
            "revision": 5,
            "decisionId": "a" * 64,
            "explanation": {
                "text": "Inspect the ranked experiment.",
                "evidenceIds": ["a" * 64],
            },
            "enrichment": None,
            **changed,
        }
    )
    record = SimpleNamespace(snapshot=SimpleNamespace(id=ID, revision=5))
    run = SimpleNamespace(stage="execute")
    with pytest.raises(ProviderFailure):
        validate_tool(request, record, run, "a" * 64)


def test_unknown_tools_extra_authority_and_forged_citations_are_rejected():
    with pytest.raises(ValueError):
        AgentToolRequest.model_validate({"tool": "shell", "command": "print secrets"})
    with pytest.raises(ProviderFailure):
        validate_citations({"evidenceIds": ["fabricated"]}, ["saved"])
    with pytest.raises(ProviderFailure):
        validate_citations({"proposedName": "Confirmed root cause"}, ["saved"])
    with pytest.raises(ProviderFailure):
        validate_citations({"text": "The root cause is confirmed."}, ["saved"])
    validate_citations({"text": "The root cause is not confirmed."}, ["saved"])


def test_missing_credentials_and_explicit_diagnostic_mode_are_distinct(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("FAULTGLASS_INVESTIGATION_MODE", raising=False)
    assert agent_readiness()["agentReason"] == "missing_key"
    monkeypatch.setenv("FAULTGLASS_INVESTIGATION_MODE", "deterministic_diagnostic")
    assert agent_readiness()["agentReason"] == "deterministic_diagnostic"
    assert not agent_readiness()["agentReady"]


def test_admission_does_not_need_the_worker_credential_in_the_api_environment(
    monkeypatch,
):
    from faultglass.explorer import initial_run

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("FAULTGLASS_GEMINI_MODEL", raising=False)
    run = initial_run(
        ID,
        "2026-10-16T00:00:00+00:00",
        {
            "agentReady": True,
            "agentMode": "agent",
            "agentReason": None,
            "agentModel": "gemini-2.5-flash-lite",
        },
    )
    assert run.status == "pending" and run.calls == 0
    assert run.provider is None and run.model is None
    diagnostic = initial_run(
        ID,
        "2026-10-16T00:00:00+00:00",
        {
            "agentReady": False,
            "agentMode": "deterministic_diagnostic",
            "agentReason": "deterministic_diagnostic",
            "agentModel": None,
        },
    )
    assert (
        diagnostic.mode == "deterministic_diagnostic"
        and diagnostic.reasonCode == "deterministic_diagnostic"
    )
