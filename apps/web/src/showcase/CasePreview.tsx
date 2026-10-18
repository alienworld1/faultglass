import { useState } from "react";
import builtInCase from "../cases/call-yield.faultglass.json";
import relatedCase from "../cases/related-call-yield.faultglass.json";

const cases = [builtInCase, relatedCase];

export default function CasePreview() {
  const [selected, setSelected] = useState(0);
  const current = cases[selected];
  const caseFile = JSON.stringify(current, null, 2);
  return (
    <section
      id="included-cases"
      className="scroll-mt-6"
      aria-labelledby="cases-heading"
    >
      <h2 id="cases-heading" className="text-2xl font-semibold">
        Start with a reproducible case
      </h2>
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
        Inspect either included case, then open it in your local workspace to
        run the comparison. These are input cases, not saved investigation
        results.
      </p>
      <div className="mt-6 grid min-w-0 border-y border-line lg:grid-cols-[minmax(240px,1fr)_minmax(0,3fr)]">
        <div className="border-b border-line py-5 lg:border-r lg:border-b-0 lg:pr-6">
          {cases.map((value, index) => (
            <button
              key={value.title}
              type="button"
              aria-pressed={index === selected}
              onClick={() => setSelected(index)}
              className="mb-2 min-h-11 w-full border-l-2 border-line px-3 py-3 text-left hover:bg-secondary aria-pressed:border-accent aria-pressed:bg-secondary aria-pressed:font-semibold"
            >
              {value.title}
            </button>
          ))}
        </div>
        <div className="min-w-0 py-6 lg:pl-8">
          <p className="text-xs uppercase tracking-wider text-muted">
            Cypher query
          </p>
          <pre
            tabIndex={0}
            className="mt-3 overflow-x-auto whitespace-pre-wrap break-words font-mono text-sm leading-relaxed"
          >
            {current.query}
          </pre>
          <details className="mt-5 border-t border-line">
            <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">
              Inspect the complete case
            </summary>
            <pre
              tabIndex={0}
              className="max-h-96 overflow-auto pb-4 font-mono text-sm leading-relaxed"
            >
              {caseFile}
            </pre>
          </details>
          <a
            className="mt-4 inline-flex min-h-11 items-center text-sm underline"
            href={`data:application/json;charset=utf-8,${encodeURIComponent(caseFile)}`}
            download={
              selected === 0
                ? "call-yield.faultglass.json"
                : "related-call-yield.faultglass.json"
            }
          >
            Download this case
          </a>
        </div>
      </div>
    </section>
  );
}
