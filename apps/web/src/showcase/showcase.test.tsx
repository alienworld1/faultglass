import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "../App";
import firstCase from "../cases/call-yield.faultglass.json";
import secondCase from "../cases/related-call-yield.faultglass.json";

let container: HTMLDivElement;
let root: Root;
let fetch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.stubEnv("MODE", "showcase");
  fetch = vi.fn(() => {
    throw new Error("The public preview must not contact a backend.");
  });
  vi.stubGlobal("fetch", fetch);
  vi.stubGlobal(
    "EventSource",
    vi.fn(() => {
      throw new Error("The public preview must not open a stream.");
    }),
  );
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

async function open(path: string) {
  await act(async () =>
    root.render(
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>,
    ),
  );
}

it("explores and downloads actual input cases without backend requests", async () => {
  await open("/");
  expect(container.textContent).toContain(
    "No queries are executed on this website.",
  );
  expect(container.textContent).toContain(firstCase.query);
  const select = [...container.querySelectorAll("button")].find(
    (button) => button.textContent?.trim() === secondCase.title,
  )!;
  await act(async () => select.click());
  expect(select.getAttribute("aria-pressed")).toBe("true");
  const download = container.querySelector<HTMLAnchorElement>("a[download]")!;
  const downloadedCase = JSON.parse(
    decodeURIComponent(download.href.split(",")[1]),
  );
  expect(downloadedCase).toEqual(secondCase);
  expect(fetch).not.toHaveBeenCalled();
  expect(EventSource).not.toHaveBeenCalled();
});

it.each([
  "/run-locally",
  "/investigations/11111111-1111-4111-8111-111111111111",
])("opens %s without a backend or a query provider", async (path) => {
  await open(path);
  expect(container.querySelector("h1")?.textContent).toBe(
    "Run FaultGlass locally",
  );
  expect(container.textContent).toContain("./deploy/local setup");
  expect(container.textContent).toContain("./deploy/local start --agent");
  expect(fetch).not.toHaveBeenCalled();
  expect(EventSource).not.toHaveBeenCalled();
});
