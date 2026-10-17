import { queryOptions } from "@tanstack/react-query";
import type {
  Snapshot,
  EvidencePage,
  ReductionPage,
  ConclusionPage,
} from "../contracts/evidence";
import { request, RequestError } from "./api";

export const retryRead = (count: number, error: Error) =>
  count < 2 &&
  !(
    error instanceof RequestError && [404, 409, 413, 422].includes(error.status)
  );
export const investigationKey = (id: string) => ["investigation", id] as const;

export async function readWorkspace(id: string, signal: AbortSignal) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const snapshot = await request<Snapshot>(`/api/investigations/${id}`, {
      signal,
    });
    if (
      snapshot.id !== id ||
      !Number.isInteger(snapshot.revision) ||
      !Number.isInteger(snapshot.lastEventSequence)
    )
      throw new RequestError("Saved evidence could not be verified.", 409);
    const [evidence, reduction, conclusion] = await Promise.all([
      readPages<EvidencePage>(id, "evidence", "items", signal),
      snapshot.reduction
        ? readPages<ReductionPage>(id, "reduction", "attempts", signal)
        : null,
      readPages<ConclusionPage>(id, "conclusion", "candidates", signal),
    ]);
    if (
      [evidence, reduction, conclusion].every(
        (page) => !page || page.revision === snapshot.revision,
      )
    ) {
      if (
        (reduction?.case &&
          reduction.case.caseId !== snapshot.reduction?.currentCaseId) ||
        (conclusion.exports && conclusion.exports.investigationId !== id)
      )
        throw new RequestError("Saved evidence could not be verified.", 409);
      return { snapshot, evidence, reduction, conclusion };
    }
  }
  throw new Error("Saved progress changed while loading. Retry connection.");
}

async function readPages<
  T extends EvidencePage | ReductionPage | ConclusionPage,
>(
  id: string,
  endpoint: string,
  field: "items" | "attempts" | "candidates",
  signal: AbortSignal,
): Promise<T> {
  let page = await request<T>(`/api/investigations/${id}/${endpoint}`, {
    signal,
  });
  const check = (value: T) => {
    const items = (value as unknown as Record<string, unknown>)[field];
    if (
      !Number.isInteger(value.revision) ||
      !Array.isArray(items) ||
      !(
        value.nextCursor === null ||
        (Number.isInteger(value.nextCursor) && value.nextCursor >= 0)
      )
    )
      throw new RequestError("Saved evidence could not be verified.", 409);
  };
  check(page);
  const cursors = new Set<number>();
  while (page.nextCursor !== null) {
    const cursor = page.nextCursor;
    if (cursors.has(cursor) || cursors.size >= 64)
      throw new RequestError("Saved evidence could not be verified.", 409);
    cursors.add(cursor);
    const next = await request<T>(
      `/api/investigations/${id}/${endpoint}?cursor=${cursor}`,
      { signal },
    );
    check(next);
    if (next.revision !== page.revision)
      throw new Error(
        "Saved progress changed while loading. Retry connection.",
      );
    page = {
      ...page,
      [field]: [
        ...(page as unknown as Record<string, unknown[]>)[field],
        ...(next as unknown as Record<string, unknown[]>)[field],
      ],
      nextCursor: next.nextCursor,
    };
  }
  return page;
}

export const workspaceOptions = (id: string) =>
  queryOptions({
    queryKey: [...investigationKey(id), "workspace"],
    queryFn: ({ signal }) => readWorkspace(id, signal),
    retry: retryRead,
    gcTime: 0,
    structuralSharing: (oldData, newData) => {
      const previous = oldData as
        Awaited<ReturnType<typeof readWorkspace>> | undefined;
      const next = newData as Awaited<ReturnType<typeof readWorkspace>>;
      return previous && previous.snapshot.revision > next.snapshot.revision
        ? previous
        : next;
    },
  });
