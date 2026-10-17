import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import type { Snapshot } from "../contracts/evidence";
import { request, RequestError } from "./api";
import {
  admissionStorageKey,
  requestDigest,
  savedStart,
  saveStart,
} from "./admission";

export function useAdmission() {
  const navigate = useNavigate();
  const [saved, setSaved] = useState(savedStart);
  const [uncertain, setUncertain] = useState(Boolean(saved));
  const [message, setMessage] = useState("");
  const locked = useRef(false);
  const start = useMutation({
    mutationFn: async ({
      caseFile,
      pairId,
    }: {
      caseFile: string;
      pairId: string;
    }) => {
      const body = JSON.stringify({ caseFile, pairId });
      const digest = await requestDigest(body);
      const existing = savedStart();
      if (existing && existing.requestDigest !== digest)
        throw new Error(
          "Choose the same case to recover your start, or start a new investigation after checking its status.",
        );
      const admission = existing ?? {
        version: 1 as const,
        key: crypto.randomUUID(),
        requestDigest: digest,
      };
      saveStart(admission);
      setSaved(admission);
      setUncertain(true);
      const result = await request<{ investigation: Snapshot }>(
        "/api/investigations",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": admission.key,
          },
          body,
        },
      );
      saveStart({ ...admission, id: result.investigation.id });
      navigate(`/investigations/${result.investigation.id}`);
    },
    retry: false,
    onError: (error) => {
      setMessage(error.message);
      if (
        !savedStart() ||
        (error instanceof RequestError &&
          [403, 413, 422, 429, 503].includes(error.status))
      )
        setUncertain(false);
    },
    onSettled: () => {
      locked.current = false;
    },
  });
  const recovery = useQuery({
    queryKey: ["admission", saved?.key],
    enabled: Boolean(saved) && uncertain && !start.isPending,
    queryFn: async ({ signal }) => {
      try {
        const result = await request<{ id: string }>(
          `/api/investigations/admission/${saved!.key}`,
          { signal },
        );
        if (!signal.aborted) saveStart({ ...saved!, id: result.id });
        return result;
      } catch (error) {
        if (!signal.aborted) {
          if (error instanceof RequestError && error.status === 404) {
            setUncertain(false);
            setMessage(
              "Your previous start was not found. Retry with the same case, or choose Start a new investigation.",
            );
          } else
            setMessage(
              error instanceof Error
                ? error.message
                : "We couldn’t confirm your previous start. Retry connection before starting again.",
            );
        }
        throw error;
      }
    },
    retry: false,
  });
  useEffect(() => {
    if (recovery.data) navigate(`/investigations/${recovery.data.id}`);
  }, [recovery.data, navigate]);
  return {
    pending: start.isPending,
    uncertain,
    message,
    hasRecovery: Boolean(saved),
    retry: () => {
      if (saved) void recovery.refetch();
    },
    submit: (caseFile: string, pairId: string) => {
      if (locked.current || uncertain) return;
      locked.current = true;
      start.mutate({ caseFile, pairId });
    },
    clear: () => {
      if (uncertain || start.isPending) return;
      try {
        sessionStorage.removeItem(admissionStorageKey);
        setSaved(null);
        setMessage("");
      } catch {
        setMessage(
          "We couldn’t save your start details. Allow browser storage and try again.",
        );
      }
    },
  };
}
