import type { Snapshot, EvidencePage } from "../contracts/evidence";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";

it("keeps evidence, selection and keyboard focus usable with reduced motion", async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: () => false,
    })),
  );
  const { default: EvidenceDisclosure } = await import("./EvidenceDisclosure");
  const div = document.createElement("div");
  document.body.append(div);
  const root = createRoot(div);
  const snapshot = {
    reduction: null,
    fingerprintId: "saved-fingerprint",
  } as Snapshot;
  const page = {
    revision: 1,
    nextCursor: null,
    items: [{ sequence: 0, kind: "seed", query: "RETURN 1", references: [] }],
  } as unknown as EvidencePage;
  await act(async () =>
    root.render(<EvidenceDisclosure snapshot={snapshot} page={page} />),
  );
  const inspect = [...div.querySelectorAll("button")].find(
    (button) => button.textContent === "Inspect fingerprint",
  )!;
  await act(async () => inspect.click());
  expect(div.textContent).toContain("saved-fingerprint");
  expect(document.activeElement?.textContent).toBe("Fingerprint evidence");
  expect(
    [...div.querySelectorAll<HTMLElement>("[style]")].every(
      (element) => !element.style.transform,
    ),
  ).toBe(true);
  await act(async () =>
    div
      .querySelector("aside")!
      .dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      ),
  );
  expect(document.activeElement).toBe(inspect);
  expect(div.textContent).toContain("RETURN 1");
  await act(async () => root.unmount());
  div.remove();
  vi.unstubAllGlobals();
});
