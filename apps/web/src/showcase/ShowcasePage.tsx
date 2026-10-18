import { Link } from "react-router-dom";
import CasePreview from "./CasePreview";

const steps = [
  [
    "01",
    "Reproduce",
    "Compare the same Cypher case on two pinned FalkorDB engines in fresh, isolated containers.",
  ],
  [
    "02",
    "Explore",
    "Use language features and verified investigation history to choose nearby query forms.",
  ],
  [
    "03",
    "Reduce",
    "Keep smaller queries and setup statements only when fresh comparisons preserve the difference.",
  ],
  [
    "04",
    "Remember",
    "Inspect the evidence, export a regression scaffold, and carry verified findings into later investigations.",
  ],
];

export default function ShowcasePage() {
  return (
    <section className="py-10 sm:py-16">
      <div className="max-w-3xl">
        <p className="text-xs uppercase tracking-wider text-accent">
          FalkorDB investigation workspace
        </p>
        <h1 className="mt-4 text-3xl font-semibold leading-tight sm:text-5xl">
          Turn a failing query into evidence you can build on.
        </h1>
        <p className="mt-6 text-lg leading-relaxed text-muted">
          FaultGlass investigates reproducible differences between FalkorDB
          engines. Follow graph-guided experiments, inspect a smaller verified
          reproducer, and export the case with a regression-test scaffold.
        </p>
        <div className="mt-7 flex flex-wrap items-center gap-5">
          <Link
            to="/run-locally"
            className="inline-flex min-h-11 items-center rounded-md bg-ink px-5 text-surface"
          >
            Run FaultGlass locally
          </Link>
          <a
            href="#included-cases"
            className="inline-flex min-h-11 items-center underline"
          >
            Explore the included cases
          </a>
        </div>
      </div>
      <aside
        className="mt-10 border-l-2 border-accent bg-secondary p-5 text-sm leading-relaxed"
        aria-label="About this preview"
      >
        <p className="font-semibold">
          Explore here. Investigate on your machine.
        </p>
        <p className="mt-2 max-w-3xl text-muted">
          This public preview runs entirely in your browser. Live
          investigations, saved evidence, and downloads of investigation results
          become available when you run the full workspace locally. No queries
          are executed on this website.
        </p>
      </aside>
      <div className="my-12 grid border-y border-line sm:grid-cols-2 lg:grid-cols-4">
        {steps.map(([number, title, description]) => (
          <article key={number} className="min-w-0 px-4 py-7">
            <p className="font-mono text-xs text-accent">{number}</p>
            <h2 className="mt-3 text-xl font-semibold">{title}</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              {description}
            </p>
          </article>
        ))}
      </div>
      <CasePreview />
      <div className="mt-10 max-w-3xl text-sm leading-relaxed text-muted">
        <p>
          The included engine pair is FalkorDB C 4.22.0 and Rust commit b033aec.
          These are historical snapshots. A difference shows disagreement; it
          does not establish which engine is correct or identify a source-code
          cause.
        </p>
      </div>
    </section>
  );
}
