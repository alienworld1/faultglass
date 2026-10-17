import { act, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { webcrypto } from "node:crypto";
import ReductionCase from "./ReductionCase";
import CaseIntake from "./CaseIntake";
import { useInvestigation } from "./useInvestigation";
import { saveStart } from "./admission";
import type { Snapshot, ReductionCaseView } from "../contracts/evidence";

let container: HTMLDivElement;
let root: Root;
let client: QueryClient;
const id = "11111111-1111-4111-8111-111111111111";
const respond = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status });
const conclusion = {
  revision: 1,
  candidates: [],
  nextCursor: null,
  conclusion: null,
  classification: null,
  exports: null,
  memory: null,
  influence: null,
  agent: null,
  interpretation: null,
};
const flush = async () => {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 20));
  });
};
const button = (label: string) =>
  [...container.querySelectorAll("button")].find(
    (value) => value.textContent?.trim() === label,
  )!;
function intakeFetch(url: string) {
  if (url === "/api/investigations") return respond({ items: [] });
  if (url === "/api/engine-matrix")
    return respond({
      engines: [],
      pairs: [
        { id: "call-yield-c-rust", label: "Approved pair", available: true },
      ],
    });
  if (url === "/api/health")
    return respond({
      workerReady: true,
      contextReady: true,
      executionReady: true,
      agentReady: true,
    });
  return respond({ title: "Validated case", query: "RETURN 1" });
}
async function mount(element: React.ReactNode) {
  await act(async () =>
    root.render(
      <StrictMode>
        <QueryClientProvider client={client}>
          <BrowserRouter>{element}</BrowserRouter>
        </QueryClientProvider>
      </StrictMode>,
    ),
  );
  await flush();
}
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.stubGlobal("crypto", webcrypto);
  window.history.replaceState({}, "", "/");
  sessionStorage.clear();
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
});
afterEach(async () => {
  await act(async () => root.unmount());
  client.clear();
  container.remove();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("case admission", () => {
  it("loads recent saved links on request without admitting an investigation", async () => {
    const fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/investigations" && init?.method !== "POST")
        return respond({
          items: [
            {
              id,
              title: "Saved investigation",
              status: "COMPLETE",
              baseline: "Baseline",
              target: "Target",
              plannedExperiments: 2,
              updatedAt: "2026-10-17T12:00:00+00:00",
              familyState: "provisional",
            },
          ],
        });
      return intakeFetch(url);
    });
    vi.stubGlobal("fetch", fetch);
    await mount(<CaseIntake />);
    expect(
      fetch.mock.calls.some(([url]) => url === "/api/investigations"),
    ).toBe(false);
    const details = [...container.querySelectorAll("details")].find((item) =>
      item
        .querySelector("summary")
        ?.textContent?.includes("Recent investigations"),
    )!;
    await act(async () => {
      details.open = true;
      details.dispatchEvent(new Event("toggle"));
    });
    await flush();
    expect(
      container.querySelector(`a[href="/investigations/${id}"]`)?.textContent,
    ).toBe("Saved investigation");
    expect(container.textContent).toContain("Investigation complete.");
    expect(
      fetch.mock.calls.some(
        ([url, init]) =>
          url === "/api/investigations" && init?.method === "POST",
      ),
    ).toBe(false);
  });
  it("waits after rate pressure and keeps the same start identity", async () => {
    const keys: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url === "/api/investigations") {
          keys.push(new Headers(init?.headers).get("Idempotency-Key") ?? "");
          return new Response("busy", {
            status: 429,
            headers: { "Retry-After": "1" },
          });
        }
        return intakeFetch(url);
      }),
    );
    await mount(<CaseIntake />);
    await act(async () => button("Start investigation").click());
    await flush();
    expect(button("Start investigation").disabled).toBe(true);
    expect(container.textContent).not.toContain("Saving investigation…");
    const saved = sessionStorage.getItem("faultglass.admission.v1");
    await act(async () => new Promise((resolve) => setTimeout(resolve, 1050)));
    await act(async () => button("Start investigation").click());
    await flush();
    expect(keys).toHaveLength(2);
    expect(keys[1]).toBe(keys[0]);
    expect(sessionStorage.getItem("faultglass.admission.v1")).toBe(saved);
  });
  it("cannot enable Start from an obsolete validation response", async () => {
    let resolveOld: (value: Response) => void = () => {};
    let resolveCurrent: (value: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url === "/api/cases/validate") {
          return new Promise<Response>((resolve) => {
            if (String(init?.body).includes("two node labels"))
              resolveCurrent = resolve;
            else resolveOld = resolve;
          });
        }
        return Promise.resolve(intakeFetch(url));
      }),
    );
    await mount(<CaseIntake />);
    await act(async () =>
      button("Trailing MATCH with two node labels").click(),
    );
    await act(async () =>
      resolveOld(respond({ title: "Obsolete", query: "RETURN 0" })),
    );
    await flush();
    expect(button("Start investigation").disabled).toBe(true);
    await act(async () => new Promise((resolve) => setTimeout(resolve, 375)));
    await act(async () =>
      resolveCurrent(respond({ title: "Current", query: "RETURN 1" })),
    );
    await flush();
    expect(button("Start investigation").disabled).toBe(false);
    expect(container.textContent).not.toContain("Obsolete");
  });
  it("checks only the settled draft and marks the selected built-in case", async () => {
    const fetch = vi.fn(async (url: string) => intakeFetch(url));
    vi.stubGlobal("fetch", fetch);
    await mount(<CaseIntake />);
    const first = button("Trailing MATCH after a procedure call");
    const second = button("Trailing MATCH with two node labels");
    expect(first.getAttribute("aria-pressed")).toBe("true");
    const calls = () =>
      fetch.mock.calls.filter(([url]) => url === "/api/cases/validate").length;
    const initial = calls();
    await act(async () => second.click());
    expect(second.getAttribute("aria-pressed")).toBe("true");
    expect(first.getAttribute("aria-pressed")).toBe("false");
    expect(button("Start investigation").disabled).toBe(true);
    await flush();
    expect(calls()).toBe(initial);
    await act(async () => new Promise((resolve) => setTimeout(resolve, 375)));
    await flush();
    expect(calls()).toBe(initial + 1);
    expect(button("Start investigation").disabled).toBe(false);
  });
  it("admits once on synchronous double click and recovers a lost acknowledgement", async () => {
    const fetch = vi.fn(async (url: string) => {
      if (url === "/api/investigations") throw new Error("Connection lost");
      if (url.includes("/admission/")) return respond({ id });
      return intakeFetch(url);
    });
    vi.stubGlobal("fetch", fetch);
    await mount(<CaseIntake />);
    await act(async () => {
      button("Start investigation").click();
      button("Start investigation").click();
    });
    await flush();
    await flush();
    expect(
      fetch.mock.calls.filter(([url]) => url === "/api/investigations"),
    ).toHaveLength(1);
    expect(window.location.pathname).toBe(`/investigations/${id}`);
    expect(sessionStorage.getItem("faultglass.admission.v1")).not.toContain(
      "caseFile",
    );
  });
  it("does not submit when browser recovery storage fails", async () => {
    const fetch = vi.fn(async (url: string) => intakeFetch(url));
    vi.stubGlobal("fetch", fetch);
    await mount(<CaseIntake />);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error();
    });
    await act(async () => button("Start investigation").click());
    await flush();
    expect(
      fetch.mock.calls.some(([url]) => url === "/api/investigations"),
    ).toBe(false);
    expect(container.textContent).toContain("Allow browser storage");
  });
  it("rejects oversized and invalid UTF-8 imports without submitting, preserving the draft", async () => {
    const fetch = vi.fn(async (url: string) => intakeFetch(url));
    vi.stubGlobal("fetch", fetch);
    await mount(<CaseIntake />);
    const input = container.querySelector<HTMLInputElement>("#case-file")!;
    const draft =
      container.querySelector<HTMLTextAreaElement>("#case-editor")!.value;
    Object.defineProperty(input, "files", {
      configurable: true,
      value: [{ size: 262145 }],
    });
    await act(async () =>
      input.dispatchEvent(new Event("change", { bubbles: true })),
    );
    expect(button("Start investigation").disabled).toBe(true);
    expect(container.textContent).toContain("smaller than 256 KiB");
    Object.defineProperty(input, "files", {
      configurable: true,
      value: [
        { size: 1, arrayBuffer: async () => new Uint8Array([255]).buffer },
      ],
    });
    await act(async () =>
      input.dispatchEvent(new Event("change", { bubbles: true })),
    );
    expect(button("Start investigation").disabled).toBe(true);
    expect(container.textContent).toContain("valid UTF-8");
    expect(
      container.querySelector<HTMLTextAreaElement>("#case-editor")!.value,
    ).toBe(draft);
    expect(
      fetch.mock.calls.some(([url]) => url === "/api/investigations"),
    ).toBe(false);
  });
  it("ignores an import completed after a newer case selection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => intakeFetch(url)),
    );
    await mount(<CaseIntake />);
    let finish: (value: ArrayBuffer) => void = () => {};
    const input = container.querySelector<HTMLInputElement>("#case-file")!;
    Object.defineProperty(input, "files", {
      configurable: true,
      value: [
        {
          size: 2,
          arrayBuffer: () =>
            new Promise<ArrayBuffer>((resolve) => {
              finish = resolve;
            }),
        },
      ],
    });
    await act(async () =>
      input.dispatchEvent(new Event("change", { bubbles: true })),
    );
    await act(async () =>
      button("Trailing MATCH with two node labels").click(),
    );
    await act(async () => finish(new TextEncoder().encode("{}").buffer));
    expect(
      container.querySelector<HTMLTextAreaElement>("#case-editor")!.value,
    ).toContain("two node labels");
  });
  it("does not abandon an uncertain admission during a service outage", async () => {
    saveStart({ version: 1, key: id, requestDigest: "a".repeat(64) });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("/admission/")
          ? respond(
              {
                error: {
                  message: "Investigations are temporarily unavailable.",
                },
              },
              503,
            )
          : intakeFetch(url),
      ),
    );
    await mount(<CaseIntake />);
    expect(button("Start investigation").disabled).toBe(true);
    expect(container.textContent).not.toContain("Start a new investigation");
    expect(sessionStorage.getItem("faultglass.admission.v1")).toContain(id);
  });
});

