import type { Decision } from "../contracts/evidence";

export default function ExperimentReason({ data }: { data: string }) {
  const plan = JSON.parse(data) as Decision;
  const candidate = plan.candidates[0];
  if (!candidate)
    return (
      <p className="text-sm text-muted">No supported experiments remain.</p>
    );
  return (
    <div className="space-y-4 text-sm">
      <p>{candidate.reason}</p>
      {candidate.source === "structural" ? (
        <p className="text-muted">
          No verified related investigations yet. Experiments will use
          structural evidence.
        </p>
      ) : null}
      <dl className="grid grid-cols-2 gap-3">
        <dt>Selected experiment</dt>
        <dd className="break-all font-mono">{candidate.probe_id}</dd>
        <dt>Utility</dt>
        <dd className="font-mono">{candidate.utility.toFixed(4)}</dd>
        <dt>Feature fit</dt>
        <dd className="font-mono">{candidate.feature_fit.toFixed(4)}</dd>
        <dt>Historical yield</dt>
        <dd className="font-mono">{candidate.historical_yield.toFixed(4)}</dd>
        <dt>Version affinity</dt>
        <dd className="font-mono">{candidate.version_affinity.toFixed(4)}</dd>
        <dt>Novelty</dt>
        <dd className="font-mono">{candidate.novelty.toFixed(4)}</dd>
        <dt>Normalized cost</dt>
        <dd className="font-mono">{candidate.normalized_cost.toFixed(4)}</dd>
      </dl>
      <p>
        Controlled features:{" "}
        <span className="font-mono">
          {candidate.matched_feature_ids.join(", ") || "None"}
        </span>
      </p>
      {candidate.chosen_history_key ? (
        <p className="break-all font-mono">
          Evidence path: {candidate.chosen_history_key}
        </p>
      ) : null}
      <p className="break-all font-mono text-xs text-muted">
        Selection: {plan.selection_id}
        <br />
        Original case: {plan.seed_case_id}
        <br />
        Output case: {candidate.output_case_id}
      </p>
    </div>
  );
}
