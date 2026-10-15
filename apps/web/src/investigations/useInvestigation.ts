import { useEffect, useState } from "react";
import type { Event, Snapshot } from "../contracts/evidence";
import { eventTypes, parseEvent, request, terminal, RequestError } from "./api";

export function useInvestigation(id: string, retry: number) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
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
    const reconcile = async () => {
      if (fetching || disposed) return;
      fetching = true;
      try {
        const saved = await request<Snapshot>(`/api/investigations/${id}`, {
          signal: controller.signal,
        });
        if (disposed) return;
        if (
          saved.id !== id ||
          !Number.isInteger(saved.revision) ||
          !Number.isInteger(saved.lastEventSequence)
        )
          throw new Error();
        setSnapshot((previous) =>
          !previous || saved.revision >= previous.revision ? saved : previous,
        );
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
        const saved = await request<Snapshot>(`/api/investigations/${id}`, {
          signal: controller.signal,
        });
        if (!disposed)
          setSnapshot((previous) =>
            !previous || saved.revision >= previous.revision ? saved : previous,
          );
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
  return { snapshot, events, connection, missing };
}
