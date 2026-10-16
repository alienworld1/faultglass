import ast
import json

from .comparison import material, result_key
from .matrix import engines_for
from .models import Result
from .normalize import normalize

TEMPLATE = '''"""Recorded behavioral coverage. Wire faultglass_repository_harness to your test suite.

The fixture must expose disposable_graph() as a context manager. Its graph provides
execute_setup(statement), observe(query, parameters, policy), and reset(). observe
returns a dictionary with status (result/error/timeout/crash), error (category and
normalizedCode), result (columns, rows, ordered), and selected postconditions.
Values are typed JSON: null/bool/int/float/string/list/map/node/relationship/path
using the recorded normalization policy; engine-local identities are excluded.
Unordered rows must be sorted by canonical JSON bytes, preserving duplicates.
Errors must remain distinct from health-check-confirmed crashes. reset must work
following errors, and exiting disposable_graph must release the disposable graph.
This is a repository adapter contract, not a drop-in destination harness.
"""
import pytest

CASE = {case}
EXPECTED = {expected}
PROVENANCE = {provenance}
ASSERTION_LIMIT = {limitation}


@pytest.fixture
def repository_harness(request):
    try:
        return request.getfixturevalue("faultglass_repository_harness")
    except pytest.FixtureLookupError:
        pytest.skip("Wire the faultglass_repository_harness fixture to a disposable repository graph.")


def test_recorded_behavior(repository_harness):
    if ASSERTION_LIMIT:
        pytest.skip(ASSERTION_LIMIT)
    with repository_harness.disposable_graph() as graph:
        try:
            for statement in CASE["setup"]:
                graph.execute_setup(statement)
            actual = graph.observe(CASE["query"], CASE["parameters"], CASE["observation"])
            assert actual["status"] != "crash", "The engine crashed instead of the recorded semantic behavior."
            if PROVENANCE["expectationBasis"] == "explicit_error":
                assert actual["status"] == "error"
                assert actual["error"]["category"] == EXPECTED["error"]["category"]
            elif PROVENANCE["expectationBasis"] == "explicit_result":
                assert actual["status"] == "result"
                assert actual["result"] == EXPECTED["result"]
            else:
                assert actual == EXPECTED, "Observed baseline compatibility behavior changed."
        finally:
            graph.reset()
'''


def regression_bytes(case, report, evidence):
    expected, basis, limitation = (
        material(report.observations.baseline, case.observation),
        "baseline_observation",
        None,
    )
    oracle = case.expectation
    if oracle and oracle.kind == "explicit_error":
        expected, basis = (
            {"status": "error", "error": {"category": oracle.errorCategory}},
            "explicit_error",
        )
    elif oracle and oracle.kind == "explicit_result":
        expected, basis = (
            {
                "status": "result",
                "result": result_key(
                    Result(
                        columns=oracle.value.columns,
                        rows=[[normalize(v) for v in row] for row in oracle.value.rows],
                        ordered=case.observation.ordering == "ordered",
                    )
                ),
            },
            "explicit_result",
        )
    if expected["status"] in {"crash", "timeout"} or expected.get("error", {}).get(
        "category"
    ) in {"UNKNOWN", "CRASH", "TIMEOUT"}:
        limitation, basis = (
            "No supported expected behavior was available for this assertion. Inspect the exact observations in report.md.",
            "unasserted",
        )
    provenance = {
        "expectationBasis": basis,
        "investigationId": evidence.investigationId,
        "engines": [e.model_dump() for e in engines_for(report.pairId)],
        "scope": evidence.profile.scope.model_dump(),
        "normalizationVersion": "typed-values-v1",
        "evidenceHashes": [
            evidence.sourceRef.sha256,
            evidence.stabilityRef.sha256,
            evidence.retainedVerificationRef.sha256,
        ],
    }
    code = TEMPLATE.format(
        case=repr(case.model_dump()),
        expected=repr(expected),
        provenance=repr(provenance),
        limitation=repr(limitation),
    ).encode()
    ast.parse(code)
    return code, basis


def report_bytes(
    case, report, evidence, conclusion, reduction, agent, interpretation, memory_key
):
    details = {
        "observed": {
            role: material(getattr(report.observations, role), case.observation)
            for role in ("baseline", "target")
        },
        "family": conclusion.model_dump(),
        "scope": evidence.profile.scope.model_dump(),
        "sourceRepeated": True,
        "retainedIndependentlyRepeated": evidence.sourceRef
        == evidence.retainedVerificationRef,
        "originalSize": reduction.originalSize.model_dump(),
        "retainedSize": reduction.currentSize.model_dump(),
        "reductionLimit": reduction.stopReason,
        "references": {
            k: getattr(evidence, k).model_dump()
            for k in (
                "sourceRef",
                "stabilityRef",
                "retainedCaseRef",
                "retainedVerificationRef",
            )
        },
        "candidates": [c.model_dump() for c in evidence.candidates],
        "unknowns": evidence.unknowns,
        "contradictions": evidence.contradictions,
        "proceduralEligibility": [
            {
                "probeId": p.probeId,
                "contribution": p.contribution,
                "resultRef": p.resultRef.model_dump(),
            }
            for p in evidence.profile.probes
        ],
        "memoryCommitKey": memory_key,
        "agent": agent.model_dump() if agent else None,
        "interpretation": interpretation.model_dump() if interpretation else None,
        "oracleAssessment": report.oracleAssessment,
    }
    basis = (
        "Explicit expectation; observed disagreement does not establish correctness."
        if case.expectation
        and case.expectation.kind in {"explicit_result", "explicit_error"}
        else "Observed baseline compatibility behavior; baseline is not universal truth."
    )
    text = (
        "# Recorded behavioral evidence\n\n"
        + basis
        + "\n\nSmallest case retained by the supported reductions. "
    )
    text += (
        "The retained case was not reduced.\n\n"
        if not reduction.acceptedCount
        else "This does not claim a global minimum.\n\n"
    )
    text += "Memory publication is separate. Check the saved investigation memory receipt using the commit key below; this sealed report does not claim that publication succeeded.\n\n"
    # Indented JSON keeps imported strings as report data.
    text += (
        "\n".join(
            "    " + line
            for line in json.dumps(details, ensure_ascii=True, indent=2).splitlines()
        )
        + "\n"
    )
    return text.encode()
