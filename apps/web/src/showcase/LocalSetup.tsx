import { Link } from "react-router-dom";

const clone =
  "git clone https://github.com/alienworld1/faultglass.git\ncd faultglass";
const start = "./deploy/local setup\n./deploy/local start";

export default function LocalSetup() {
  return (
    <section className="max-w-4xl py-10 sm:py-16">
      <p className="text-xs uppercase tracking-wider text-accent">
        Your own investigation workspace
      </p>
      <h1 className="mt-4 text-3xl font-semibold">Run FaultGlass locally</h1>
      <p className="mt-5 text-lg leading-relaxed text-muted">
        Run real engine comparisons, follow live progress, and keep the evidence
        on your machine. The quickest start needs no model API key.
      </p>
      <section
        className="mt-8 border-y border-line py-6"
        aria-labelledby="requirements-heading"
      >
        <h2 id="requirements-heading" className="text-xl font-semibold">
          Before you start
        </h2>
        <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-relaxed">
          <li>
            Linux on an Intel or AMD x86-64 machine. On Windows, use an x86-64
            WSL2 Linux environment with Docker integration. ARM and Apple
            Silicon are not supported by the approved engine pair.
          </li>
          <li>
            Python 3.12 or newer, Git, and pnpm 11.25.0. The project prepares
            its pinned Node runtime during installation.
          </li>
          <li>
            Docker Engine with Docker Compose v2, running and accessible to your
            user without sudo.
          </li>
          <li>
            Allow at least 4 GB of RAM as a starting point, disk space for
            dependencies and engine images, and at least 2 GiB free in the
            evidence filesystem. Actual memory needs depend on the
            investigation.
          </li>
        </ul>
      </section>
      <ol className="mt-8 space-y-8">
        <li>
          <h2 className="text-xl font-semibold">1. Get the code</h2>
          <pre
            tabIndex={0}
            className="mt-4 overflow-x-auto rounded-md border border-line bg-secondary p-4 font-mono text-sm leading-relaxed"
          >
            {clone}
          </pre>
        </li>
        <li>
          <h2 className="text-xl font-semibold">2. Set up and start</h2>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            Setup installs the project dependencies and downloads the two exact
            engine images. Start brings up investigation memory, the API, the
            investigator, and the browser app together. Keep this terminal open.
          </p>
          <pre
            tabIndex={0}
            className="mt-4 overflow-x-auto rounded-md border border-line bg-secondary p-4 font-mono text-sm leading-relaxed"
          >
            {start}
          </pre>
        </li>
        <li>
          <h2 className="text-xl font-semibold">3. Open your workspace</h2>
          <p className="mt-3 text-sm leading-relaxed">
            Open{" "}
            <a href="http://127.0.0.1:5173" className="underline">
              http://127.0.0.1:5173
            </a>{" "}
            and choose <strong>Trailing MATCH after a procedure call</strong>.
            Start an investigation to compare the engines and inspect the
            evidence.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            The default session runs deterministic diagnostics. Gemini
            interpretation is disabled, and saved outcomes say so. Press Ctrl+C
            to stop the app; investigation memory and evidence are preserved.
          </p>
        </li>
      </ol>
      <details className="mt-10 border-y border-line py-3">
        <summary className="min-h-11 cursor-pointer py-3 font-semibold">
          Enable Gemini-guided investigations
        </summary>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          Stop the running app, then use the command below. You’ll be prompted
          privately for your Gemini API key if it is not already configured.
          Only the investigator receives it. Free API access depends on your
          account, model availability, and remaining quota.
        </p>
        <pre
          tabIndex={0}
          className="my-4 overflow-x-auto rounded-md border border-line bg-secondary p-4 font-mono text-sm"
        >
          ./deploy/local start --agent
        </pre>
        <p className="pb-4 text-sm leading-relaxed text-muted">
          The default model is gemini-2.5-flash-lite. Set
          FAULTGLASS_GEMINI_MODEL in your terminal to choose another model
          available to your key. Use public or synthetic cases; model processing
          is restricted to the approved built-in cases and their approved
          connected history.
        </p>
      </details>
      <p className="mt-8 text-sm leading-relaxed text-muted">
        If startup stops, follow its prerequisite message. Don’t start a second
        worker while another session is running. For manual setup, recovery, and
        evidence verification, see the{" "}
        <a
          href="https://github.com/alienworld1/faultglass#run-locally"
          className="underline"
        >
          repository guide
        </a>
        .
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex min-h-11 items-center text-sm underline"
      >
        Back to FaultGlass
      </Link>
    </section>
  );
}
