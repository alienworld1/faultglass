import type {
  Event,
  Snapshot,
  ReductionPage,
  ReductionAttemptView,
} from "../contracts/evidence";

export class RequestError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function request<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok)
    throw new RequestError(
      body.error?.message ?? "We couldn’t load this investigation.",
      response.status,
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
