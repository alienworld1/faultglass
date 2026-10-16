import { useState } from "react";
import type { ExportManifest } from "../contracts/evidence";

export default function RegressionDownloads({
  id,
  manifest,
}: {
  id: string;
  manifest: ExportManifest;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const labels = {
    case: "Download case",
    "regression-test": "Download regression test",
    report: "Download report",
  };
  async function download(key: string, filename: string) {
    try {
      const response = await fetch(`/api/investigations/${id}/export/${key}`);
      if (!response.ok) throw new Error();
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage("Download prepared.");
    } catch {
      setMessage(
        "This download could not be verified. Your saved conclusion is preserved.",
      );
    }
  }
  async function showTest() {
    setOpen((value) => !value);
    if (preview !== null) return;
    setPending(true);
    try {
      const response = await fetch(
        `/api/investigations/${id}/export/regression-test`,
      );
      if (!response.ok) throw new Error();
      setPreview(await response.text());
    } catch {
      setMessage(
        "This download could not be verified. Retry connection to check its saved status.",
      );
    } finally {
      setPending(false);
    }
  }
  async function copy() {
    if (preview === null) return;
    try {
      await navigator.clipboard.writeText(preview);
      setMessage("Regression test copied.");
    } catch {
      setMessage(
        "We couldn’t copy the test. Select the text below to copy it.",
      );
    }
  }
  return (
    <div className="border-t border-line py-6">
      <h4 className="font-semibold">Take the evidence with you</h4>
      <p className="mt-3 text-sm text-muted">
        Smallest case retained by the supported reductions.{" "}
        {manifest.expectationBasis === "baseline_observation"
          ? "The test records observed baseline compatibility behavior; it does not establish universal correctness."
          : manifest.expectationBasis === "unasserted"
            ? "No supported expected behavior was available for this assertion."
            : "The test encodes the case’s explicit expectation."}{" "}
        Wire its disposable graph fixture into your repository before use.
      </p>
      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
        {manifest.files.map((file) => (
          <a
            key={file.key}
            className="inline-flex min-h-11 items-center underline"
            href={`/api/investigations/${id}/export/${file.key}`}
            download={file.path}
            onClick={(event) => {
              if (
                !event.ctrlKey &&
                !event.metaKey &&
                !event.shiftKey &&
                !event.altKey
              ) {
                event.preventDefault();
                void download(file.key, file.path);
              }
            }}
          >
            {labels[file.key]}
          </a>
        ))}
      </div>
      <button
        className="mt-3 min-h-11 underline"
        aria-expanded={open}
        onClick={() => void showTest()}
      >
        {open ? "Hide regression test" : "Show regression test"}
      </button>
      {open ? (
        <div>
          {pending ? <p role="status">Loading regression test…</p> : null}
          {preview !== null ? (
            <>
              <button
                className="min-h-11 border border-line px-4"
                onClick={() => void copy()}
              >
                Copy test
              </button>
              <pre
                tabIndex={0}
                className="mt-4 max-h-96 overflow-auto border border-line bg-surface p-4 font-mono text-xs"
              >
                {preview}
              </pre>
            </>
          ) : null}
        </div>
      ) : null}
      {message ? (
        <p role="status" className="mt-3 text-sm">
          {message}
        </p>
      ) : null}
    </div>
  );
}
