import { Link } from "react-router-dom";
import type { HistoricalInfluence as Influence } from "../contracts/evidence";

export default function HistoricalInfluence({
  influence,
}: {
  influence: Influence;
}) {
  if (!influence.priorInvestigationIds.length) return null;
  const selected = influence.selectedProbeId;
  const before = influence.withoutHistory.find((p) => p.probeId === selected);
  const after = influence.withHistory.find((p) => p.probeId === selected);
  return (
    <details className="border-b border-line py-5">
      <summary className="min-h-11 cursor-pointer py-3 font-semibold">
        {before && after && before.rank !== after.rank
          ? `Prior evidence moved the selected experiment from rank ${before.rank} to ${after.rank}.`
          : influence.changed
            ? "Related evidence changed the ranking; the selected experiment’s rank is unchanged."
            : "Related investigation evidence informed this decision; the experiment order is unchanged."}
      </summary>
      <p className="mt-3 text-sm">
        Selected experiment:{" "}
        <span className="break-words font-mono">{selected}</span>
      </p>
      <div className="mt-3 flex flex-wrap gap-4">
        {influence.priorInvestigationIds.map((id) => (
          <Link
            key={id}
            className="inline-flex min-h-11 items-center break-all text-sm underline"
            to={`/investigations/${id}`}
          >
            Prior investigation {id.slice(0, 8)}
          </Link>
        ))}
      </div>
      {before && after ? (
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <dt>Selected rank · without / with history</dt>
          <dd className="font-mono">
            {before.rank} / {after.rank}
          </dd>
          <dt>Selected utility · without / with history</dt>
          <dd className="font-mono">
            {before.score.toFixed(4)} / {after.score.toFixed(4)}
          </dd>
        </dl>
      ) : (
        <p className="mt-3 text-sm">
          Selected probe rank comparison is unavailable.
        </p>
      )}
      <p className="mt-3 break-all text-sm">
        Relationship references:{" "}
        <span className="font-mono">{influence.pathRefs.join(" · ")}</span>
      </p>
      <details>
        <summary className="min-h-11 cursor-pointer py-3 text-sm">
          Raw · saved ranking and provenance
        </summary>
        <pre
          tabIndex={0}
          className="mt-3 max-h-72 overflow-auto bg-surface p-3 font-mono text-xs"
        >
          {JSON.stringify(
            {
              "Without this prior evidence": influence.withoutHistory,
              "With this prior evidence": influence.withHistory,
              "Graph paths": influence.pathRefs,
              decision: influence.decisionRef,
            },
            null,
            2,
          )}
        </pre>
      </details>
    </details>
  );
}
