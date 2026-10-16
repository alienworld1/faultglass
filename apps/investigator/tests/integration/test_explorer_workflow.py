from contextlib import suppress
from typing import ClassVar
from uuid import uuid4

import pytest

from faultglass.agent_models import (
    AgentInterpretation,
    AgentToolRequest,
    FingerprintEnrichment,
)
from faultglass.context_artifacts import read_reference
from faultglass.context_config import ContextConfig
from faultglass.explorer import load_run
from faultglass.graph_repository import GraphRepository
from faultglass.investigation_models import TERMINAL, Admission, Status
from faultglass.jsonio import encode, loads
from faultglass.public_cases import FLAGSHIP
from faultglass.worker import Worker

pytestmark = pytest.mark.docker


class ScriptedProvider:
    model = "gemini-isolated-fixture"
    calls: ClassVar[list] = []

    def generate(self, operation, context):
        self.calls.append((operation, context))
        citation = {
            "text": "Inspect the recorded version-scoped behavior.",
            "evidenceIds": context["evidenceIds"][:1],
        }
        explanation = dict(observed=citation, interpretation=citation, unknown=citation)
        if operation == "interpretation":
            return AgentInterpretation.model_validate(
                {
                    "family": {
                        "proposedName": "Trailing required match",
                        **explanation,
                    },
                    "narrative": explanation,
                }
            )
        return AgentToolRequest.model_validate(
            {
                "tool": context["allowedTool"],
                "investigationId": context["investigationId"],
                "revision": context["revision"],
                "decisionId": context["decisionId"],
                "explanation": citation,
                "enrichment": FingerprintEnrichment(**explanation).model_dump()
                if context["enrichmentRequired"]
                else None,
            }
        )


def test_durable_agent_requests_precede_execution_and_reuse_saved_response(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEMINI_API_KEY", "isolated-provider-fixture")
    monkeypatch.setenv("FAULTGLASS_GEMINI_MODEL", ScriptedProvider.model)
    monkeypatch.setenv("FAULTGLASS_INVESTIGATION_MODE", "agent")
    monkeypatch.setattr("faultglass.explorer.GeminiProvider", ScriptedProvider)
    ScriptedProvider.calls = []
    repo = GraphRepository(
        ContextConfig(graph="faultglass__test_" + uuid4().hex, artifact_root=tmp_path)
    )
    repo.ensure_schema()
    worker = Worker(repo)
    record, _ = worker.store.admit(
        Admission(caseFile=encode(FLAGSHIP).decode(), pairId="call-yield-c-rust"),
        str(uuid4()),
    )
    original = worker.store.commit
    interrupted = []

    def after_saved_response(*args, **kwargs):
        fresh = original(*args, **kwargs)
        run = load_run(worker.store, fresh)
        if (
            not interrupted
            and run.stage == "execute"
            and run.turns[-1].responseRef
            and not any(r.requestId == run.turns[-1].id for r in run.results)
        ):
            interrupted.append(run.turns[-1].id)
            raise KeyboardInterrupt()
        return fresh

    monkeypatch.setattr(worker.store, "commit", after_saved_response)
    try:
        for _ in range(120):
            record = worker.store.load(record.snapshot.id)
            if record.snapshot.status in TERMINAL:
                break
            with suppress(KeyboardInterrupt):
                worker.step(record.snapshot.id)
        run = load_run(worker.store, record)
        assert interrupted and run.status == "completed" and run.calls == 10
        assert len(ScriptedProvider.calls) == 10
        assert (
            record.snapshot.status == Status.COMPLETE
            and record.snapshot.conclusion.interpretationRef
        )
        assert len(run.outputRefs) == 2
        assert [r.tool for r in run.results].count("execute_ranked_probe") == 2
        assert record.snapshot.budget.reservedProbes == 2
        for receipt in worker.store.history(record):
            if receipt.reservation and receipt.reservation.purpose == "probe":
                ledger = load_run(worker.store, receipt)
                assert any(r.tool == "execute_ranked_probe" for r in ledger.results)
        assert all(t.inputHash and t.responseRef for t in run.turns)
        assert run.promptVersion == "explorer-v2"
        for turn in run.turns:
            assert turn.inputRef and turn.providerResponseRef
            context = loads(read_reference(worker.store.root, turn.inputRef))
            provider_output = loads(
                read_reference(worker.store.root, turn.providerResponseRef)
            )
            canonical = loads(read_reference(worker.store.root, turn.responseRef))
            if "explanation" in provider_output:
                handles = provider_output["explanation"]["evidenceIds"]
                assert canonical["explanation"]["evidenceIds"] == [
                    context["evidenceReferences"][handle] for handle in handles
                ]
    finally:
        repo.graph.delete()
        repo.close()
