import { motion, useReducedMotion } from "motion/react";
import { useMotionTiming } from "./useMotionTiming";
import { useState } from "react";
import type { SavedReduction } from "./api";
import ReductionAttempt from "./ReductionAttempt";
import ReductionCaseLoader from "./ReductionCaseLoader";
import ReductionCase from "./ReductionCase";
import PairedEvidence from "./PairedEvidence";
import { reductionAction } from "./reductionCopy";

export default function ReductionLineage({
  id,
  page,
}: {
  id: string;
  page: SavedReduction;
}) {
  const reducedMotion = useReducedMotion();
  const transition = useMotionTiming("medium");
  const [visible, setVisible] = useState(10);
  const summary = page.summary;
  if (!summary || !page.case) return null;
  const accepted = page.attempts.filter(
    (item) => item.attempt.state === "accepted",
  );
  const rejected = page.attempts.filter((item) =>
    ["rejected", "failed"].includes(item.attempt.state),
  );
  return (
    <motion.section
      initial={false}
      layout={reducedMotion ? false : "position"}
      layoutDependency={page.summary?.currentCaseId}
      transition={transition}
      aria-labelledby="reduction-heading"
      className="min-w-0 border-b border-line"
    >
      <h2 className="sr-only">Case reduction</h2>
      <div className="border-b border-line p-4 sm:p-6">
        <h3 id="reduction-heading" className="font-semibold">
          Evidence-preserving reduction
        </h3>
        <p className="mt-3 min-h-12 text-sm text-accent">
          {reductionAction(summary)}
        </p>
        <p className="text-sm text-muted">
          Reduction source:{" "}
          {summary.source.sourceKind === "probe"
            ? `Experiment ${summary.source.sourceProbeSequence}`
            : "Original case"}
          .{" "}
          {summary.source.stable
            ? "The same difference was verified again on fresh engines."
            : "Repeatability has not been established."}
        </p>
        {summary.stopReason && summary.acceptedCount === 0 ? (
          <p className="mt-3 text-sm">
            No smaller case was verified. The reduction source is preserved.
          </p>
        ) : null}
        <p className="mt-4 text-sm">
          Accepted changes: {summary.acceptedCount} · Changes not retained:{" "}
          {summary.rejectedCount} · Verification failures:{" "}
          {summary.verificationFailures}
        </p>
      </div>
      <div className="border-b border-divergence bg-divergence-soft p-4 sm:px-6">
        <h4 className="font-semibold text-divergence">Difference observed.</h4>
        <p className="mt-2 text-sm">
          {summary.source.referenceDivergence.kind} ·{" "}
          {summary.source.referenceDivergence.changedDimensions.join(", ")}
        </p>
        <details>
          <summary className="min-h-11 cursor-pointer py-3 text-sm">
            Inspect difference and comparator provenance
          </summary>
          <p className="text-sm">
            An engine disagreement does not establish which engine is correct.
          </p>
          <dl className="mt-3 space-y-2 text-xs">
            <dt>Comparison version</dt>
            <dd className="break-all font-mono">
              {summary.source.referenceDivergence.comparisonVersion}
            </dd>
            <dt>Reference signature</dt>
            <dd className="break-all font-mono">
              {summary.source.referenceDivergence.signature}
            </dd>
            <dt>Baseline observation digest</dt>
            <dd className="break-all font-mono">
              {summary.source.referenceDivergence.baselineObservationDigest}
            </dd>
            <dt>Target observation digest</dt>
            <dd className="break-all font-mono">
              {summary.source.referenceDivergence.targetObservationDigest}
            </dd>
          </dl>
        </details>
      </div>
      <div className="grid min-w-0 divide-y divide-line lg:grid-cols-[1fr_2fr] lg:divide-x lg:divide-y-0">
        <div className="min-w-0 p-4 sm:p-6">
          <h4 className="font-semibold">Size of the case</h4>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <caption className="sr-only">
                Original, reduction source, and current verified case size
              </caption>
              <thead>
                <tr>
                  <th className="pr-3">Measure</th>
                  <th className="pr-3">Original</th>
                  <th className="pr-3">Source</th>
                  <th>Current</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                <tr>
                  <th className="py-3 pr-3 font-sans font-normal">
                    Query tokens
                  </th>
                  <td>{summary.originalSize.queryTokens}</td>
                  <td>{summary.sourceSize.queryTokens}</td>
                  <td>{summary.currentSize.queryTokens}</td>
                </tr>
                <tr>
                  <th className="py-3 pr-3 font-sans font-normal">
                    Setup statements
                  </th>
                  <td>{summary.originalSize.setupStatements}</td>
                  <td>{summary.sourceSize.setupStatements}</td>
                  <td>{summary.currentSize.setupStatements}</td>
                </tr>
                <tr>
                  <th className="py-3 pr-3 font-sans font-normal">
                    Setup tokens
                  </th>
                  <td>{summary.originalSize.setupTokens}</td>
                  <td>{summary.sourceSize.setupTokens}</td>
                  <td>{summary.currentSize.setupTokens}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <details className="mt-4">
            <summary className="min-h-11 cursor-pointer text-sm">
              Reduction source verification
            </summary>
            <p className="mb-4 break-all font-mono text-xs">
              Reference signature:{" "}
              {summary.source.referenceDivergence.signature}
            </p>
            {page.sourceCase ? (
              <ReductionCase
                label="Reduction source"
                value={page.sourceCase}
                id={id}
              />
            ) : (
              <ReductionCaseLoader
                id={id}
                label="Reduction source"
                caseId={summary.source.sourceCaseId}
              />
            )}
            {page.sourceObservations ? (
              <PairedEvidence observations={page.sourceObservations} />
            ) : null}
            <h5 className="my-4 font-semibold">Fresh repeat</h5>
            {page.stabilityObservations ? (
              <PairedEvidence observations={page.stabilityObservations} />
            ) : (
              <p className="text-sm">No complete repeat is available yet.</p>
            )}
          </details>
        </div>
        <div className="min-w-0 p-4 sm:p-6">
          <ReductionCase
            label="Current verified case"
            value={page.case}
            id={id}
          />
        </div>
      </div>
      <div className="min-w-0 border-t border-line p-4 sm:p-6">
        <h4 className="mb-3 font-semibold">Accepted lineage</h4>
        <ol>
          {page.attempts
            .filter((value) =>
              ["accepted", "proposed", "verifying"].includes(
                value.attempt.state,
              ),
            )
            .map((value) => (
              <ReductionAttempt key={value.attempt.id} value={value} id={id} />
            ))}
        </ol>
        {!accepted.length ? (
          <p className="text-sm text-muted">
            The reduction source remains the retained case.
          </p>
        ) : null}
        <details className="mt-5">
          <summary className="min-h-11 cursor-pointer text-sm">
            Show unsuccessful attempts ({rejected.length})
          </summary>
          <ol>
            {rejected.slice(0, visible).map((value) => (
              <ReductionAttempt key={value.attempt.id} value={value} id={id} />
            ))}
          </ol>
          {rejected.length > visible ? (
            <button
              className="min-h-11 underline"
              onClick={() => setVisible((count) => Math.min(32, count + 10))}
            >
              Show older attempts
            </button>
          ) : null}
        </details>
      </div>
    </motion.section>
  );
}
