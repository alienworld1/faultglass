import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { eventTypes, parseEvent, terminal, RequestError } from "./api";
import { workspaceOptions } from "./queries";

export function useInvestigation(id: string, retry: number) {
  const client = useQueryClient();
  const options = workspaceOptions(id);
  const query = useQuery(options);
  const [connection, setConnection] = useState("Loading saved evidence…");
  useEffect(() => {
    let disposed = false;
    let source: EventSource | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let refreshTimer: ReturnType<typeof setTimeout> | undefined;
    let lastSequence = 0;
    let reconnects = 0;
    let reading = false;
    let again = false;
    const refresh = async () => {
      if (disposed) return;
      if (reading) {
        again = true;
        return;
      }
      reading = true;
      try {
        const state = await client.fetchQuery({
          ...workspaceOptions(id),
          staleTime: 0,
        });
        if (disposed) return;
        setConnection("");
        clearTimeout(timer);
        reconnects = 0;
        if (
          terminal(state.snapshot.status) &&
          lastSequence >= state.snapshot.lastEventSequence
        ) {
          source?.close();
          source = undefined;
        } else if (!source) connect();
      } catch (error) {
        if (disposed) return;
        if (
          error instanceof RequestError &&
          [404, 409, 422].includes(error.status)
        ) {
          source?.close();
          source = undefined;
          setConnection(
            error.status === 409
              ? "Saved evidence could not be verified. Previously confirmed evidence is stale."
              : error.message,
          );
        } else reconnect();
      } finally {
        reading = false;
        if (again && !disposed) {
          again = false;
          scheduleRefresh();
        }
      }
    };
    const scheduleRefresh = () => {
      clearTimeout(refreshTimer);
      refreshTimer = setTimeout(() => void refresh(), 120);
    };
    const reconnect = () => {
      if (disposed) return;
      source?.close();
      source = undefined;
      setConnection("Progress is temporarily unavailable. Reconnecting…");
      clearTimeout(timer);
      timer = setTimeout(
        () => void refresh(),
        Math.min(30000, 1000 * 2 ** Math.min(reconnects++, 5)),
      );
    };
    const connect = () => {
      if (disposed || source) return;
      source = new EventSource(
        `/api/investigations/${id}/events?after=${lastSequence}`,
      );
      const receive = (raw: MessageEvent<string>) => {
        try {
          const event = parseEvent(raw.data, id);
          if (event.sequence <= lastSequence) return;
          if (event.sequence !== lastSequence + 1) throw new Error();
          lastSequence = event.sequence;
          scheduleRefresh();
        } catch {
          reconnect();
        }
      };
      eventTypes.forEach((type) =>
        source?.addEventListener(type, receive as EventListener),
      );
      source.onerror = reconnect;
    };
    void refresh();
    return () => {
      disposed = true;
      source?.close();
      clearTimeout(timer);
      clearTimeout(refreshTimer);
      void client.cancelQueries({ queryKey: workspaceOptions(id).queryKey });
    };
  }, [id, retry, client]);
  return {
    snapshot: query.data?.snapshot ?? null,
    evidence: query.data?.evidence ?? null,
    reduction: query.data?.reduction ?? null,
    conclusion: query.data?.conclusion ?? null,
    connection,
    missing:
      query.error instanceof RequestError &&
      query.error.status === 404 &&
      !query.data,
    integrityError:
      query.error instanceof RequestError && query.error.status === 409,
  };
}
