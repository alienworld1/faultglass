import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ReductionPage } from "../contracts/evidence";
import { request } from "./api";
import { investigationKey, retryRead } from "./queries";
import ReductionCase from "./ReductionCase";
export default function ReductionCaseLoader({
  id,
  caseId,
  label,
}: {
  id: string;
  caseId: string;
  label: string;
}) {
  const [enabled, setEnabled] = useState(false);
  const query = useQuery({
    queryKey: [...investigationKey(id), "case", caseId],
    enabled,
    retry: retryRead,
    queryFn: async ({ signal }) => {
      const page = await request<ReductionPage>(
        `/api/investigations/${id}/reduction?caseId=${encodeURIComponent(caseId)}`,
        { signal },
      );
      if (page.case?.caseId !== caseId)
        throw new Error("Saved evidence could not be verified.");
      return page.case;
    },
  });
  if (query.data)
    return <ReductionCase id={id} label={label} value={query.data} />;
  return (
    <div className="min-w-0">
      <button
        className="min-h-11 underline disabled:opacity-50"
        disabled={query.isFetching}
        onClick={() => {
          setEnabled(true);
          if (enabled) void query.refetch();
        }}
      >
        {query.isFetching ? "Loading case…" : `Inspect ${label.toLowerCase()}`}
      </button>
      {query.error ? (
        <p className="text-sm text-failure" role="status">
          We couldn’t load this saved case. Retry the case read.
        </p>
      ) : null}
    </div>
  );
}
