import { useState } from "react";
import type { EvidencePage } from "../contracts/evidence";
import { request } from "./api";
import ExperimentReason from "./ExperimentReason";
import PairedEvidence from "./PairedEvidence";

export default function EvidenceDisclosure({
  id,
  revision,
}: {
  id: string;
  revision: number;
}) {
  const [page, setPage] = useState<EvidencePage | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  async function load(cursor = 0) {
    setLoading(true);
    try {
      setPage(
        await request<EvidencePage>(
          `/api/investigations/${id}/evidence?cursor=${cursor}`,
        ),
      );
      setError("");
    } catch {
      setError("Evidence is temporarily unavailable. Retry connection.");
    } finally {
      setLoading(false);
    }
  }
  return (
    <details
      className="border-b border-line py-6"
      onToggle={(event) => {
        if (event.currentTarget.open && (!page || page.revision < revision))
          void load();
      }}
    >
      <summary className="min-h-11 cursor-pointer font-semibold">
        Evidence
      </summary>
      {loading ? (
        <p className="text-sm text-muted">Loading saved evidence…</p>
      ) : null}
      {error ? (
        <p role="status">
          {error}
          <button
            className="ml-3 min-h-11 underline"
            onClick={() => void load()}
          >
            Retry connection
          </button>
        </p>
      ) : null}
      {page?.items.map((item, index) => (
        <article
          key={`${item.sequence}:${item.kind}:${index}`}
          className="min-w-0 border-t border-line py-6"
        >
          <h3 className="mb-4 font-semibold">
            {item.sequence === 0
              ? "Original comparison"
              : `Experiment ${item.sequence}`}{" "}
            ·{" "}
            {item.kind === "selection"
              ? "Why this experiment?"
              : "Paired observations"}
          </h3>
          {item.query ? (
            <pre className="mb-5 overflow-x-auto font-mono text-sm">
              {item.query}
            </pre>
          ) : null}
          {item.observations ? (
            <PairedEvidence observations={item.observations} />
          ) : null}
          {item.decision ? <ExperimentReason data={item.decision} /> : null}
          <details className="mt-4">
            <summary className="min-h-11 cursor-pointer text-sm">
              Verified artifact metadata
            </summary>
            <ul className="space-y-4">
              {item.references.map((ref) => (
                <li
                  key={`${ref.owner}/${ref.path}`}
                  className="break-all font-mono text-xs"
                >
                  {ref.kind} · {ref.bytes} bytes
                  <br />
                  {ref.sha256}
                </li>
              ))}
            </ul>
          </details>
        </article>
      ))}
      {page && page.items.length === 0 ? (
        <p className="text-sm text-muted">
          No comparison evidence has been recorded yet.
        </p>
      ) : null}
      {page?.nextCursor != null ? (
        <button
          className="min-h-11 underline"
          onClick={() => void load(page.nextCursor!)}
        >
          More evidence
        </button>
      ) : null}
    </details>
  );
}
