import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { admissionStorageKey, savedStart } from "./admission";
import EngineIdentity from "./EngineIdentity";
import MissingInvestigation from "./MissingInvestigation";
import { request, terminal } from "./api";
import { useInvestigation } from "./useInvestigation";
import InvestigationConclusion from "./InvestigationConclusion";
import ReductionLineage from "./ReductionLineage";
import { reductionAction } from "./reductionCopy";
import EvidenceDisclosure from "./EvidenceDisclosure";
import { investigationStatus as labels } from "./investigationStatus";

export default function InvestigationPage({ id }: { id: string }) {
  const [retry, setRetry] = useState(0);
  const [cancelled, setCancelled] = useState(false);
  const {
    snapshot,
    evidence,
    reduction,
    conclusion,
    connection,
    missing,
    integrityError,
  } = useInvestigation(id, retry);
  const cancellation = useMutation({
    mutationFn: () =>
      request(`/api/investigations/${id}/cancel`, { method: "POST" }),
    retry: false,
    onSuccess: () => setCancelled(true),
    onSettled: () => setRetry((value) => value + 1),
  });
  if (missing) return <MissingInvestigation />;
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
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line py-6">
            <div className="min-w-0">
              <p className="break-all font-mono text-xs text-muted">
                {snapshot.id}
              </p>
              <h1 className="mt-2 text-2xl font-semibold">{snapshot.title}</h1>
            </div>
            <Link
              to="/"
              className="inline-flex min-h-11 items-center underline"
              onClick={() => {
                try {
                  if (savedStart()?.id === id)
                    sessionStorage.removeItem(admissionStorageKey);
                } catch {
                  return;
                }
              }}
            >
              New investigation
            </Link>
            <h2 className="sr-only">Engine pair</h2>
            <div className="grid w-full min-w-0 gap-4 sm:grid-cols-2">
              {snapshot.engines.map((engine, index) => (
                <EngineIdentity
                  key={engine.id}
                  role={index === 0 ? "Baseline" : "Target"}
                  engine={engine}
                />
              ))}
            </div>
          </div>
          <div className="border-b border-line py-6">
            <h2 className="text-xs uppercase tracking-wider text-muted">
              Current action
            </h2>
            <p
              className="mt-3 min-h-12 text-lg"
              aria-live="polite"
              aria-atomic="true"
            >
              {(snapshot.cancelRequestedAt || cancelled) &&
              !terminal(snapshot.status)
                ? "Cancellation requested. Finishing the current comparison and cleanup."
                : snapshot.status === "REDUCING" && snapshot.reduction
                  ? reductionAction(snapshot.reduction)
                  : (labels[snapshot.status] ?? "Loading saved progress…")}
            </p>
            {snapshot.terminalReason &&
            snapshot.terminalReason.message !== labels[snapshot.status] ? (
              <p className="mt-2 text-sm">{snapshot.terminalReason.message}</p>
            ) : null}
            <p className="mt-4 text-sm text-muted">
              Experiment budget: {snapshot.budget.reservedProbes} /{" "}
              {snapshot.budget.maxProbes} · Evidence:{" "}
              {snapshot.budget.chargedBytes.toLocaleString()} /{" "}
              {snapshot.budget.maxArtifactBytes.toLocaleString()} bytes
            </p>
            {!terminal(snapshot.status) ? (
              <button
                className="mt-5 min-h-11 border border-line px-4 disabled:opacity-50"
                disabled={
                  ["CLASSIFYING", "EXPORTING"].includes(snapshot.status) ||
                  cancellation.isPending ||
                  cancelled ||
                  Boolean(snapshot.cancelRequestedAt)
                }
                onClick={() => cancellation.mutate()}
              >
                {cancellation.isPending
                  ? "Saving cancellation…"
                  : "Cancel investigation"}
              </button>
            ) : null}
            {["CLASSIFYING", "EXPORTING"].includes(snapshot.status) ? (
              <p className="mt-2 text-sm text-muted">
                This investigation is finishing and can no longer be cancelled.
              </p>
            ) : null}
            {cancellation.error ? (
              <p role="status" className="mt-4 text-sm text-failure">
                We couldn’t confirm cancellation. Retry connection to check its
                saved status.
              </p>
            ) : null}
          </div>
          <div className="min-w-0 border-x border-line bg-surface">
            {reduction ? <ReductionLineage id={id} page={reduction} /> : null}
            {evidence ? (
              <EvidenceDisclosure page={evidence} snapshot={snapshot} />
            ) : null}
          </div>
          {conclusion ? (
            <InvestigationConclusion
              id={id}
              page={
                integrityError ? { ...conclusion, exports: null } : conclusion
              }
              snapshot={snapshot}
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}
