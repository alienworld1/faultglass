import { parseDecision, selectedCandidate } from "./decision";
export default function ExperimentReason({ data }: { data: string }) {
  const plan = parseDecision(data);
  if (!plan)
    return (
      <p className="text-sm text-failure">
        We couldn’t read this evidence. Retry connection.
      </p>
    );
  const candidate = selectedCandidate(plan);
  if (!candidate)
    return (
      <p className="text-sm text-muted">
        {plan.selected_probe_id
          ? "The saved selection is absent from the returned candidates. No ranking can be confirmed."
          : "No supported experiment was selected."}
      </p>
    );
  const scores = {
    Rank: candidate.rank,
    Utility: candidate.utility,
    "Feature fit": candidate.feature_fit,
    "Historical yield": candidate.historical_yield,
    "Version affinity": candidate.version_affinity,
    Novelty: candidate.novelty,
    "Normalized cost": candidate.normalized_cost,
    Attempts: candidate.attempts,
    Successes: candidate.successes,
    "Average cost (ms)": candidate.avg_cost_ms,
  };
  return (
    <div className="min-w-0 space-y-4 text-sm">
      <p className="break-words font-mono">{candidate.probe_id}</p>
      <p>{candidate.reason}</p>
      <div className="border-l-2 border-accent pl-3">
        <h4 className="font-semibold">Transformation</h4>
        <pre tabIndex={0} className="mt-2 overflow-x-auto font-mono text-xs">
          {candidate.edit.before}
          {"\n→\n"}
          {candidate.edit.after}
        </pre>
      </div>
      {plan.novel && candidate.source === "structural" ? (
        <p className="text-muted">
          No verified related investigations yet. Experiments will use
          structural evidence.
        </p>
      ) : null}
      <h4 className="font-semibold">Saved score inputs</h4>
      <p className="text-muted">
        These are deterministic ranking inputs, not probabilities.
      </p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        {Object.entries(scores).map(([label, value]) => (
          <div key={label} className="contents">
            <dt>{label}</dt>
            <dd className="font-mono tabular-nums">
              {typeof value === "number"
                ? Number.isInteger(value)
                  ? value
                  : value.toFixed(4)
                : "Unavailable"}
            </dd>
          </div>
        ))}
      </dl>
      <p>
        Matched features:{" "}
        <span className="break-all font-mono">
          {candidate.matched_feature_ids.join(", ") || "None"}
        </span>
      </p>
      <p>
        Target features:{" "}
        <span className="break-all font-mono">
          {candidate.target_feature_ids.join(", ") || "None"}
        </span>
      </p>
      <p>
        Eligibility:{" "}
        {candidate.eligibility.applicable ? "Applicable" : "Not applicable"} ·{" "}
        {candidate.eligibility.reason_code}
      </p>
      <p>
        Evidence source: {candidate.source} · Cost class: {candidate.cost_class}
      </p>
      {candidate.chosen_history_key ? (
        <p className="break-all">
          Historical relationship reference:{" "}
          <span className="font-mono">{candidate.chosen_history_key}</span>
        </p>
      ) : null}
      <details>
        <summary className="min-h-11 cursor-pointer py-3">
          Case identities and version scope
        </summary>
        <pre
          tabIndex={0}
          className="max-h-80 overflow-auto bg-secondary p-3 font-mono text-xs"
        >
          {JSON.stringify(
            {
              selection: plan.selection_id,
              fingerprint: plan.fingerprint_id,
              originalCase: plan.seed_case_id,
              inputCase: candidate.input_case_id,
              outputCase: candidate.output_case_id,
              transformedCase: candidate.transformed_case_ref,
              scope: plan.scope,
              planner: plan.planner_version,
            },
            null,
            2,
          )}
        </pre>
      </details>
    </div>
  );
}
