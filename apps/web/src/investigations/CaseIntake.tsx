import { useEffect, useState } from "react";
import type { EnginePair, EngineSpec, Snapshot } from "../contracts/evidence";
import builtInCase from "../cases/call-yield.faultglass.json";
import { request, RequestError } from "./api";

type Matrix = {
  engines: EngineSpec[];
  pairs: (EnginePair & { available: boolean })[];
};
type Pending = { version: 1; key: string; requestDigest: string; id?: string };
const storageKey = "faultglass.admission.v1";
const builtIn = JSON.stringify(builtInCase, null, 2);
function savedStart(): Pending | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(storageKey) ?? "null");
    return value?.version === 1 &&
      typeof value.key === "string" &&
      typeof value.requestDigest === "string"
      ? value
      : null;
  } catch {
    return null;
  }
}

export default function CaseIntake({
  navigate,
}: {
  navigate: (path: string) => void;
}) {
  const [matrix, setMatrix] = useState<Matrix | null>(null);
  const [ready, setReady] = useState(false);
  const [pairId, setPairId] = useState("call-yield-c-rust");
  const [caseFile, setCaseFile] = useState(builtIn);
  const [validation, setPreview] = useState<{
    title: string;
    query: string;
    input: string;
    pairId: string;
  } | null>(null);
  const [message, setMessage] = useState("Checking available engines…");
  const [pending, setPending] = useState(false);
  const [uncertain, setUncertain] = useState(() => savedStart() !== null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      request<Matrix>("/api/engine-matrix", { signal: controller.signal }),
      request<{
        workerReady: boolean;
        contextReady: boolean;
        executionReady: boolean;
      }>("/api/health", { signal: controller.signal }),
    ])
      .then(([catalog, health]) => {
        setMatrix(catalog);
        setReady(
          health.workerReady && health.contextReady && health.executionReady,
        );
        setMessage(
          health.workerReady && health.contextReady && health.executionReady
            ? ""
            : "Investigations are temporarily unavailable. Check the worker and available engines.",
        );
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setMessage("We couldn’t check available engines. Retry connection.");
      });
    return () => controller.abort();
  }, [retry]);
  useEffect(() => {
    const controller = new AbortController();
    request<{ title: string; query: string }>("/api/cases/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ caseFile, pairId }),
      signal: controller.signal,
    })
      .then((value) => setPreview({ ...value, input: caseFile, pairId }))
      .catch((error) => {
        if (!controller.signal.aborted) setMessage(error.message);
      });
    return () => controller.abort();
  }, [caseFile, pairId, retry]);
  useEffect(() => {
    const saved = savedStart();
    if (!saved) return;
    let disposed = false;
    request<{ id: string }>(`/api/investigations/admission/${saved.key}`)
      .then((value) => {
        if (!disposed) {
          sessionStorage.setItem(
            storageKey,
            JSON.stringify({ ...saved, id: value.id }),
          );
          navigate(`/investigations/${value.id}`);
        }
      })
      .catch((error) => {
        if (disposed) return;
        if (error instanceof RequestError && error.status === 404) {
          setUncertain(false);
          setMessage(
            "Your previous start was not found. You can retry with the same case.",
          );
        } else
          setMessage(
            "We couldn’t confirm your previous start. Retry connection before starting again.",
          );
      });
    return () => {
      disposed = true;
    };
  }, [navigate, retry]);
  const preview =
    validation?.input === caseFile && validation.pairId === pairId
      ? validation
      : null;
  async function submit() {
    if (pending || uncertain || !preview) return;
    setPending(true);
    try {
      const body = JSON.stringify({ caseFile, pairId });
      const hash = await crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(body),
      );
      const requestDigest = Array.from(new Uint8Array(hash), (byte) =>
        byte.toString(16).padStart(2, "0"),
      ).join("");
      const saved = savedStart();
      if (saved && saved.requestDigest !== requestDigest) {
        setMessage(
          "Choose the same case to recover your start, or explicitly start a new investigation.",
        );
        return;
      }
      const admission: Pending = saved ?? {
        version: 1,
        key: crypto.randomUUID(),
        requestDigest,
      };
      sessionStorage.setItem(storageKey, JSON.stringify(admission));
      setUncertain(true);
      const value = await request<{ investigation: Snapshot }>(
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
      sessionStorage.setItem(
        storageKey,
        JSON.stringify({ ...admission, id: value.investigation.id }),
      );
      navigate(`/investigations/${value.investigation.id}`);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "We couldn’t confirm your start. Retry connection.",
      );
      if (
        error instanceof RequestError &&
        [413, 422, 429, 503].includes(error.status)
      )
        setUncertain(false);
    } finally {
      setPending(false);
    }
  }
  async function importFile(file?: File) {
    if (!file) return;
    if (file.size > 262144) {
      setPreview(null);
      setMessage("Choose a case file smaller than 256 KiB.");
      return;
    }
    try {
      setCaseFile(
        new TextDecoder("utf-8", { fatal: true }).decode(
          await file.arrayBuffer(),
        ),
      );
    } catch {
      setPreview(null);
      setMessage("Choose a valid UTF-8 case file.");
    }
  }
  return (
    <section className="divide-y divide-line border-b border-line">
      <div className="py-8">
        <h2 className="text-2xl font-semibold">
          Choose a case and compare two FalkorDB engines.
        </h2>
        <p className="mt-4 text-sm text-muted">
          Investigations and their evidence are visible in this workspace. Use
          public or synthetic cases.
        </p>
      </div>
      <div className="grid gap-6 py-8 sm:grid-cols-2">
        <div>
          <button
            type="button"
            className="min-h-11 border border-line px-4"
            onClick={() => {
              setCaseFile(builtIn);
              setRetry((value) => value + 1);
            }}
          >
            Use built-in case
          </button>
          <label htmlFor="case-file" className="mt-5 block text-sm">
            Or import a .faultglass.json file
          </label>
          <input
            id="case-file"
            type="file"
            accept=".json,application/json"
            className="mt-2 block w-full text-sm"
            aria-describedby="intake-message"
            onChange={(event) => void importFile(event.target.files?.[0])}
          />
        </div>
        <div>
          <label htmlFor="engine-pair" className="block text-sm">
            Engine pair
          </label>
          <select
            id="engine-pair"
            className="mt-2 min-h-11 w-full border border-line bg-surface px-3"
            value={pairId}
            onChange={(event) => setPairId(event.target.value)}
          >
            {matrix?.pairs.map((pair) => (
              <option key={pair.id} value={pair.id} disabled={!pair.available}>
                {pair.label}
                {pair.available ? "" : " — unavailable"}
              </option>
            )) ?? (
              <option value="call-yield-c-rust">
                Checking available engines…
              </option>
            )}
          </select>
        </div>
      </div>
      {preview ? (
        <div className="py-6">
          <h3 className="font-semibold">{preview.title}</h3>
          <pre className="mt-4 overflow-x-auto font-mono text-sm">
            {preview.query}
          </pre>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {["baseline", "target"].map((role) => {
              const pair = matrix?.pairs.find((item) => item.id === pairId);
              const engine = matrix?.engines.find(
                (item) =>
                  item.id ===
                  pair?.[role === "baseline" ? "baselineId" : "targetId"],
              );
              return (
                <p key={role} className="min-w-0 text-sm">
                  <span className="block font-semibold capitalize">{role}</span>
                  <span className="font-mono break-all">
                    {engine?.label ?? "Checking engine identity…"}
                  </span>
                </p>
              );
            })}
          </div>
        </div>
      ) : null}
      <div className="py-6">
        <p
          id="intake-message"
          role="status"
          className="mb-4 text-sm text-muted"
        >
          {message}
        </p>
        <button
          type="button"
          className="min-h-11 bg-ink px-5 text-surface disabled:opacity-50"
          disabled={
            !ready ||
            !preview ||
            pending ||
            uncertain ||
            !matrix?.pairs.find((pair) => pair.id === pairId)?.available
          }
          onClick={() => void submit()}
        >
          {pending ? "Saving investigation…" : "Start investigation"}
        </button>
        <button
          type="button"
          className="ml-4 min-h-11 underline"
          onClick={() => setRetry((value) => value + 1)}
        >
          Retry connection
        </button>
        {savedStart() && !uncertain ? (
          <button
            type="button"
            className="mt-4 block min-h-11 underline"
            onClick={() => {
              sessionStorage.removeItem(storageKey);
              setMessage("Ready for a new investigation.");
              setRetry((value) => value + 1);
            }}
          >
            Start a new investigation
          </button>
        ) : null}
      </div>
    </section>
  );
}
