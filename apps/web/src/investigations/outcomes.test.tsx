import { renderToStaticMarkup } from "react-dom/server";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import type {
  AgentRun,
  ConclusionPage,
  Snapshot,
  EvidencePage,
  RankedCandidate,
} from "../contracts/evidence";
import InvestigationConclusion from "./InvestigationConclusion";
import AgentEvidence from "./AgentEvidence";
import HistoricalInfluence from "./HistoricalInfluence";
import EvidenceDisclosure from "./EvidenceDisclosure";
import ReductionLineage from "./ReductionLineage";
import type { SavedReduction } from "./api";
import GraphSelectionPath from "./GraphSelectionPath";

const ref = {
  id: "case-ref",
  owner: "saved/export",
  path: "case.json",
  sha256: "a".repeat(64),
  bytes: 10,
  kind: "case",
  mediaType: "application/json",
};
function render(element: React.ReactNode) {
  const client = new QueryClient();
  const html = renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <BrowserRouter>{element}</BrowserRouter>
    </QueryClientProvider>,
  );
  client.clear();
  return html;
}
describe("evidence outcome presentation", () => {
  it("shows the saved graph path without inventing historical evidence on a cold start", () => {
    const candidate = {
      source: "structural",
      chosen_history_key: null,
      matched_feature_ids: ["CALL", "MATCH"],
      probe_id: "INSERT_WITH_BEFORE_TERMINAL_MATCH:v1",
      successes: 0,
      attempts: 0,
    } as RankedCandidate;
    const cold = render(<GraphSelectionPath candidate={candidate} />);
    expect(cold).toContain("USES_FEATURE");
    expect(cold).toContain("TARGETS_FEATURE");
    expect(cold).not.toContain("EFFECTIVE_FOR");
    const learned = render(
      <GraphSelectionPath
        candidate={{
          ...candidate,
          source: "history",
          chosen_history_key: 'family-id:{"baseline":"saved"}',
          successes: 2,
          attempts: 3,
        }}
      />,
    );
    expect(learned).toContain("INVOLVES_FEATURE");
    expect(learned).toContain("EFFECTIVE_FOR");
    expect(learned).toContain("family-id");
    expect(learned).toContain("2 useful outcomes across 3 prior attempts");
    expect(learned).not.toContain("TARGETS_FEATURE");
  });
  it("preserves recorded input and paired evidence while a newly selected experiment is pending", () => {
    const observed = {
      engineVersionId: "saved-engine",
      status: "error",
      columns: [],
      rowCount: null,
      detail: null,
      errorCategory: "SEMANTIC",
    };
    const html = render(
      <EvidenceDisclosure
        snapshot={{ reduction: null } as Snapshot}
        page={
          {
            revision: 2,
            nextCursor: null,
            items: [
              {
                sequence: 0,
                kind: "seed",
                query: "RETURN original",
                references: [],
                observations: {
                  baseline: observed,
                  target: { ...observed, status: "crash" },
                },
              },
              { sequence: 1, kind: "selection", references: [] },
            ],
          } as unknown as EvidencePage
        }
      />,
    );
    expect(html).toContain("Last recorded case");
    expect(html).toContain("RETURN original");
    expect(html).toContain("same case / sequence");
    expect(html).toContain("awaiting paired evidence");
    expect(html).not.toContain("No comparison evidence has been recorded yet.");
  });
  it("keeps a verified case authoritative while a different candidate is pending", () => {
    const size = {
      queryTokens: 4,
      setupStatements: 0,
      setupTokens: 0,
      executableBytes: 10,
    };
    const page = {
      case: {
        caseId: "verified",
        caseRef: ref,
        query: "RETURN verified",
        setup: [],
        setupTotal: 0,
        nextSetupCursor: null,
      },
      sourceCase: null,
      sourceObservations: null,
      stabilityObservations: null,
      summary: {
        state: "reducing",
        currentCaseId: "verified",
        acceptedCount: 0,
        rejectedCount: 0,
        verificationFailures: 0,
        originalSize: size,
        sourceSize: size,
        currentSize: size,
        stopReason: null,
        source: {
          sourceKind: "seed",
          stable: true,
          sourceCaseId: "source",
          referenceDivergence: {
            kind: "status",
            changedDimensions: ["status"],
            signature: "saved-signature",
            comparisonVersion: "saved-comparator",
          },
        },
      },
      attempts: [
        {
          attempt: {
            id: "pending",
            state: "verifying",
            ordinal: 1,
            change: { description: "Remove setup" },
            beforeSize: size,
            afterSize: null,
            artifactRefs: [],
            parentCaseId: "verified",
            candidateCaseId: "candidate",
          },
          parent: null,
          candidate: null,
          observations: null,
        },
      ],
    } as unknown as SavedReduction;
    const html = render(<ReductionLineage id="saved" page={page} />);
    expect(html).toContain("Current verified case");
    expect(html).toContain("RETURN verified");
    expect(html).toContain("Candidate");
    expect(html).toContain(
      "Verification is pending. The current verified case is preserved.",
    );
    expect(html).not.toContain("Verified change");
  });
  it("keeps manifest downloads available after memory failure and displays verification limits", () => {
    const page = {
      conclusion: {
        state: "unresolved",
        familyName: null,
        observed: ["The difference was verified."],
        unknowns: ["Family remains unresolved."],
        evidenceRef: ref,
      },
      candidates: [],
      classification: { retainedIsRepeatedSource: false },
      exports: {
        expectationBasis: "baseline_observation",
        files: [
          { ...ref, key: "case" },
          { ...ref, key: "regression-test" },
          { ...ref, key: "report" },
        ],
      },
      memory: null,
      influence: null,
      agent: null,
      interpretation: null,
    } as unknown as ConclusionPage;
    const html = render(
      <InvestigationConclusion
        id="saved"
        page={page}
        snapshot={
          {
            status: "FAILED",
            terminalReason: { code: "memory_failure" },
          } as Snapshot
        }
      />,
    );
    expect(html).toContain(
      "Downloads are ready, but investigation memory was not saved.",
    );
    expect(html).toContain("Download case");
    expect(html).toContain("Download regression test");
    expect(html).toContain("Download evidence report");
    expect(html).toContain("retained descendant was verified once");
    expect(html).toContain("Family remains unresolved.");
  });
  it("does not promise interpretation work after a terminal investigation", () => {
    const html = render(
      <AgentEvidence
        agent={
          { status: "running", mode: "agent", model: "saved-model" } as AgentRun
        }
        interpretation={null}
        finished
      />,
    );
    expect(html).toContain(
      "Interpretation is unavailable. Verified evidence is preserved.",
    );
    expect(html).not.toContain("Inspecting connected investigation evidence");
    expect(html).toContain("running");
  });
  it("does not claim a selected rank change when other experiments changed order", () => {
    const html = render(
      <HistoricalInfluence
        influence={{
          selectedProbeId: "selected",
          changed: true,
          priorInvestigationIds: ["prior"],
          pathRefs: ["opaque-reference"],
          decisionRef: ref,
          withoutHistory: [{ probeId: "selected", rank: 1, score: 0.5 }],
          withHistory: [{ probeId: "selected", rank: 1, score: 0.7 }],
        }}
      />,
    );
    expect(html).toContain("selected experiment’s rank is unchanged");
    expect(html).toContain("opaque-reference");
    expect(html).toContain("/investigations/prior");
    expect(html).not.toContain("from rank 1 to 1");
  });
});
