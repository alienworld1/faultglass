import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";
import type { RecentInvestigations as RecentPage } from "../contracts/evidence";
import { request, RequestError } from "./api";
import { retryRead } from "./queries";
import { investigationStatus } from "./investigationStatus";

export default function RecentInvestigations() {
  const [open, setOpen] = useState(false);
  const recent = useQuery({
    queryKey: ["recent-investigations"],
    enabled: open,
    queryFn: async ({ signal }) => {
      const page = await request<RecentPage>("/api/investigations", { signal });
      if (!Array.isArray(page.items))
        throw new RequestError("We couldn’t read recent investigations.", 409);
      return page;
    },
    retry: retryRead,
    refetchInterval: 15000,
  });
  return (
    <details
      className="mb-6 border-y border-line"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="min-h-11 cursor-pointer py-4 font-semibold">
        Recent investigations
        {recent.data ? ` · ${recent.data.items.length}` : ""}
      </summary>
      {recent.isPending ? (
        <p role="status" className="pb-4 text-sm">
          Loading recent investigations…
        </p>
      ) : null}
      {recent.error ? (
        <p role="status" className="pb-4 text-sm">
          We couldn’t load recent investigations.{" "}
          <button
            className="min-h-11 underline"
            onClick={() => void recent.refetch()}
          >
            Retry recent investigations
          </button>
        </p>
      ) : recent.data?.items.length === 0 ? (
        <p className="pb-4 text-sm text-muted">
          Your investigations will appear here after you start a case.
        </p>
      ) : null}
      <ul className="divide-y divide-line">
        {recent.data?.items.map((item) => (
          <li key={item.id} className="min-w-0 py-4">
            <Link
              className="inline-flex min-h-11 items-center break-words font-semibold underline"
              to={`/investigations/${item.id}`}
            >
              {item.title}
            </Link>
            <p className="mt-1 text-sm">{investigationStatus[item.status]}</p>
            <p className="mt-2 break-words text-sm text-muted">
              {item.baseline} → {item.target} · {item.plannedExperiments}{" "}
              {item.plannedExperiments === 1 ? "experiment" : "experiments"}{" "}
              planned
            </p>
            {item.verifiedDifferences != null ? (
              <p className="mt-2 text-sm">
                {item.verifiedDifferences} verified{" "}
                {item.verifiedDifferences === 1 ? "difference" : "differences"}
                {item.sourceBehavior ? ` · Source: ${item.sourceBehavior}` : ""}
              </p>
            ) : null}
            {item.familyState ? (
              <p className="mt-2 text-sm capitalize">
                {item.familyState} behavioral family
              </p>
            ) : null}
            <p className="mt-2 break-all font-mono text-xs text-muted">
              {item.id}
            </p>
            <p className="mt-2 text-xs text-muted">
              Updated{" "}
              <time dateTime={item.updatedAt}>
                {new Date(item.updatedAt).toLocaleString()}
              </time>
            </p>
          </li>
        ))}
      </ul>
      {recent.data?.items.length ? (
        <p className="py-4 text-xs text-muted">
          The 10 most recently updated investigations in this shared workspace.
        </p>
      ) : null}
    </details>
  );
}
