import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import type { ExportManifest, DownloadReference } from "../contracts/evidence";
import { investigationKey } from "./queries";
import { verifiedExport } from "./verifiedExport";
export default function RegressionDownloads({
  id,
  manifest,
}: {
  id: string;
  manifest: ExportManifest;
}) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const labels = {
    case: "Download case",
    "regression-test": "Download regression test",
    report: "Download evidence report",
  };
  const test = manifest.files.find((file) => file.key === "regression-test");
  const preview = useQuery({
    queryKey: [...investigationKey(id), "export", test?.sha256],
    enabled: open && Boolean(test),
    retry: false,
    queryFn: async ({ signal }) =>
      (await verifiedExport(id, test!, signal)).text(),
  });
  const download = useMutation({
    retry: false,
    mutationFn: async (file: DownloadReference) => {
      const url = URL.createObjectURL(await verifiedExport(id, file));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.path.split("/").at(-1) ?? file.key;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    onSuccess: () => setMessage("Download prepared."),
    onError: () =>
      setMessage(
        "This download could not be verified. Your saved conclusion is preserved.",
      ),
  });
  async function copy() {
    if (!preview.data) return;
    try {
      await navigator.clipboard.writeText(preview.data);
      setMessage("Regression test copied.");
    } catch {
      setMessage(
        "We couldn’t copy the test. Select the text below to copy it.",
      );
    }
  }
  return (
    <div className="border-t border-line py-6">
      <h3 className="font-semibold">Take the evidence with you</h3>
      <p className="mt-3 text-sm text-muted">
        Smaller verified case retained by the supported reductions; global
        minimality is not established.{" "}
        {manifest.expectationBasis === "baseline_observation"
          ? "The test records observed baseline compatibility behavior; it does not establish universal correctness."
          : manifest.expectationBasis === "unasserted"
            ? "No supported expected behavior was available for this assertion."
            : "The test encodes the case’s explicit expectation."}{" "}
        The regression test is a scaffold requiring your repository harness.
        Wire its disposable graph fixture into your repository before use.
      </p>
      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
        {manifest.files.map((file) => (
          <button
            key={file.key}
            disabled={download.isPending}
            className="min-h-11 underline disabled:opacity-50"
            onClick={() => download.mutate(file)}
          >
            {labels[file.key]}
          </button>
        ))}
      </div>
      {download.isPending ? (
        <p className="mt-2 text-sm" role="status">
          Verifying download…
        </p>
      ) : null}
      {test ? (
        <button
          className="mt-3 min-h-11 underline"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Hide regression test" : "Show regression test"}
        </button>
      ) : null}
      {open ? (
        <div>
          {preview.isFetching ? (
            <p role="status">Loading regression test…</p>
          ) : null}
          {preview.error ? (
            <p className="text-sm text-failure" role="status">
              This download could not be verified.{" "}
              <button
                className="min-h-11 underline"
                onClick={() => void preview.refetch()}
              >
                Retry download
              </button>
            </p>
          ) : null}
          {preview.data !== undefined ? (
            <>
              <button
                className="min-h-11 border border-line px-4"
                onClick={() => void copy()}
              >
                Copy test
              </button>
              <pre
                tabIndex={0}
                className="mt-4 max-h-96 overflow-auto border-l-2 border-line-strong bg-secondary p-4 font-mono text-xs"
              >
                {preview.data}
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
