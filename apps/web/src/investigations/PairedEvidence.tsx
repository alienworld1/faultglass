import type { PairedSummary } from "../contracts/evidence";

export default function PairedEvidence({
  observations,
}: {
  observations: PairedSummary;
}) {
  return (
    <div className="grid min-w-0 divide-y divide-line border-y border-line sm:grid-cols-2 sm:divide-x sm:divide-y-0">
      {(["baseline", "target"] as const).map((role) => (
        <div className="min-w-0 py-4 sm:px-4" key={role}>
          <h4 className="font-semibold capitalize">{role}</h4>
          <p className="mt-2 break-all font-mono text-xs">
            {observations[role].engineVersionId}
          </p>
          <p className="mt-3 text-md font-semibold capitalize">
            {observations[role].status}
          </p>
          {observations[role].errorCategory ? (
            <p className="mt-2 font-mono text-xs">
              {observations[role].errorCategory}
            </p>
          ) : null}
          {observations[role].detail ? (
            <p className="mt-3 break-words text-sm">
              {observations[role].detail}
            </p>
          ) : null}
          {observations[role].rowCount !== null ? (
            <p className="mt-3 text-sm">
              {observations[role].rowCount}{" "}
              {observations[role].rowCount === 1 ? "row" : "rows"} observed
            </p>
          ) : null}
          {observations[role].columns.length ? (
            <p className="mt-2 break-words font-mono text-xs">
              Columns: {observations[role].columns.join(", ")}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}
