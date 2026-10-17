import { afterEach, expect, it, vi } from "vitest";
import { request, RequestError } from "./api";

afterEach(() => vi.unstubAllGlobals());

it.each([
  [429, "The workspace is busy. Try again shortly."],
  [413, "Choose a case file smaller than 256 KiB."],
  [403, "This page cannot start or change investigations."],
  [408, "The request took too long. Try again shortly."],
])("explains non-JSON ingress failure %s", async (status, message) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("<html>upstream</html>", { status })),
  );
  await expect(request("/api/investigations")).rejects.toMatchObject({
    status,
    message,
  });
});

it("retains Retry-After without automatically repeating a command", async () => {
  const fetch = vi.fn(
    async () =>
      new Response("busy", { status: 429, headers: { "Retry-After": "20" } }),
  );
  vi.stubGlobal("fetch", fetch);
  try {
    await request("/api/investigations", { method: "POST" });
    expect.unreachable();
  } catch (error) {
    expect(error).toBeInstanceOf(RequestError);
    expect(error).toMatchObject({ retryAfterMs: 20000 });
  }
  expect(fetch).toHaveBeenCalledTimes(1);
});