it("appends complete setup pages without mixing different initial setup windows", async () => {
  const setup = Array.from({ length: 16 }, (_, index) => `RETURN ${index}`);
  const caseView = {
    caseId: "saved-case",
    caseRef: { path: "case.json", sha256: "saved-hash" },
    query: "RETURN 1",
    setupTotal: 16,
  };
  const fetch = vi.fn(async (url: string) => {
    const cursor = Number(
      new URL(url, "http://localhost").searchParams.get("setupCursor"),
    );
    return respond({
      revision: 1,
      case: {
        ...caseView,
        setup: setup.slice(cursor, cursor + 8),
        nextSetupCursor: cursor + 8 < 16 ? cursor + 8 : null,
      },
    });
  });
  vi.stubGlobal("fetch", fetch);
  await mount(
    <div>
      <ReductionCase
        id={id}
        label="Current verified case"
        value={
          {
            ...caseView,
            setup: setup.slice(0, 8),
            nextSetupCursor: 8,
          } as unknown as ReductionCaseView
        }
      />
      <ReductionCase
        id={id}
        label="Parent case"
        value={
          {
            ...caseView,
            setup: [],
            nextSetupCursor: 0,
          } as unknown as ReductionCaseView
        }
      />
    </div>,
  );
  await act(async () => button("More setup statements").click());
  await flush();
  const current = container.querySelectorAll("section")[0];
  expect(current.querySelectorAll("ol li")).toHaveLength(16);
  await act(async () => button("Show setup statements").click());
  await flush();
  const parent = container.querySelectorAll("section")[1];
  expect(parent.querySelectorAll("ol li")).toHaveLength(8);
  expect(parent.textContent).toContain("RETURN 0");
  await act(async () => button("More setup statements").click());
  await flush();
  expect(parent.querySelectorAll("ol li")).toHaveLength(16);
  expect(current.querySelectorAll("ol li")).toHaveLength(16);
});

