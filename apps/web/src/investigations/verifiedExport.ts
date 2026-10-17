import type { DownloadReference } from "../contracts/evidence";
export async function verifiedExport(
  id: string,
  file: DownloadReference,
  signal?: AbortSignal,
) {
  if (
    file.owner.split("/")[0] !== id ||
    !["case", "regression-test", "report"].includes(file.key)
  )
    throw new Error("This download could not be verified.");
  const response = await fetch(`/api/investigations/${id}/export/${file.key}`, {
    signal,
  });
  if (!response.ok) throw new Error("This download could not be verified.");
  const data = await response.arrayBuffer();
  const hash = await crypto.subtle.digest("SHA-256", data);
  const digest = Array.from(new Uint8Array(hash), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  if (data.byteLength !== file.bytes || digest !== file.sha256)
    throw new Error("This download could not be verified.");
  return new Blob([data], { type: file.mediaType });
}
