import { useState } from "react";
import { request, terminal } from "./api";
import { useInvestigation } from "./useInvestigation";
import EvidenceDisclosure from "./EvidenceDisclosure";

const labels: Record<string, string> = {
  QUEUED: "Waiting to investigate.",
  FINGERPRINTING: "Fingerprinting case",
  REPRODUCING: "Reproducing the difference",
  PLANNING: "Choosing an experiment",
  PROBING: "Running an experiment",
  NOT_REPRODUCED: "No difference observed for this case and engine pair.",
  UNRESOLVED: "Investigation ended without a supported conclusion.",
  CANCELLED: "Investigation cancelled. Collected evidence is preserved.",
  FAILED: "We couldn’t finish this investigation.",
};

export default function InvestigationPage({ id }: { id: string }) {
  const [retry, setRetry] = useState(0);
  const [cancelPending, setCancelPending] = useState(false);
  const [cancelled, setCancelled] = useState(false);
  const [error, setError] = useState("");
  const [visible, setVisible] = useState(30);
  const { snapshot, events, connection, missing } = useInvestigation(id, retry);
  async function cancel() {
    setCancelPending(true);
    try {
      await request(`/api/investigations/${id}/cancel`, { method: "POST" });
      setCancelled(true);
    } catch {
      setError(
        "We couldn’t confirm cancellation. Retry connection to check its saved status.",
      );
    } finally {
      setCancelPending(false);
    }
  }
  if (missing)
    return <p className="py-8">We couldn’t find that investigation.</p>;
  return (
    <section className="min-w-0">
      {connection ? (
        <div className="border-b border-line py-5">
          <p role="status">{connection}</p>
          {snapshot ? (
            <p className="mt-2 text-sm text-muted">
              Last confirmed: {new Date(snapshot.updatedAt).toLocaleString()}
            </p>
          ) : null}
          <button
            className="mt-3 min-h-11 underline"
            onClick={() => setRetry((value) => value + 1)}
          >
            Retry connection
          </button>
        </div>
      ) : null}
      {snapshot ? (
        <>
          <div className="border-b border-line py-8">
            <p className="break-all font-mono text-xs text-muted">
              {snapshot.id}
            </p>
            <h2 className="mt-3 text-2xl font-semibold">{snapshot.title}</h2>
            <div className="mt-6 grid gap-6 sm:grid-cols-2">
              {snapshot.engines.map((engine, index) => (
                <div className="min-w-0" key={index}>
                  <h3 className="font-semibold">
                    {index === 0 ? "Baseline" : "Target"}
                  </h3>
                  <p className="mt-2 font-mono text-sm">{engine.label}</p>
                  <p className="mt-2 break-all font-mono text-xs text-muted">
                    {engine.commitSha}
                    <br />
                    {engine.imageDigest}
                  </p>
                </div>
              ))}
            </div>
          </div>
          <div className="border-b border-line py-6">
            <h3 className="text-xs uppercase tracking-wider text-muted">
              Current action
            </h3>
            <p
              className="mt-3 min-h-12 text-lg"
              aria-live="polite"
              aria-atomic="true"
            >
              {(snapshot.cancelRequestedAt || cancelled) &&
              !terminal(snapshot.status)
                ? "Cancellation requested. Finishing the current comparison and cleanup."
                : (labels[snapshot.status] ?? snapshot.status)}
            </p>
            {snapshot.terminalReason ? (
              <p className="mt-2 text-sm">{snapshot.terminalReason.message}</p>
            ) : null}
            <p className="mt-4 text-sm text-muted">
              Experiments reserved: {snapshot.budget.reservedProbes} /{" "}
              {snapshot.budget.maxProbes} · Evidence:{" "}
              {snapshot.budget.chargedBytes.toLocaleString()} /{" "}
              {snapshot.budget.maxArtifactBytes.toLocaleString()} bytes
            </p>
            {!terminal(snapshot.status) ? (
              <button
                className="mt-5 min-h-11 border border-line px-4 disabled:opacity-50"
                disabled={
                  cancelPending ||
                  cancelled ||
                  Boolean(snapshot.cancelRequestedAt)
                }
                onClick={() => void cancel()}
              >
                {cancelPending
                  ? "Saving cancellation…"
                  : "Cancel investigation"}
              </button>
            ) : null}
            {error ? (
              <p role="status" className="mt-4 text-sm text-failure">
                {error}
              </p>
            ) : null}
          </div>
          <EvidenceDisclosure id={id} revision={snapshot.revision} />
          <div className="border-b border-line py-6">
            <h3 className="font-semibold">Chronological trace</h3>
            {events.length > visible ? (
              <button
                className="mt-3 min-h-11 underline"
                onClick={() => setVisible((value) => Math.min(512, value + 30))}
              >
                Show older events
              </button>
            ) : null}
            <ol className="mt-5 divide-y divide-line">
              {events.slice(-visible).map((event) => (
                <li
                  key={event.id}
                  className="grid gap-2 py-4 sm:grid-cols-[9rem_1fr]"
                >
                  <time
                    className="font-mono text-xs text-muted"
                    dateTime={event.at}
                  >
                    {new Date(event.at).toLocaleTimeString()}
                  </time>
                  <p className="text-sm">{event.summary}</p>
                </li>
              ))}
            </ol>
          </div>
        </>
      ) : null}
    </section>
  );
}
