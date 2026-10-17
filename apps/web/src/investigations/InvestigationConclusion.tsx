import type { ConclusionPage, Snapshot } from "../contracts/evidence";
import { terminal } from "./api";
import FamilyEvidence from "./FamilyEvidence";
import RegressionDownloads from "./RegressionDownloads";
import InvestigationMemory from "./InvestigationMemory";
import AgentEvidence from "./AgentEvidence";
import HistoricalInfluence from "./HistoricalInfluence";

export default function InvestigationConclusion({
  id,
  page,
  snapshot,
}: {
  id: string;
  page: ConclusionPage;
  snapshot: Snapshot;
}) {
  const conclusion = page.conclusion;
  return (
    <section
      className="min-w-0 border-x border-b border-line px-4 sm:px-6"
      aria-label="Investigation conclusion"
    >
      {page.influence ? (
        <HistoricalInfluence influence={page.influence} />
      ) : null}
      {conclusion ? (
        <div className="py-6">
          <p className="mb-3 text-xs uppercase tracking-wider text-evidence">
            Conclusion
          </p>
          <h2 className="text-xl font-semibold">
            {conclusion.state === "matched"
              ? "Matched behavioral family"
              : conclusion.state === "provisional"
                ? "Provisional behavioral family"
                : "Family unresolved"}
          </h2>
          {conclusion.familyName ? (
            <p className="mt-3 font-semibold">{conclusion.familyName}</p>
          ) : null}
          <p className="mt-3 text-sm leading-relaxed text-muted">
            {conclusion.state === "unresolved"
              ? "The difference is verified, but its family remains unresolved."
              : "This grouping is supported by the recorded behavior. Its underlying cause is not confirmed."}
          </p>
          <h4 className="mt-5 text-xs font-semibold uppercase tracking-wider">
            Observed
          </h4>
          {conclusion.observed.map((fact) => (
            <p key={fact} className="mt-2 text-sm">
              {fact}
            </p>
          ))}
          <h3 className="mt-5 text-xs font-semibold uppercase tracking-wider text-unresolved">
            Unknown
          </h3>
          {conclusion.unknowns.map((fact) => (
            <p key={fact} className="mt-2 text-sm">
              {fact}
            </p>
          ))}
          {page.classification ? (
            <p className="mt-4 text-sm text-muted">
              {page.classification.retainedIsRepeatedSource
                ? "The retained case is the source that was checked twice."
                : "The source was checked twice. The retained descendant was verified once."}{" "}
              A smaller verified case does not establish global minimality.
            </p>
          ) : null}
          <details className="mt-4">
            <summary className="min-h-11 cursor-pointer py-3 text-sm">
              Inspect family evidence and limits
            </summary>
            <p className="text-sm text-muted">
              Behavioral match score: deterministic evidence score; not a
              probability.
            </p>
            {page.classification ? (
              <>
                <p className="mt-3 text-sm text-muted">
                  {page.classification.retainedIsRepeatedSource
                    ? "The retained case is the source that was checked twice."
                    : "The source was checked twice. The retained descendant was verified once."}
                </p>
                <pre
                  tabIndex={0}
                  className="mt-3 max-h-80 overflow-auto bg-surface p-3 font-mono text-xs"
                >
                  {JSON.stringify(page.classification, null, 2)}
                </pre>
              </>
            ) : null}
            {page.candidates.map((candidate) => (
              <FamilyEvidence
                key={candidate.familyId + candidate.sourceInvestigationId}
                candidate={candidate}
                scope={page.classification?.scope}
              />
            ))}
            {!page.candidates.length ? (
              <p className="mt-3 text-sm">
                No existing family sufficiently explains this behavior.
              </p>
            ) : null}
            <p className="mt-3 break-all font-mono text-xs text-muted">
              Evidence: {conclusion.evidenceRef.sha256}
            </p>
          </details>
        </div>
      ) : snapshot.status === "CLASSIFYING" ? (
        <p className="py-6" role="status">
          Comparing fault-family evidence…
        </p>
      ) : null}
      {page.exports ? (
        <RegressionDownloads id={id} manifest={page.exports} />
      ) : conclusion ? (
        <p className="py-5 text-sm text-muted">
          {snapshot.terminalReason?.code === "export_failure"
            ? "We couldn’t prepare the downloads. Verified evidence is preserved."
            : terminal(snapshot.status)
              ? "No verified downloads are available for this investigation."
              : "Preparing downloads…"}
        </p>
      ) : null}
      {conclusion ? (
        <InvestigationMemory
          memory={page.memory}
          downloadsReady={Boolean(page.exports)}
          finished={terminal(snapshot.status)}
          state={
            snapshot.terminalReason?.code === "memory_failure"
              ? "failed"
              : snapshot.memoryState
          }
        />
      ) : null}
      <AgentEvidence
        agent={page.agent}
        interpretation={page.interpretation}
        finished={terminal(snapshot.status)}
      />
    </section>
  );
}
