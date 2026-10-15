import { useState } from "react";
import type { ReductionCaseView, ReductionPage } from "../contracts/evidence";
import { request } from "./api";

export default function ReductionCase({
  label,
  value,
  id,
}: {
  label: string;
  value: ReductionCaseView;
  id: string;
}) {
  const [extra, setExtra] = useState<{
    caseId: string;
    setup: string[];
    cursor: number | null;
  } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const saved = extra?.caseId === value.caseId ? extra : null;
  const setup = [...value.setup, ...(saved?.setup ?? [])];
  const cursor = saved ? saved.cursor : value.nextSetupCursor;
  async function more() {
    setLoading(true);
    try {
      const page = await request<ReductionPage>(
        `/api/investigations/${id}/reduction?caseId=${value.caseId}&setupCursor=${cursor}`,
      );
      if (page.case?.caseId !== value.caseId) throw new Error();
      setExtra({
        caseId: value.caseId,
        setup: [...(saved?.setup ?? []), ...page.case.setup],
        cursor: page.case.nextSetupCursor,
      });
      setError("");
    } catch {
      setError("We couldn't load the saved setup. Retry connection.");
    } finally {
      setLoading(false);
    }
  }
  return (
    <section className="min-w-0">
      <h4 className="font-semibold">{label}</h4>
      <pre className="mt-3 max-w-full overflow-x-auto border-l border-line pl-3 font-mono text-sm">
        {value.query}
      </pre>
      <p className="mt-4 text-xs text-muted">
        Setup statements: {setup.length} of {value.setupTotal}
      </p>
      {setup.length ? (
        <ol className="mt-2 space-y-3">
          {setup.map((query, index) => (
            <li key={index}>
              <pre className="max-w-full overflow-x-auto font-mono text-xs">
                {query}
              </pre>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 text-sm">
          {value.setupTotal === 0
            ? "No setup statements."
            : "Load the saved setup statements below."}
        </p>
      )}
      {cursor !== null ? (
        <button
          disabled={loading}
          className="mt-3 min-h-11 underline disabled:opacity-50"
          onClick={() => void more()}
        >
          {loading
            ? "Loading setup…"
            : setup.length === 0
              ? "Show setup statements"
              : "More setup statements"}
        </button>
      ) : null}
      {error ? (
        <p role="status" className="mt-3 text-sm text-failure">
          {error}
        </p>
      ) : null}
      <details className="mt-3">
        <summary className="min-h-11 cursor-pointer text-xs text-muted">
          Case evidence reference
        </summary>
        <p className="break-all font-mono text-xs">
          {value.caseId}
          <br />
          {value.caseRef.path}
          <br />
          {value.caseRef.sha256}
        </p>
      </details>
    </section>
  );
}
