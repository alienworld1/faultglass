import { Link } from "react-router-dom";
import type { FamilyCandidate, VersionScope } from "../contracts/evidence";
export default function FamilyEvidence({
  candidate,
  scope,
}: {
  candidate: FamilyCandidate;
  scope?: VersionScope;
}) {
  return (
    <details className="mt-4 min-w-0 border-t border-line">
      <summary className="min-h-11 cursor-pointer py-3 text-sm break-words">
        Family {candidate.familyId} · {candidate.familyStatus} ·{" "}
        {candidate.compatible ? "Compatible scope" : "Incompatible scope"}
      </summary>
      <h5 className="mt-2 text-xs uppercase tracking-wider text-muted">
        Summary
      </h5>
      <p className="mt-2 text-sm">
        {candidate.eligible
          ? "Eligible behavioral candidate"
          : "Candidate excluded from matching"}{" "}
        · score {candidate.score.toFixed(4)}. This score is not a probability.
      </p>
      <h5 className="mt-5 text-xs uppercase tracking-wider text-evidence">
        Evidence
      </h5>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
        {Object.entries({
          "Feature contribution": candidate.feature,
          "Behavior contribution": candidate.behavior,
          "Version contribution": candidate.version,
          "Reduced shape contribution": candidate.reducedShape,
        }).map(([label, value]) => (
          <div key={label} className="contents">
            <dt>{label}</dt>
            <dd className="font-mono">{value.toFixed(4)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-sm">
        Supporting probes:{" "}
        <span className="break-all font-mono">
          {candidate.supportingProbeIds.join(", ") || "None"}
        </span>
      </p>
      <p className="mt-3 text-sm">
        Contradictory probes:{" "}
        <span className="break-all font-mono">
          {candidate.contradictoryProbeIds.join(", ") || "None"}
        </span>
      </p>
      <ul className="mt-3 text-sm">
        {candidate.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
      <Link
        to={`/investigations/${candidate.sourceInvestigationId}`}
        className="mt-3 inline-flex min-h-11 items-center break-all text-sm underline"
      >
        Source investigation {candidate.sourceInvestigationId}
      </Link>
      {scope ? (
        <p className="mt-3 text-sm break-all">
          Compared version scope:{" "}
          <span className="font-mono">
            {scope.baseline} / {scope.target} · {scope.comparison_version}
          </span>
        </p>
      ) : null}
      <p className="mt-3 text-sm break-all">
        Relationship references:{" "}
        <span className="font-mono">
          {candidate.pathRefs.join(" · ") || "None returned"}
        </span>
      </p>
      <details className="mt-3">
        <summary className="min-h-11 cursor-pointer py-3 text-sm">
          Raw · family metadata
        </summary>
        <pre
          tabIndex={0}
          className="max-h-80 overflow-auto bg-secondary p-3 font-mono text-xs"
        >
          {JSON.stringify(candidate, null, 2)}
        </pre>
      </details>
    </details>
  );
}
