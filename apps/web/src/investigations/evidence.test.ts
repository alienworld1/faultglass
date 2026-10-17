import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import type {
  Decision,
  DownloadReference,
  EvidencePage,
  Snapshot,
} from "../contracts/evidence";
import { request, RequestError, parseEvent } from "./api";
import { parseDecision, selectedCandidate } from "./decision";
import { readWorkspace, workspaceOptions, retryRead } from "./queries";
import { verifiedExport } from "./verifiedExport";
import { evidenceSubjects } from "./evidenceSubjects";
import { requestDigest, saveStart, savedStart } from "./admission";
import { webcrypto } from "node:crypto";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});
const id = "11111111-1111-4111-8111-111111111111";
const signal = () => new AbortController().signal;
const response = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const emptyConclusion = (revision: number) => ({
  revision,
  candidates: [],
  nextCursor: null,
  conclusion: null,
  classification: null,
  exports: null,
  memory: null,
  influence: null,
  agent: null,
  interpretation: null,
});

describe("saved evidence boundaries", () => {
  it("preserves field-path feedback and permanent read errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          {
            error: {
              code: "invalid_case",
              message: "Choose a valid case file.",
              fields: [{ path: "query", message: "Add a query." }],
            },
          },
          422,
        ),
      ),
    );
    await expect(request("/api/cases/validate")).rejects.toMatchObject({
      status: 422,
      code: "invalid_case",
      fields: [{ path: "query", message: "Add a query." }],
    });
    expect(retryRead(0, new RequestError("Missing", 404))).toBe(false);
    expect(retryRead(0, new RequestError("Integrity", 409))).toBe(false);
    expect(retryRead(2, new Error())).toBe(false);
  });
  it("rejects malformed or foreign event envelopes", () => {
    const event = {
      id: `${id}:1`,
      investigationId: id,
      sequence: 1,
      type: "phase.started",
      summary: "Comparing",
      data: { revision: 1 },
    };
    expect(parseEvent(JSON.stringify(event), id).sequence).toBe(1);
    expect(() =>
      parseEvent(JSON.stringify({ ...event, sequence: 513 }), id),
    ).toThrow();
    expect(() => parseEvent(JSON.stringify(event), "foreign")).toThrow();
    expect(() => parseEvent("{", id)).toThrow();
  });
  it("resolves the selected ID instead of assuming the first ranked candidate", () => {
    const plan = {
      selected_probe_id: "chosen",
      candidates: [{ probe_id: "first" }, { probe_id: "chosen" }],
    } as Decision;
    expect(selectedCandidate(plan)?.probe_id).toBe("chosen");
    expect(
      selectedCandidate({ ...plan, selected_probe_id: "missing" }),
    ).toBeNull();
    expect(parseDecision("not json")).toBeNull();
    expect(
      parseDecision(
        '{"candidates":[{}],"selection_id":"id","selected_probe_id":"chosen"}',
      ),
    ).toBeNull();
  });
  it("keeps selection and observations attached to their stable input sequence", () => {
    const page = {
      revision: 1,
      nextCursor: null,
      items: [
        { sequence: 1, kind: "selection", decision: "saved", references: [] },
        { sequence: 0, kind: "seed", query: "RETURN 1", references: [] },
        { sequence: 1, kind: "observation", query: "RETURN 2", references: [] },
      ],
    } as unknown as EvidencePage;
    const subjects = evidenceSubjects(page);
    expect(subjects.map((item) => item.sequence)).toEqual([0, 1]);
    expect(subjects[1]).toMatchObject({ decision: "saved", query: "RETURN 2" });
  });
  it("reconciles mixed revisions before publishing a workspace", async () => {
    let revision = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith(id))
          return response({
            id,
            revision: ++revision,
            lastEventSequence: 0,
            reduction: null,
          });
        if (url.endsWith("evidence"))
          return response({ revision, items: [], nextCursor: null });
        return response(emptyConclusion(2));
      }),
    );
    const saved = await readWorkspace(id, signal());
    expect(saved.snapshot.revision).toBe(2);
    expect(saved.evidence.revision).toBe(2);
    expect(saved.conclusion.revision).toBe(2);
  });
  it("retains all evidence and family pages within one revision", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith(id))
          return response({
            id,
            revision: 3,
            lastEventSequence: 0,
            reduction: null,
          });
        if (url.includes("evidence"))
          return response({
            revision: 3,
            items: [{ sequence: url.includes("cursor") ? 1 : 0 }],
            nextCursor: url.includes("cursor") ? null : 1,
          });
        return response({
          ...emptyConclusion(3),
          candidates: [
            { familyId: url.includes("cursor") ? "second" : "first" },
          ],
          nextCursor: url.includes("cursor") ? null : 1,
        });
      }),
    );
    const saved = await readWorkspace(id, signal());
    expect(saved.evidence.items.map((item) => item.sequence)).toEqual([0, 1]);
    expect(saved.conclusion.candidates.map((item) => item.familyId)).toEqual([
      "first",
      "second",
    ]);
  });
  it("never overwrites a newer coherent revision or discards it on integrity failure", async () => {
    const client = new QueryClient();
    const options = workspaceOptions(id);
    const newer = {
      snapshot: { id, revision: 9 } as Snapshot,
      evidence: { revision: 9, items: [], nextCursor: null },
      reduction: null,
      conclusion: emptyConclusion(9),
    } as unknown as Awaited<ReturnType<typeof readWorkspace>>;
    client.setQueryData(options.queryKey, newer);
    await client.fetchQuery({
      ...options,
      queryFn: async () => ({
        ...newer,
        snapshot: { ...newer.snapshot, revision: 8 },
      }),
    });
    expect(
      client.getQueryData<typeof newer>(options.queryKey)?.snapshot.revision,
    ).toBe(9);
    await expect(
      client.fetchQuery({
        ...options,
        queryFn: async () => {
          throw new RequestError("Saved evidence could not be verified.", 409);
        },
      }),
    ).rejects.toThrow();
    expect(
      client.getQueryData<typeof newer>(options.queryKey)?.snapshot.revision,
    ).toBe(9);
    client.clear();
  });
});

