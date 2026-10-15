import { useState } from "react";
import type { ReductionCaseView, ReductionPage } from "../contracts/evidence";
import { request } from "./api";
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
  const [value, setValue] = useState<ReductionCaseView | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function load() {
    setLoading(true);
    try {
      const page = await request<ReductionPage>(
        `/api/investigations/${id}/reduction?caseId=${caseId}`,
      );
      if (page.case?.caseId !== caseId) throw new Error();
      setValue(page.case);
      setError("");
    } catch {
      setError("We couldn't load this saved case. Retry connection.");
    } finally {
      setLoading(false);
    }
  }
  if (value) return <ReductionCase id={id} label={label} value={value} />;
  return (
    <div className="min-w-0">
      <button
        className="min-h-11 underline disabled:opacity-50"
        disabled={loading}
        onClick={() => void load()}
      >
        {loading ? "Loading case…" : `Inspect ${label.toLowerCase()}`}
      </button>
      {error ? (
        <p className="text-sm text-failure" role="status">
          {error}
        </p>
      ) : null}
    </div>
  );
}
