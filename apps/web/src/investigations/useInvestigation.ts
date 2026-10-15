import { useEffect, useState } from "react";
import type { Event, Snapshot, ReductionPage } from "../contracts/evidence";
import type { SavedReduction } from "./api";
import { eventTypes, parseEvent, request, terminal, RequestError } from "./api";

export function useInvestigation(id: string, retry: number) {
  const [savedState, setSavedState] = useState<{
    snapshot: Snapshot | null;
    reduction: SavedReduction | null;
  }>({ snapshot: null, reduction: null });
  const snapshot = savedState.snapshot?.id === id ? savedState.snapshot : null;
  const reduction = snapshot ? savedState.reduction : null;
  const [events, setEvents] = useState<Event[]>([]);
  const [connection, setConnection] = useState("Loading investigation…");
  const [missing, setMissing] = useState(false);
  useEffect(() => {
    let disposed = false;
    let source: EventSource | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let lastSequence = 0;
    let fetching = false;
    let reconnects = 0;
    const controller = new AbortController();
    const loadSaved = async () => {
      for (let attempt = 0; attempt < 3; attempt++) {
        const saved = await request<Snapshot>(`/api/investigations/${id}`, {
          signal: controller.signal,
        });
        let page: SavedReduction | null = null;
        if (saved.reduction) {
          let loaded: SavedReduction = await request<ReductionPage>(
            `/api/investigations/${id}/reduction`,
            { signal: controller.signal },
          );
          while (loaded.nextCursor !== null) {
            const next: ReductionPage = await request<ReductionPage>(
              `/api/investigations/${id}/reduction?cursor=${loaded.nextCursor}`,
              { signal: controller.signal },
            );
            if (next.revision !== loaded.revision) break;
            loaded = {
              ...loaded,
              attempts: [...loaded.attempts, ...next.attempts].slice(0, 32),
              nextCursor: next.nextCursor,
            };
          }
          page = loaded;
          if (page.revision !== saved.revision || page.nextCursor !== null)
            continue;
        }
        if (!disposed) {
          setSavedState((previous) =>
            !previous.snapshot ||
            previous.snapshot.id !== id ||
            saved.revision >= previous.snapshot.revision
              ? { snapshot: saved, reduction: page }
              : previous,
          );
        }
        return saved;
      }
      throw new Error("Saved progress changed while loading.");
    };
    const reconcile = async () => {
      if (fetching || disposed) return;
      fetching = true;
      try {
        const saved = await loadSaved();
        if (disposed) return;
        if (
          saved.id !== id ||
          !Number.isInteger(saved.revision) ||
          !Number.isInteger(saved.lastEventSequence)
        )
          throw new Error();
        setConnection("");
        if (lastSequence > saved.lastEventSequence) {
          lastSequence = 0;
          setEvents([]);
        }
        reconnects = 0;
        if (!source) {
          // Replay from zero fills the bounded durable history, including a terminal investigation.
          source = new EventSource(
            `/api/investigations/${id}/events?after=${lastSequence}`,
          );
          const receive = (raw: MessageEvent<string>) => {
            try {
              const event = parseEvent(raw.data, id);
              if (event.sequence <= lastSequence) return;
              if (event.sequence !== lastSequence + 1) throw new Error();
              lastSequence = event.sequence;
              setEvents((previous) =>
                previous.some((item) => item.id === event.id)
                  ? previous
                  : [...previous, event].slice(-512),
              );
              if (
                terminal(event.data.status) &&
                event.sequence >= saved.lastEventSequence
              ) {
                source?.close();
                source = undefined;
              }
              void refresh();
            } catch {
              reconnect();
            }
          };
          eventTypes.forEach((type) =>
            source?.addEventListener(type, receive as EventListener),
          );
          source.onopen = () => {
            if (!disposed) setConnection("");
          };
          source.onerror = reconnect;
        }
        if (terminal(saved.status) && lastSequence >= saved.lastEventSequence) {
          source?.close();
          source = undefined;
        }
      } catch (error) {
        if (disposed) return;
        if (error instanceof RequestError && error.status === 404) {
          setMissing(true);
          setConnection("");
          return;
        }
        if (error instanceof RequestError && error.status === 409) {
          setConnection(error.message);
          return;
        }
        reconnect();
      } finally {
        fetching = false;
      }
    };
    let refreshing = false;
    let refreshAgain = false;
    const refresh = async () => {
      if (refreshing) {
        refreshAgain = true;
        return;
      }
      refreshing = true;
      try {
        await loadSaved();
      } catch {
        if (!disposed) reconnect();
      } finally {
        refreshing = false;
        if (refreshAgain && !disposed) {
          refreshAgain = false;
          void refresh();
        }
      }
    };
    const reconnect = () => {
      if (disposed) return;
      source?.close();
      source = undefined;
      setConnection("Progress is temporarily unavailable. Reconnecting…");
      clearTimeout(timer);
      timer = setTimeout(
        () => void reconcile(),
        Math.min(30000, 1000 * 2 ** Math.min(reconnects++, 5)),
      );
    };
    void reconcile();
    return () => {
      disposed = true;
      controller.abort();
      source?.close();
      clearTimeout(timer);
    };
  }, [id, retry]);
  return {
    snapshot,
    reduction,
    events: events.filter((event) => event.investigationId === id),
    connection,
    missing,
  };
}