describe("admission and export integrity", () => {
  it("keeps only recovery identity and exact request digest in session storage", async () => {
    vi.stubGlobal("crypto", webcrypto);
    const digest = await requestDigest('{"caseFile":"public","pairId":"pair"}');
    expect(digest).not.toBe(
      await requestDigest('{"caseFile":"public ","pairId":"pair"}'),
    );
    saveStart({ version: 1, key: id, requestDigest: digest });
    expect(savedStart()).toEqual({
      version: 1,
      key: id,
      requestDigest: digest,
    });
    expect(sessionStorage.getItem("faultglass.admission.v1")).not.toContain(
      "caseFile",
    );
  });
  it("fails before admission when recovery storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error();
    });
    expect(() =>
      saveStart({ version: 1, key: id, requestDigest: "a".repeat(64) }),
    ).toThrow("Allow browser storage");
  });
  it("verifies export bytes and refuses JSON errors or altered downloads", async () => {
    vi.stubGlobal("crypto", webcrypto);
    const data = new TextEncoder().encode("verified case");
    const hash = Array.from(
      new Uint8Array(await webcrypto.subtle.digest("SHA-256", data)),
      (byte) => byte.toString(16).padStart(2, "0"),
    ).join("");
    const file = {
      key: "case",
      owner: `${id}/export`,
      bytes: data.length,
      sha256: hash,
      mediaType: "application/json",
    } as DownloadReference;
    const fetch = vi.fn().mockResolvedValue(new Response(data));
    vi.stubGlobal("fetch", fetch);
    expect((await verifiedExport(id, file)).size).toBe(data.length);
    fetch.mockResolvedValue(new Response("altered"));
    await expect(verifiedExport(id, file)).rejects.toThrow(
      "could not be verified",
    );
    fetch.mockResolvedValue(response({ error: "integrity" }, 409));
    await expect(verifiedExport(id, file)).rejects.toThrow(
      "could not be verified",
    );
    await expect(verifiedExport("foreign", file)).rejects.toThrow(
      "could not be verified",
    );
  });
});
