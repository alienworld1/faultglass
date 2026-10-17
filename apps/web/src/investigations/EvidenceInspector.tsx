import { useEffect, useRef } from "react";
import type { Snapshot } from "../contracts/evidence";
import type { EvidenceSubject } from "./evidenceSubjects";
import ExperimentReason from "./ExperimentReason";
import PairedEvidence from "./PairedEvidence";
export default function EvidenceInspector({
  subject,
  snapshot,
  close,
}: {
  subject: EvidenceSubject | "fingerprint";
  snapshot: Snapshot;
  close: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const identity = subject === "fingerprint" ? "fingerprint" : subject.sequence;
  useEffect(() => {
    heading.current?.focus();
  }, [identity]);
  return (
    <aside
      className="min-w-0 border-t border-line bg-secondary p-4 sm:p-6 2xl:max-h-[80dvh] 2xl:self-start 2xl:overflow-y-auto 2xl:border-t-0 2xl:border-l"
      aria-label="Contextual inspector"
      onKeyDown={(event) => {
        if (event.key === "Escape") close();
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <h2 ref={heading} tabIndex={-1} className="py-3 font-semibold">
          {subject === "fingerprint"
            ? "Fingerprint evidence"
            : subject.sequence === 0
              ? "Original comparison"
              : `Experiment ${subject.sequence}`}
        </h2>
        <button className="min-h-11 shrink-0 underline" onClick={close}>
          Close inspector
        </button>
      </div>
      <h3 className="mt-4 text-xs uppercase tracking-wider text-muted">
        Summary
      </h3>
      {subject === "fingerprint" ? (
        <p className="mt-3 break-all font-mono text-xs">
          {snapshot.fingerprintId ?? "No fingerprint has been saved yet."}
        </p>
      ) : (
        <p className="mt-3 text-sm">
          Review the saved query, why it was chosen, and what happened on each
          engine in this comparison.
        </p>
      )}
      <h3 className="mt-6 mb-3 text-xs uppercase tracking-wider text-muted">
        Evidence
      </h3>
      {subject === "fingerprint" ? (
        <p className="text-sm">
          Only the saved fingerprint identity is returned here. Features used by
          each experiment appear in its selection evidence.
        </p>
      ) : (
        <div className="space-y-6">
          {subject.decision ? (
            <ExperimentReason data={subject.decision} />
          ) : null}
          {subject.observations ? (
            <PairedEvidence observations={subject.observations} />
          ) : (
            <p className="text-sm">
              Results for this comparison haven’t been saved yet.
            </p>
          )}
        </div>
      )}
      <details className="mt-6">
        <summary className="min-h-11 cursor-pointer py-3 font-semibold">
          Raw · returned metadata
        </summary>
        <p className="my-3 text-sm text-muted">
          Full execution bytes are available in the evidence report when ready.
          References alone do not expose file contents.
        </p>
        <pre
          tabIndex={0}
          className="max-h-96 max-w-full overflow-auto bg-surface p-3 font-mono text-xs"
        >
          {JSON.stringify(
            subject === "fingerprint"
              ? {
                  fingerprintId: snapshot.fingerprintId,
                  references: snapshot.evidence,
                }
              : subject,
            null,
            2,
          )}
        </pre>
      </details>
    </aside>
  );
}
