import type { MemoryDelta } from "../contracts/evidence";

export default function InvestigationMemory({
  memory,
  state,
  downloadsReady,
  finished,
}: {
  memory: MemoryDelta | null;
  state: string | null;
  downloadsReady: boolean;
  finished: boolean;
}) {
  return (
    <div className="border-t border-line py-6">
      <h4 className="font-semibold">
        {memory?.state === "recorded"
          ? "Investigation memory saved"
          : memory?.state === "ineligible"
            ? "Evidence saved. No procedural update was made."
            : state === "failed"
              ? downloadsReady
                ? "Downloads are ready, but investigation memory was not saved."
                : "Investigation memory was not saved."
              : finished
                ? "No saved memory receipt is available."
                : "Saving investigation memory…"}
      </h4>
      {memory?.reason ? (
        <p className="mt-3 text-sm text-muted">{memory.reason}</p>
      ) : null}
      {memory?.entries.map((entry) => (
        <details key={entry.selectionId} className="mt-3 border-t border-line">
          <summary className="min-h-11 cursor-pointer py-3 text-sm break-words">
            {entry.probeId.replaceAll("_", " ").replace(":v1", "")} ·{" "}
            <span className="tabular-nums">
              {entry.before.successes}/{entry.before.attempts} →{" "}
              {entry.after.successes}/{entry.after.attempts}
            </span>{" "}
            useful / attempted
          </summary>
          <p className="py-2 text-sm text-muted">
            {entry.reason === "repeated_source"
              ? "Supplied the source case that preserved the difference when checked again."
              : entry.reason === "semantic_contrast"
                ? "Established a recorded contrast in the target’s behavior."
                : "Recorded an experiment without a verified contribution."}
          </p>
          <pre
            tabIndex={0}
            className="max-h-64 overflow-auto bg-surface p-3 font-mono text-xs"
          >
            {JSON.stringify(
              {
                family: entry.familyId,
                scope: memory.scope,
                before: entry.before,
                after: entry.after,
                evidence: entry.evidenceRefs,
                commit: memory.commitKey,
              },
              null,
              2,
            )}
          </pre>
        </details>
      ))}
    </div>
  );
}
