from math import sqrt

from .canonicalize import case_identity
from .jsonio import encode
from .planner_models import ProbeEligibility, RankedCandidate, Rejection
from .probe_transforms import transform

COSTS = {"small": 0.25, "medium": 0.5, "large": 1.0}
PLANNER_VERSION = "planner-v2"


def history_key(row):
    return row.family_id + ":" + encode(row.version_scope.model_dump()).decode()


def affinity(row, scope, lineages):
    other = row.version_scope
    if other.comparison_version != scope.comparison_version or (
        other.baseline == scope.target and other.target == scope.baseline
    ):
        return None
    if other == scope:
        return 1.0
    actual = [
        entry.engine.properties["lineage"] for entry in row.supporting_episodes[0].runs
    ]
    return 0.5 if actual == lineages else None


def factors(features, targets, row=None, version_affinity=0.0, cost_class="small"):
    fit = len(set(features) & set(targets)) / len(targets)
    attempts, successes, cost = (
        (row.attempts, row.successes, row.avg_cost_ms) if row else (0, 0, 0.0)
    )
    if row:
        fit = 0.5 * fit + 0.5 * len(set(features) & set(row.feature_ids)) / len(
            features
        )
    normalized_cost = COSTS[cost_class]
    if row and attempts > 0:
        normalized_cost = (normalized_cost + min(cost / 60000, 1)) / 2
    result = dict(
        feature_fit=fit,
        historical_yield=(successes + 1) / (attempts + 2),
        version_affinity=version_affinity,
        novelty=1 / sqrt(attempts + 1),
        normalized_cost=normalized_cost,
        boundary_value=float(bool(row and getattr(row, "semantic_contrast", False))),
    )
    result["utility"] = (
        0.35 * result["feature_fit"]
        + 0.30 * result["historical_yield"]
        + 0.20 * result["version_affinity"]
        + 0.10 * result["novelty"]
        - 0.05 * result["normalized_cost"]
        + 0.10 * result["boundary_value"]
    )
    return result


def rank_candidates(case, snapshot, save_output, *, tried_outputs=()):
    candidates, rejections, seen = [], [], set(tried_outputs)
    known = {item.definition.id for item in snapshot.catalog}
    for row in snapshot.history:
        if row.probe_id not in known:
            rejections.append(
                Rejection(
                    input_case_id=case_identity(case)[0],
                    probe_id=row.probe_id,
                    reason_code="unknown_definition",
                    history_key=history_key(row),
                )
            )
    for catalog in sorted(snapshot.catalog, key=lambda entry: entry.definition.id):
        definition = catalog.definition
        output, edit, reason = transform(case, definition)
        if not catalog.enabled or not definition.enabled:
            reason = "disabled"
        if reason != "applicable":
            rejections.append(
                Rejection(
                    input_case_id=case_identity(case)[0],
                    probe_id=definition.id,
                    reason_code=reason,
                )
            )
            continue
        output_id = case_identity(output)[0]
        if output_id in seen:
            rejections.append(
                Rejection(
                    input_case_id=case_identity(case)[0],
                    probe_id=definition.id,
                    reason_code="duplicate_output",
                )
            )
            continue
        seen.add(output_id)
        targets = sorted(edge.target_id for edge in catalog.targets)
        choices = []
        for row in snapshot.history:
            if row.probe_id != definition.id:
                continue
            if (
                row.template_version != definition.template_version
                or row.probe_type != definition.type
            ):
                raise ValueError(
                    "The registered experiment conflicts with related evidence."
                )
            weight = affinity(row, snapshot.scope, snapshot.lineages)
            if weight is None:
                rejections.append(
                    Rejection(
                        input_case_id=case_identity(case)[0],
                        probe_id=definition.id,
                        reason_code="incompatible_scope",
                        history_key=history_key(row),
                    )
                )
                continue
            score = factors(
                snapshot.feature_ids, targets, row, weight, definition.cost_class
            )
            choices.append((score, row))
        choices.sort(key=lambda pair: (-pair[0]["utility"], history_key(pair[1])))
        score, row = (
            choices[0]
            if choices
            else (
                factors(
                    snapshot.feature_ids, targets, cost_class=definition.cost_class
                ),
                None,
            )
        )
        output_ref = save_output(definition, output)
        candidates.append(
            RankedCandidate(
                eligibility=ProbeEligibility(
                    probe_id=definition.id,
                    applicable=True,
                    reason_code="applicable",
                    input_case_id=case_identity(case)[0],
                    output_case_id=output_id,
                    transformed_case_ref=output_ref,
                ),
                probe_id=definition.id,
                template_version=definition.template_version,
                definition_sha256=definition.definition_sha256,
                input_case_id=case_identity(case)[0],
                output_case_id=output_id,
                target_feature_ids=targets,
                matched_feature_ids=sorted(
                    set(snapshot.feature_ids)
                    & (set(row.feature_ids) if row else set(targets))
                ),
                source="history" if row else "structural",
                chosen_history_key=history_key(row) if row else None,
                attempts=row.attempts if row else 0,
                successes=row.successes if row else 0,
                avg_cost_ms=row.avg_cost_ms if row else 0.0,
                reason="Highest utility among compatible related evidence for this experiment."
                if row
                else "No compatible related evidence; ranked by supported structural targets.",
                cost_class=definition.cost_class,
                rank=1,
                edit=edit,
                transformed_case_ref=output_ref,
                **score,
            )
        )
    candidates.sort(key=lambda item: (-item.utility, item.probe_id))
    candidates = [
        item.model_copy(update={"rank": index})
        for index, item in enumerate(candidates, 1)
    ]
    return candidates, rejections