class SavedEvents {
  static instances: SavedEvents[] = [];
  closed = false;
  listeners = new Map<string, EventListener>();
  onerror: (() => void) | null = null;
  constructor(_url: string) {
    SavedEvents.instances.push(this);
  }
  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, listener);
  }
  close() {
    this.closed = true;
  }
  send(sequence: number) {
    this.listeners.get("phase.started")?.({
      data: JSON.stringify({
        id: `${id}:${sequence}`,
        investigationId: id,
        sequence,
        type: "phase.started",
        summary: "Running",
        data: { revision: sequence, status: "PROBING" },
      }),
    } as unknown as Event);
  }
}
function SavedState() {
  const state = useInvestigation(id, 0);
  return (
    <p>
      {state.snapshot?.title} {state.connection}
    </p>
  );
}
describe("saved investigation subscriptions", () => {
  it("cleans up StrictMode subscriptions, deduplicates replay and reconciles gaps using reads", async () => {
    SavedEvents.instances = [];
    vi.stubGlobal("EventSource", SavedEvents);
    const snapshot = {
      id,
      title: "Confirmed evidence",
      revision: 1,
      lastEventSequence: 0,
      status: "PROBING",
      reduction: null,
    } as Snapshot;
    const fetch = vi.fn(async (url: string) =>
      url.endsWith(id)
        ? respond(snapshot)
        : url.endsWith("evidence")
          ? respond({ revision: 1, items: [], nextCursor: null })
          : respond(conclusion),
    );
    vi.stubGlobal("fetch", fetch);
    await mount(<SavedState />);
    expect(SavedEvents.instances.filter((value) => !value.closed)).toHaveLength(
      1,
    );
    const stream = SavedEvents.instances.find((value) => !value.closed)!;
    await act(async () => {
      stream.send(1);
      stream.send(1);
    });
    await act(async () => new Promise((resolve) => setTimeout(resolve, 180)));
    expect(
      fetch.mock.calls.filter(([url]) => url.endsWith(id)).length,
    ).toBeLessThanOrEqual(3);
    await act(async () => stream.send(3));
    expect(stream.closed).toBe(true);
    expect(container.textContent).toContain("Confirmed evidence");
    expect(container.textContent).toContain("Reconnecting");
    expect(
      fetch.mock.calls.every(([url]) =>
        url.startsWith(`/api/investigations/${id}`),
      ),
    ).toBe(true);
    await act(async () => root.unmount());
    expect(SavedEvents.instances.every((value) => value.closed)).toBe(true);
    root = createRoot(container);
  });
});
