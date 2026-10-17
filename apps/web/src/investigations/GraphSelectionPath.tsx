import type { RankedCandidate } from "../contracts/evidence";

export default function GraphSelectionPath({
  candidate,
}: {
  candidate: RankedCandidate;
}) {
  const family = candidate.chosen_history_key?.split(":{")[0];
  if (
    !candidate.matched_feature_ids.length ||
    (candidate.source === "history" && !family)
  )
    return null;
  return (
    <section
      aria-label="Graph selection path"
      className="border-l-2 border-evidence pl-3"
    >
      <h4 className="font-semibold">Connected evidence</h4>
      <ol className="mt-3 space-y-2 text-sm">
        <li>Your case’s fingerprint</li>
        <li>
          <span className="font-mono text-xs text-evidence">
            ↓ USES_FEATURE
          </span>
          <p className="mt-1 break-words font-mono">
            {candidate.matched_feature_ids.join(" · ")}
          </p>
        </li>
        {candidate.source === "history" && family ? (
          <li>
            <span className="font-mono text-xs text-evidence">
              ↑ INVOLVES_FEATURE
            </span>
            <p className="mt-1 break-all">Related family · {family}</p>
          </li>
        ) : null}
        <li>
          <span className="font-mono text-xs text-evidence">
            ↑{" "}
            {candidate.source === "history"
              ? "EFFECTIVE_FOR"
              : "TARGETS_FEATURE"}
          </span>
          <p className="mt-1 break-words font-mono">{candidate.probe_id}</p>
        </li>
      </ol>
      <p className="mt-3 text-muted">
        {candidate.source === "history"
          ? `${candidate.successes} useful ${candidate.successes === 1 ? "outcome" : "outcomes"} across ${candidate.attempts} prior ${candidate.attempts === 1 ? "attempt" : "attempts"} informed this experiment’s ranking.`
          : "The experiment targets features in your case. No prior outcomes contributed to this ranking."}
      </p>
      {candidate.boundary_value ? (
        <p className="mt-2 text-evidence">
          This experiment previously revealed a verified change in behavior,
          helping locate the fault family’s boundary.
        </p>
      ) : null}
    </section>
  );
}
