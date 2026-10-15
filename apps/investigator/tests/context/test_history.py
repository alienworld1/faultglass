from datetime import UTC, datetime
from pathlib import Path

import pytest

from faultglass.comparison import COMPARISON_VERSION
from faultglass.context_errors import ContextError
from faultglass.context_models import VersionScope
from faultglass.jsonio import encode

pytestmark = pytest.mark.context


def install_history(repository, receipt, suffix="a", scope=None):
    assert repository.config.graph.startswith("faultglass__test_")
    context = repository.get_investigation_context(receipt.investigation_id)
    scope = scope or VersionScope(
        baseline=context.runs[0].engine.properties["id"],
        target=context.runs[1].engine.properties["id"],
        comparison_version=COMPARISON_VERSION,
    )
    reference = context.investigation.properties["report_artifact_ref"]
    params = {
        "investigation_id": receipt.investigation_id,
        "family_id": "synthetic-family-" + suffix,
        "probe_id": "synthetic-probe-" + suffix,
        "now": datetime.now(UTC).isoformat(),
        "reference": reference,
        "scope": encode(scope.model_dump()).decode(),
        **{
            name: "synthetic-" + name + "-" + suffix
            for name in (
                "target_edge",
                "feature_a_edge",
                "feature_b_edge",
                "effective_edge",
                "classification_edge",
            )
        },
    }
    repository.graph.query(
        Path(__file__).with_name("synthetic-history.cypher").read_text(),
        params,
        timeout=2000,
    )
    return scope


def test_real_multihop_history_is_bounded_deduplicated_and_changes_with_graph(
    repository, completed_evidence
):
    _, reports = completed_evidence
    receipt = repository.record_seed_context(reports[0].runId)
    assert not repository.get_fingerprint_history(receipt.fingerprint_id).candidates
    scope = install_history(repository, receipt)
    history = repository.get_fingerprint_history(receipt.fingerprint_id, scope=scope)
    assert len(history.candidates) == 1
    candidate = history.candidates[0]
    assert candidate.feature_ids == ["CALL", "YIELD"] and candidate.feature_overlap == 2
    assert candidate.attempts == 4 and candidate.successes == 3
    assert candidate.exact_pair_match
    assert len(candidate.supporting_episodes) == 1
    assert (
        candidate.supporting_episodes[0].investigation.properties["id"]
        == receipt.investigation_id
    )
    assert not repository.get_fingerprint_history(
        receipt.fingerprint_id, exclude_id=receipt.investigation_id
    ).candidates
    reversed_scope = VersionScope(
        baseline=scope.target,
        target=scope.baseline,
        comparison_version=scope.comparison_version,
    )
    assert (
        not repository.get_fingerprint_history(
            receipt.fingerprint_id, scope=reversed_scope
        )
        .candidates[0]
        .exact_pair_match
    )
    cross_scope = scope.model_copy(update={"target": "0" * 64})
    assert (
        not repository.get_fingerprint_history(
            receipt.fingerprint_id, scope=cross_scope
        )
        .candidates[0]
        .exact_pair_match
    )
    # Duplicate optional joins must not multiply feature counts or supporting episodes.
    repository.graph.query(
        "MATCH (f:FaultFamily {id:'synthetic-family-a'})-[e:INVOLVES_FEATURE]->(x:Feature {id:'CALL'}) CREATE (f)-[copy:INVOLVES_FEATURE]->(x) SET copy=properties(e),copy.id='synthetic-extra-feature'"
    )
    assert (
        repository.get_fingerprint_history(receipt.fingerprint_id)
        .candidates[0]
        .feature_overlap
        == 2
    )
    repository.graph.query(
        "MATCH (d:Divergence)-[e:MATCHES_FAMILY]->(f:FaultFamily) CREATE (d)-[copy:MATCHES_FAMILY]->(f) SET copy=properties(e),copy.id='synthetic-extra-classification'"
    )
    assert (
        len(
            repository.get_fingerprint_history(receipt.fingerprint_id)
            .candidates[0]
            .supporting_episodes
        )
        == 1
    )
    repository.graph.query(
        "MATCH (:FaultFamily)-[e:INVOLVES_FEATURE]->(:Feature {id:'YIELD'}) DELETE e"
    )
    assert repository.get_fingerprint_history(receipt.fingerprint_id).candidates[
        0
    ].feature_ids == ["CALL"]
    repository.graph.query("MATCH (:FaultFamily)-[e:INVOLVES_FEATURE]->() DELETE e")
    assert not repository.get_fingerprint_history(receipt.fingerprint_id).candidates
    repository.graph.query(
        "MATCH (f:FaultFamily {id:'synthetic-family-a'}),(x:Feature {id:'CALL'}) CREATE (f)-[:INVOLVES_FEATURE {id:'synthetic-restored',created_at:$now,source_kind:'verified_classification',source_id:$ref}]->(x)",
        {
            "now": datetime.now(UTC).isoformat(),
            "ref": candidate.supporting_episodes[0].investigation.properties[
                "report_artifact_ref"
            ],
        },
    )
    assert (
        repository.get_fingerprint_history(receipt.fingerprint_id)
        .candidates[0]
        .feature_overlap
        == 1
    )
    repository.graph.query("MATCH (:Probe)-[e:EFFECTIVE_FOR]->() DELETE e")
    assert not repository.get_fingerprint_history(receipt.fingerprint_id).candidates


