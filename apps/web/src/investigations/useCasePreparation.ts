import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { EnginePair, EngineSpec } from "../contracts/evidence";
import builtInCase from "../cases/call-yield.faultglass.json";
import { request } from "./api";
import { retryRead } from "./queries";
import { useDebouncedValue } from "./useDebouncedValue";

const builtIn = JSON.stringify(builtInCase, null, 2);
type Matrix = {
  engines: EngineSpec[];
  pairs: (EnginePair & { available: boolean })[];
};
type Health = {
  workerReady: boolean;
  contextReady: boolean;
  executionReady: boolean;
  agentReady: boolean;
  agentMode: string;
};
export function useCasePreparation() {
  const [pairId, setPairId] = useState("call-yield-c-rust");
  const [caseFile, setCaseFile] = useState(builtIn);
  const [importError, setImportError] = useState("");
  const [focusErrors, setFocusErrors] = useState(false);
  const [importing, setImporting] = useState(false);
  const importGeneration = useRef(0);
  const [draftVersion, setDraftVersion] = useState(0);
  const errorSummary = useRef<HTMLDivElement>(null);
  const settledVersion = useDebouncedValue(draftVersion, 350);
  const editing = settledVersion !== draftVersion;
  const matrix = useQuery({
    queryKey: ["engine-matrix"],
    queryFn: ({ signal }) => request<Matrix>("/api/engine-matrix", { signal }),
    retry: retryRead,
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => request<Health>("/api/health", { signal }),
    retry: retryRead,
    refetchInterval: 15000,
  });
  const validation = useQuery({
    queryKey: ["case-validation", caseFile, pairId, draftVersion],
    enabled: !importError && !importing && !editing,
    queryFn: ({ signal }) =>
      request<{ title: string; query: string }>("/api/cases/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ caseFile, pairId }),
        signal,
      }),
    retry: false,
  });
  useEffect(() => {
    if (focusErrors && (validation.error || importError))
      errorSummary.current?.focus();
  }, [focusErrors, validation.error, importError]);
  useEffect(
    () => () => {
      importGeneration.current++;
    },
    [],
  );
  function changePair(value: string) {
    setDraftVersion(++importGeneration.current);
    setImporting(false);
    setPairId(value);
  }
  function changeDraft(value: string) {
    setFocusErrors(false);
    setDraftVersion(++importGeneration.current);
    setImporting(false);
    setCaseFile(value);
    setImportError("");
  }
  async function importFile(file?: File) {
    if (!file) return;
    setFocusErrors(true);
    const version = ++importGeneration.current;
    setDraftVersion(version);
    setImporting(true);
    setImportError("");
    try {
      if (file.size > 262144)
        throw new Error("Choose a case file smaller than 256 KiB.");
      const content = new TextDecoder("utf-8", { fatal: true }).decode(
        await file.arrayBuffer(),
      );
      if (version === importGeneration.current) setCaseFile(content);
    } catch (error) {
      if (version !== importGeneration.current) return;
      setImportError(
        error instanceof TypeError
          ? "Choose a valid UTF-8 case file."
          : (error as Error).message,
      );
    } finally {
      if (version === importGeneration.current) setImporting(false);
    }
  }
  const pair = matrix.data?.pairs.find((value) => value.id === pairId);
  const ready =
    !health.isError &&
    !matrix.isError &&
    health.data?.workerReady &&
    health.data.contextReady &&
    health.data.executionReady;
  const currentValid =
    validation.isSuccess &&
    !validation.isFetching &&
    !editing &&
    !importError &&
    !importing;
  return {
    pairId,
    caseFile,
    importError,
    importing,
    editing,
    errorSummary,
    matrix,
    health,
    validation,
    changePair,
    changeDraft,
    importFile,
    pair,
    ready,
    currentValid,
  };
}
