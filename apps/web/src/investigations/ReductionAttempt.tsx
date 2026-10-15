import type { ReductionAttemptView } from "../contracts/evidence";
import PairedEvidence from "./PairedEvidence";
import ReductionCaseLoader from "./ReductionCaseLoader";
import ReductionCase from "./ReductionCase";
import { reductionReasons } from "./reductionCopy";

export default function ReductionAttempt({
  value,
  id,
}: {
  value: ReductionAttemptView;
  id: string;
}) {
  const attempt = value.attempt;
  const accepted = attempt.state === "accepted";
  const pending = ["proposed", "verifying"].includes(attempt.state);
  return (
    <li className="min-w-0 border-t border-line">
      <details>
        <summary className="min-h-11 cursor-pointer py-3 text-sm">
          <span
            className={
              accepted
                ? "text-evidence"
                : pending
                  ? "text-accent"
                  : "text-muted"
            }
          >
            {accepted
              ? "Verified change"
              : pending
                ? "Candidate"
                : "Change not retained"}{" "}
            {attempt.ordinal}
          </span>{" "}
          · {attempt.change.description}
        </summary>
        <div className="min-w-0 space-y-5 pb-6">
          <p className="text-sm">
            {attempt.reason
              ? reductionReasons[attempt.reason]
              : "Verification is pending. The current verified case is preserved."}
          </p>
          <p className="font-mono text-xs">
            Query tokens: {attempt.beforeSize.queryTokens} →{" "}
            {attempt.afterSize?.queryTokens ?? "unavailable"} · Setup
            statements: {attempt.beforeSize.setupStatements} →{" "}
            {attempt.afterSize?.setupStatements ?? "unavailable"}
          </p>
          <div className="grid min-w-0 gap-6 lg:grid-cols-2">
            {value.parent ? (
              <ReductionCase label="Parent case" value={value.parent} id={id} />
            ) : (
              <ReductionCaseLoader
                label="Parent case"
                id={id}
                caseId={attempt.parentCaseId}
              />
            )}
            {value.candidate ? (
              <ReductionCase
                label="Candidate"
                value={value.candidate}
                id={id}
              />
            ) : attempt.candidateCaseId ? (
              <ReductionCaseLoader
                label="Candidate"
                id={id}
                caseId={attempt.candidateCaseId}
              />
            ) : null}
          </div>
          {value.observations ? (
            <section>
              <h4 className="mb-4 font-semibold">Verification evidence</h4>
              <PairedEvidence observations={value.observations} />
            </section>
          ) : (
            <p className="text-sm text-muted">
              {pending
                ? "Waiting for the saved paired comparison."
                : "No complete paired verification is available for this change."}
            </p>
          )}
          <details>
            <summary className="min-h-11 cursor-pointer text-sm">
              Signature and verified artifact metadata
            </summary>
            <p className="break-all font-mono text-xs">
              {attempt.observedDivergence?.signature ??
                "No divergence signature recorded."}
            </p>
            <ul className="mt-4 space-y-3">
              {attempt.artifactRefs.map((ref) => (
                <li
                  key={`${ref.owner}/${ref.path}`}
                  className="break-all font-mono text-xs"
                >
                  {ref.kind} · {ref.bytes} bytes
                  <br />
                  {ref.sha256}
                </li>
              ))}
            </ul>
          </details>
        </div>
      </details>
    </li>
  );
}
