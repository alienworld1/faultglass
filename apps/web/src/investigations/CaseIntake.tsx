import relatedCase from "../cases/related-call-yield.faultglass.json";
import builtInCase from "../cases/call-yield.faultglass.json";
import { RequestError } from "./api";
import { useAdmission } from "./useAdmission";
import { useCasePreparation } from "./useCasePreparation";
import EngineIdentity from "./EngineIdentity";
import RecentInvestigations from "./RecentInvestigations";

export default function CaseIntake() {
  const admission = useAdmission();
  const {
    pairId,
    caseFile,
    importError,
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
  } = useCasePreparation();
  const reason = admission.pending
    ? "Saving investigation…"
    : admission.uncertain
      ? "Checking your previous start. Retry connection if it remains unavailable."
      : !ready
        ? !health.data?.contextReady
          ? "Investigation memory is unavailable. Retry connection in a moment."
          : !health.data.workerReady
            ? "The investigator is offline. Start the worker, then retry connection."
            : "The comparison engines are unavailable. Retry connection in a moment."
        : !pair?.available
          ? "Choose an available engine pair."
          : !currentValid
            ? editing || validation.isFetching
              ? "Validating case…"
              : "Validate this case before starting."
            : "Ready to investigate.";
  const validationError = validation.error;
  return (
    <section className="min-w-0 py-8">
      <div className="mb-8 max-w-3xl">
        <p className="mb-3 text-xs uppercase tracking-wider text-accent">
          Case preparation
        </p>
        <h1 className="text-2xl font-semibold">
          One repro in. The whole fault family out.
        </h1>
        <p className="mt-4 text-base leading-relaxed">
          Start with a failing Cypher query. Follow graph-guided experiments,
          inspect a smaller verified reproducer, and download regression
          coverage.
        </p>
        <p className="mt-4 text-sm text-muted">
          Investigations and their evidence are visible in this workspace. Use
          public or synthetic cases.
        </p>
      </div>
      <RecentInvestigations />
      <div className="grid min-w-0 border-y border-line lg:grid-cols-[minmax(240px,1fr)_minmax(0,3fr)]">
        <aside
          className="min-w-0 border-b border-line py-6 lg:border-r lg:border-b-0 lg:pr-6"
          aria-label="Case selection"
        >
          <h2 className="font-semibold">Start from a case</h2>
          {[builtInCase, relatedCase].map((value) => (
            <button
              key={value.title}
              type="button"
              aria-pressed={caseFile === JSON.stringify(value, null, 2)}
              className="mt-3 min-h-11 w-full border-l-2 border-line px-3 py-3 text-left hover:bg-secondary aria-pressed:border-accent aria-pressed:bg-secondary aria-pressed:font-semibold"
              onClick={() => changeDraft(JSON.stringify(value, null, 2))}
            >
              {value.title}
            </button>
          ))}
          <label htmlFor="case-file" className="mt-6 block text-sm">
            Or import a .faultglass.json file
          </label>
          <input
            id="case-file"
            aria-describedby="validation-errors"
            type="file"
            accept=".json,application/json"
            className="mt-2 min-h-11 w-full min-w-0 text-sm"
            onChange={(event) => {
              void importFile(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <label htmlFor="engine-pair" className="mt-6 block font-semibold">
            Engine pair
          </label>
          <select
            id="engine-pair"
            className="mt-2 min-h-11 w-full border border-line bg-surface px-3 text-sm"
            value={pairId}
            onChange={(event) => changePair(event.target.value)}
          >
            {matrix.data?.pairs.map((value) => (
              <option
                key={value.id}
                value={value.id}
                disabled={!value.available}
              >
                {value.label}
                {value.available ? "" : " — unavailable"}
              </option>
            )) ?? <option value={pairId}>Checking available engines…</option>}
          </select>
          <p className="mt-4 text-sm text-muted">
            The same setup and query run in fresh, isolated engines within a
            15-minute investigation limit. You can close this tab and return
            using the investigation’s saved URL.
          </p>
        </aside>
        <div className="min-w-0 py-6 lg:pl-8">
          <label htmlFor="case-editor" className="font-semibold">
            Case · editable JSON
          </label>
          <p id="editor-help" className="mt-2 text-sm text-muted">
            Choose a case to get started, or edit its setup and query below.
            Changes are checked automatically after you pause typing.
          </p>
          <textarea
            id="case-editor"
            className="mt-4 min-h-96 w-full resize-y rounded-sm border border-line bg-surface p-4 font-mono text-sm leading-relaxed"
            spellCheck={false}
            value={caseFile}
            aria-describedby="editor-help validation-errors"
            aria-invalid={Boolean(validationError || importError)}
            onChange={(event) => changeDraft(event.target.value)}
          />
          <div
            ref={errorSummary}
            tabIndex={-1}
            id="validation-errors"
            className="mt-3 text-sm text-failure"
            role="status"
          >
            {importError || validationError?.message}
            {validationError instanceof RequestError ? (
              <ul>
                {validationError.fields.map((field, index) => (
                  <li key={index}>
                    <a
                      href={
                        field.path === "pairId"
                          ? "#engine-pair"
                          : "#case-editor"
                      }
                      className="inline-flex min-h-11 items-center underline"
                    >
                      {field.path || "Case"}: {field.message}
                    </a>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          {currentValid ? (
            <div className="mt-4 border-l-2 border-evidence pl-4">
              <h2 className="font-semibold">{validation.data?.title}</h2>
              <pre
                tabIndex={0}
                className="mt-3 max-w-full overflow-x-auto font-mono text-sm"
              >
                {validation.data?.query}
              </pre>
            </div>
          ) : null}
          <div className="mt-6 grid min-w-0 gap-4 sm:grid-cols-2">
            {(["baseline", "target"] as const).map((role) => (
              <EngineIdentity
                key={role}
                role={role}
                engine={matrix.data?.engines.find(
                  (value) =>
                    value.id ===
                    pair?.[role === "baseline" ? "baselineId" : "targetId"],
                )}
              />
            ))}
          </div>
        </div>
      </div>
      <div className="py-6">
        <p role="status" className="mb-3 text-sm text-muted">
          {matrix.isPending || health.isPending
            ? "Checking available engines…"
            : reason}
        </p>
        {matrix.error || health.error ? (
          <p className="mb-3 text-sm text-failure">
            We couldn’t check available engines. Retry connection.
          </p>
        ) : null}
        <p className="mb-4 text-sm text-muted">
          {!health.data?.workerReady
            ? "Investigations run independently of your browser once the investigator is online."
            : health.data?.agentMode === "deterministic_diagnostic"
              ? "Interpretation is disabled for this diagnostic session."
              : health.data && !health.data.agentReady
                ? "Interpretation is unavailable. The saved agent outcome will explain any limits."
                : "Approved public cases can use connected evidence to guide experiments."}
        </p>
        {admission.message ? (
          <p role="status" className="mb-4 text-sm">
            {admission.message}
          </p>
        ) : null}
        <button
          type="button"
          className="min-h-11 rounded-md bg-ink px-5 text-surface disabled:opacity-50"
          disabled={
            !ready ||
            !currentValid ||
            !pair?.available ||
            admission.pending ||
            admission.coolingDown ||
            admission.uncertain
          }
          onClick={() => admission.submit(caseFile, pairId)}
        >
          {" "}
          {admission.pending ? "Saving investigation…" : "Start investigation"}
        </button>
        <button
          type="button"
          className="ml-4 min-h-11 underline"
          onClick={() => {
            void matrix.refetch();
            void health.refetch();
            void validation.refetch();
            admission.retry();
          }}
        >
          Retry connection
        </button>
        {admission.hasRecovery && !admission.uncertain ? (
          <button
            className="mt-3 block min-h-11 underline"
            onClick={admission.clear}
          >
            Start a new investigation
          </button>
        ) : null}
      </div>
    </section>
  );
}
