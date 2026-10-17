import type {
  Event,
  Snapshot,
  ReductionPage,
  ReductionAttemptView,
} from "../contracts/evidence";

export class RequestError extends Error {
  status: number;
  fields: { path: string; message: string }[];
  code: string;
  retryAfterMs: number;
  constructor(
    message: string,
    status: number,
    fields: { path: string; message: string }[] = [],
    code = "",
    retryAfterMs = 0,
  ) {
    super(message);
    this.status = status;
    this.fields = fields;
    this.code = code;
    this.retryAfterMs = retryAfterMs;
  }
}

export async function request<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(url, options);
  const retryHeader = response.headers.get("Retry-After");
  const retryAfterMs = retryHeader
    ? /^\d+$/.test(retryHeader)
      ? Number(retryHeader) * 1000
      : Math.max(0, Date.parse(retryHeader) - Date.now())
    : 0;
  const retryDelay = Number.isFinite(retryAfterMs) ? retryAfterMs : 0;
  const fallback =
    response.status === 429
      ? "The workspace is busy. Try again shortly."
      : response.status === 413
        ? "Choose a case file smaller than 256 KiB."
        : response.status === 403
          ? "This page cannot start or change investigations."
          : response.status === 408
            ? "The request took too long. Try again shortly."
            : "Investigations are temporarily unavailable. Retry connection.";
  let body;
  try {
    body = await response.json();
  } catch {
    throw new RequestError(
      response.ok
        ? "We couldn’t read this evidence. Retry connection."
        : fallback,
      response.ok ? 409 : response.status,
      [],
      "",
      retryDelay,
    );
  }
  if (!response.ok)
    throw new RequestError(
      body?.error?.message ?? fallback,
      response.status,
      Array.isArray(body?.error?.fields)
        ? body.error.fields.filter(
            (field: { path?: unknown; message?: unknown }) =>
              typeof field.path === "string" &&
              typeof field.message === "string",
          )
        : [],
      body?.error?.code ?? "",
      retryDelay,
    );
  return body as T;
}

export const terminal = (status: Snapshot["status"]) =>
  ["COMPLETE", "NOT_REPRODUCED", "UNRESOLVED", "CANCELLED", "FAILED"].includes(
    status,
  );
export const eventTypes = [
  "investigation.created",
  "phase.started",
  "fingerprint.completed",
  "graph.read",
  "probe.candidates",
  "probe.selected",
  "engine.observed",
  "divergence.detected",
  "graph.write",
  "reduction.started",
  "reduction.verifying",
  "reduction.accepted",
  "reduction.rejected",
  "reduction.finished",
  "agent.action",
  "agent.degraded",
  "family.matched",
  "family.provisional",
  "family.unresolved",
  "export.ready",
  "memory.updated",
  "investigation.complete",
  "cancellation.requested",
  "investigation.not_reproduced",
  "investigation.unresolved",
  "investigation.cancelled",
  "investigation.failed",
] as const;

export function parseEvent(data: string, id: string): Event {
  const value = JSON.parse(data) as Event;
  if (
    value.investigationId !== id ||
    !Number.isInteger(value.sequence) ||
    value.sequence < 1 ||
    value.sequence > 512 ||
    value.id !== `${id}:${value.sequence}` ||
    typeof value.summary !== "string" ||
    value.summary.length > 256 ||
    !eventTypes.includes(value.type) ||
    !Number.isInteger(value.data?.revision)
  )
    throw new Error("The saved trace needs to reconnect.");
  return value;
}

export type SavedReduction = Omit<ReductionPage, "attempts"> & {
  attempts: ReductionAttemptView[];
};
