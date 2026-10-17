import type { Decision, RankedCandidate } from "../contracts/evidence";

export function parseDecision(data: string): Decision | null {
  try {
    const value = JSON.parse(data) as Decision;
    if (
      !value ||
      !Array.isArray(value.candidates) ||
      !(
        value.selected_probe_id === null ||
        typeof value.selected_probe_id === "string"
      ) ||
      typeof value.selection_id !== "string"
    )
      return null;
    if (!value.candidates.every(validCandidate)) return null;
    return value;
  } catch {
    return null;
  }
}
function validCandidate(value: RankedCandidate) {
  return (
    value &&
    typeof value.probe_id === "string" &&
    typeof value.reason === "string" &&
    [
      value.rank,
      value.utility,
      value.feature_fit,
      value.historical_yield,
      value.version_affinity,
      value.novelty,
      value.normalized_cost,
      value.attempts,
      value.successes,
      value.avg_cost_ms,
    ].every(Number.isFinite) &&
    Array.isArray(value.matched_feature_ids) &&
    value.matched_feature_ids.every((feature) => typeof feature === "string") &&
    Array.isArray(value.target_feature_ids) &&
    value.target_feature_ids.every((feature) => typeof feature === "string") &&
    ["history", "structural"].includes(value.source) &&
    value.edit &&
    typeof value.edit.before === "string" &&
    typeof value.edit.after === "string" &&
    value.eligibility &&
    typeof value.eligibility.applicable === "boolean" &&
    typeof value.eligibility.reason_code === "string"
  );
}
export function selectedCandidate(plan: Decision) {
  return (
    plan.candidates.find(
      (value) => value.probe_id === plan.selected_probe_id,
    ) ?? null
  );
}
