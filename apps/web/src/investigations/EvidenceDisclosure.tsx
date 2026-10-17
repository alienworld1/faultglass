import { useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import type { EvidencePage, Snapshot } from "../contracts/evidence";
import { terminal } from "./api";
import { evidenceSubjects } from "./evidenceSubjects";
import PairedEvidence from "./PairedEvidence";
import EvidenceInspector from "./EvidenceInspector";
import { useMotionTiming } from "./useMotionTiming";
import { parseDecision, selectedCandidate } from "./decision";

export default function EvidenceDisclosure({
  page,
  snapshot,
}: {
  page: EvidencePage;
  snapshot: Snapshot;
}) {
  const [selection, setSelection] = useState<number | "fingerprint" | null>(
    null,
  );
  const invokingControl = useRef<HTMLButtonElement | null>(null);
  const reducedMotion = useReducedMotion();
  const transition = useMotionTiming("short");
  const subjects = evidenceSubjects(page);
  const active = subjects.at(-1);
  const recorded =
    subjects.toReversed().find((value) => value.observations && value.query) ??
    subjects.toReversed().find((value) => value.query);
  const subject =
    selection === "fingerprint"
      ? "fingerprint"
      : subjects.find((value) => value.sequence === selection);
  function inspect(
    sequence: number | "fingerprint",
    button: HTMLButtonElement,
  ) {
    invokingControl.current = button;
    setSelection(sequence);
  }
  function close() {
    setSelection(null);
    invokingControl.current?.focus();
  }
  const plan = active?.decision ? parseDecision(active.decision) : null;
  const chosen = plan ? selectedCandidate(plan) : null;
  return (
    <motion.div
      initial={false}
      layout={reducedMotion ? false : "position"}
      transition={transition}
      className={
        subject
          ? "grid min-w-0 2xl:grid-cols-[minmax(0,18fr)_minmax(320px,7fr)]"
          : "min-w-0"
      }
    >
      <div className="grid min-w-0 lg:grid-cols-[minmax(160px,1fr)_minmax(0,3fr)]">
        <section className="min-w-0 p-4 sm:p-6 lg:col-start-2 lg:row-start-1">
          <p className="text-xs uppercase tracking-wider text-muted">
            {active?.sequence
              ? `Experiment ${active.sequence}`
              : "Original case"}
          </p>
          <h2 className="mt-3 text-xl font-semibold">
            {snapshot.reduction
              ? "Evidence leading to reduction"
              : active?.observations
                ? "Current tested case"
                : "Last recorded case"}
          </h2>
          {recorded?.query ? (
            <pre
              tabIndex={0}
              className="mt-5 overflow-x-auto border-l-2 border-line-strong bg-surface p-4 font-mono text-md"
            >
              {recorded.query}
            </pre>
          ) : (
            <p className="mt-4 text-sm text-muted">
              The case will appear when execution evidence is saved.
            </p>
          )}
          {recorded ? (
            <p className="mt-2 text-xs text-muted">
              Case evidence:{" "}
              {recorded.sequence === 0
                ? "Original comparison"
                : `Experiment ${recorded.sequence}`}
            </p>
          ) : null}
          {active && !active.observations ? (
            <p className="mt-3 text-sm text-muted">
              {terminal(snapshot.status)
                ? "No paired evidence was recorded for the selected experiment. The last recorded case and observations remain available."
                : "The selected experiment is awaiting paired evidence. The last recorded case and observations remain available."}
            </p>
          ) : null}
          {chosen ? (
            <div className="mt-5 border-l-2 border-accent pl-4">
              <h3 className="text-xs uppercase tracking-wider text-accent">
                Selected action
              </h3>
              <p className="mt-2 break-words font-mono text-sm">
                {chosen.probe_id}
              </p>
              <p className="mt-2 text-md">{chosen.reason}</p>
              <p className="mt-2 font-mono text-xs">
                Saved rank {chosen.rank} · utility {chosen.utility.toFixed(4)}
              </p>
            </div>
          ) : null}
          {recorded?.observations ? (
            <div className="mt-6">
              <h3 className="mb-4 text-xs uppercase tracking-wider text-evidence">
                Paired evidence · same case / sequence {recorded.sequence}
              </h3>
              <PairedEvidence observations={recorded.observations} />
            </div>
          ) : (
            <p className="mt-6 text-sm text-muted">
              No comparison evidence has been recorded yet.
            </p>
          )}
          {active ? (
            <div className="mt-4 flex flex-wrap gap-x-5">
              <button
                className="min-h-11 underline"
                aria-expanded={selection === active.sequence}
                onClick={(event) =>
                  inspect(active.sequence, event.currentTarget)
                }
              >
                {active.decision
                  ? "Why this experiment?"
                  : "Inspect comparison evidence"}
              </button>
              {snapshot.fingerprintId ? (
                <button
                  className="min-h-11 underline"
                  aria-expanded={selection === "fingerprint"}
                  onClick={(event) =>
                    inspect("fingerprint", event.currentTarget)
                  }
                >
                  Inspect fingerprint
                </button>
              ) : null}
            </div>
          ) : null}
        </section>
        <nav
          aria-label="Evidence history"
          className="min-w-0 border-t border-line p-4 sm:p-6 lg:col-start-1 lg:row-start-1 lg:border-t-0 lg:border-r"
        >
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
            Evidence history
          </h2>
          <p className="mt-3 text-sm text-muted">
            Earlier comparisons remain available.
          </p>
          <ol className="mt-4">
            {subjects.map((item) => (
              <motion.li
                transition={transition}
                initial={false}
                layout={reducedMotion ? false : "position"}
                key={item.sequence}
                className="border-t border-line"
              >
                <button
                  className="min-h-11 w-full border-l-2 border-transparent py-3 pl-3 text-left aria-pressed:border-accent aria-pressed:bg-secondary"
                  aria-pressed={selection === item.sequence}
                  onClick={(event) =>
                    inspect(item.sequence, event.currentTarget)
                  }
                >
                  <span className="block text-sm font-semibold">
                    {item.sequence === 0
                      ? "Original comparison"
                      : `Experiment ${item.sequence}`}
                  </span>
                  <span className="mt-1 block text-xs text-muted">
                    {item.observations
                      ? `${item.observations.baseline.status} / ${item.observations.target.status}`
                      : terminal(snapshot.status)
                        ? "Selection saved; no paired observations"
                        : "Selection saved; awaiting observations"}
                  </span>
                </button>
              </motion.li>
            ))}
          </ol>
        </nav>
      </div>
      {subject ? (
        <EvidenceInspector
          subject={subject}
          snapshot={snapshot}
          close={close}
        />
      ) : null}
    </motion.div>
  );
}
