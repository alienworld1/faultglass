import type { AgentRun, AgentInterpretation } from "../contracts/evidence";

export default function AgentEvidence({
  agent,
  interpretation,
  finished,
}: {
  agent: AgentRun | null;
  interpretation: AgentInterpretation | null;
  finished: boolean;
}) {
  if (!agent) return null;
  return (
    <div className="border-t border-line py-6 text-interpretation">
      <h3 className="font-semibold">AI investigation</h3>
      <p className="mt-3 text-sm text-muted">
        {agent.mode === "deterministic_diagnostic"
          ? "AI investigation is disabled for this diagnostic session."
          : agent.status === "data_excluded"
            ? "This case or its connected history is excluded from AI sharing. Verified evidence is preserved."
            : agent.status === "degraded"
              ? "Interpretation is unavailable. Verified evidence is preserved."
              : agent.status === "completed"
                ? "The Explorer inspected connected evidence and requested the recorded experiments."
                : finished
                  ? "Interpretation is unavailable. Verified evidence is preserved."
                  : "Inspecting connected investigation evidence…"}
      </p>
      <p className="mt-2 break-words font-mono text-xs">
        Saved agent: {agent.model || "No model recorded"} · {agent.status}
        {agent.reasonCode ? ` · ${agent.reasonCode}` : ""}
      </p>
      {interpretation ? (
        <dl className="mt-4 space-y-4 border-l-2 border-interpretation pl-4">
          {(["observed", "interpretation", "unknown"] as const).map((key) => (
            <div key={key}>
              <dt className="text-xs font-semibold uppercase tracking-wider">
                {key}
              </dt>
              <dd className="mt-2 text-sm leading-relaxed">
                {interpretation.narrative[key].text}
              </dd>
              <dd className="mt-1 break-all font-mono text-xs text-muted">
                Evidence references:{" "}
                {interpretation.narrative[key].evidenceIds.join(" · ")}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
      <details className="mt-4">
        <summary className="min-h-11 cursor-pointer py-3 text-sm">
          Inspect AI action receipts
        </summary>
        <pre
          tabIndex={0}
          className="max-h-80 overflow-auto bg-surface p-3 font-mono text-xs"
        >
          {JSON.stringify(agent, null, 2)}
        </pre>
      </details>
    </div>
  );
}