def test_history_filters_unproven_disabled_superseded_and_orders_before_expansion(
    repository, completed_evidence
):
    _, reports = completed_evidence
    receipt = repository.record_seed_context(reports[0].runId)
    install_history(repository, receipt, "b")
    install_history(repository, receipt, "a")
    history = repository.get_fingerprint_history(receipt.fingerprint_id, limit=1)
    assert [c.family_id for c in history.candidates] == ["synthetic-family-a"]
    repository.graph.query(
        "MATCH (p:Probe {id:'synthetic-probe-a'}) SET p.enabled=false"
    )
    assert [
        c.family_id
        for c in repository.get_fingerprint_history(receipt.fingerprint_id).candidates
    ] == ["synthetic-family-b"]
    repository.graph.query(
        "MATCH (f:FaultFamily {id:'synthetic-family-b'}) SET f.status='superseded',f.superseded_by_id='synthetic-replacement'"
    )
    assert not repository.get_fingerprint_history(receipt.fingerprint_id).candidates
    repository.graph.query("MATCH (p:Probe) SET p.enabled=true")
    repository.graph.query("MATCH ()-[e:MATCHES_FAMILY]->() DELETE e")
    assert not repository.get_fingerprint_history(receipt.fingerprint_id).candidates


@pytest.mark.parametrize(
    "corruption",
    ["negative", "successes", "scope", "source", "missing_run", "artifact"],
)
def test_malformed_or_missing_support_is_an_integrity_failure(
    repository, completed_evidence, corruption
):
    root, reports = completed_evidence
    receipt = repository.record_seed_context(reports[0].runId)
    install_history(repository, receipt)
    changed_file, original = None, None
    if corruption == "negative":
        repository.graph.query("MATCH ()-[e:EFFECTIVE_FOR]->() SET e.attempts=-1")
    elif corruption == "successes":
        repository.graph.query("MATCH ()-[e:EFFECTIVE_FOR]->() SET e.successes=5")
    elif corruption == "scope":
        for kind in ("EFFECTIVE_FOR", "MATCHES_FAMILY"):
            repository.graph.query(
                "MATCH ()-[e:" + kind + "]->() SET e.version_scope='{}'"
            )
    elif corruption == "source":
        repository.graph.query("MATCH ()-[e:MATCHES_FAMILY]->() SET e.source_id='{}'")
    elif corruption == "missing_run":
        repository.graph.query(
            "MATCH ()-[e:EXECUTED_AS]->(r:Run {role:'target'}) DELETE e"
        )
    else:
        context = repository.get_investigation_context(receipt.investigation_id)
        ref = context.artifacts[0]
        changed_file = root / ref.owner / ref.path
        original = changed_file.read_bytes()
        changed_file.write_bytes(b"changed")
    try:
        with pytest.raises(ContextError):
            repository.get_fingerprint_history(receipt.fingerprint_id)
    finally:
        if changed_file:
            changed_file.write_bytes(original)
