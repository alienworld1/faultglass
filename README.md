# FaultGlass

FaultGlass investigates reproducible Cypher differences between two FalkorDB engines. It runs the same case in isolated containers, tests nearby query forms, reduces cases that preserve the difference, and exports the evidence with a regression-test scaffold.

The investigation history is a FalkorDB graph connecting language features, experiments, engine versions, and observed behavior. Later investigations use verified history to rank experiments, with the supporting graph paths available for inspection. Gemini requests bounded investigation tools and provides cited interpretations; deterministic code controls execution, comparison, and publication.

The current engine pair is FalkorDB C 4.22.0 and Rust commit `b033aec`, pinned by image digest. The built-in case, `CALL db.labels() YIELD label MATCH (n)`, produces a semantic error on the baseline and a crash on the target. These are historical engine snapshots. Disagreement does not establish which engine is correct, and a behavioral grouping does not establish a source-code cause.

## Graph Hacks submission

FaultGlass targets **Agents That Act on Connected Data** and **Agent Memory and Coordination**. The first track is supported by evidence-driven experiment selection and execution; the second by persistent, version-scoped investigation memory reused across sessions. This is a single investigator with durable state, not a multi-agent coordination system.

FalkorDB is the primary and only graph database. Removing the context service prevents browser investigations from being admitted, resumed, or planned. The standalone comparison CLI below is an execution diagnostic; it does not provide the product's investigation workflow or reusable memory. Files hold immutable evidence, while FalkorDB owns the relationships and receipts needed to verify and reuse it.

### Graph model and dependent queries

The [graph model](apps/investigator/CONTEXT.md#graph-model-and-reviewed-queries) defines the node labels, relationships, identities, and provenance. The workflow depends on these checked-in queries:

| Query                                                                                                                                                            | Role in the product                                                                                           |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| [runtime-create](apps/investigator/faultglass/queries/runtime-create.cypher), [runtime-commit](apps/investigator/faultglass/queries/runtime-commit.cypher)       | Persist admissions and investigation progress.                                                                |
| [record-seed](apps/investigator/faultglass/queries/record-seed.cypher)                                                                                           | Connect a case and its fingerprint to observed runs, engines, and differences.                                |
| [history](apps/investigator/faultglass/queries/history.cypher)                                                                                                   | Traverse shared features, behavioral families, and effective experiments to retrieve relevant prior evidence. |
| [history-provenance](apps/investigator/faultglass/queries/history-provenance.cypher), [history-paths](apps/investigator/faultglass/queries/history-paths.cypher) | Recover supporting episodes and relationship paths for inspection and verification.                           |
| [memory-provenance](apps/investigator/faultglass/queries/memory-provenance.cypher) and the [memory writer](apps/investigator/faultglass/memory_writer.py)        | Verify prior contributions and prepare learned evidence for later investigations.                             |

The [planner](apps/investigator/faultglass/planner.py) ranks the retrieved candidates; Gemini can request bounded tools and explain the evidence. Query traversal, execution authority, and evidence verification remain deterministic. The [graph action tests](apps/investigator/tests/context/test_probe_action.py) demonstrate that relevant history changes the executed experiment, removing the connecting relationships removes that influence, and unavailable memory prevents planning and execution.

### Data sources and AI assistance

The built-in reproducer credits [FalkorDB issue #3279](https://github.com/FalkorDB/FalkorDB/issues/3279). Its setup creates synthetic nodes; the related two-label case is a synthetic variation. Other bundled fixtures use small synthetic graphs. Observations and investigation memory are produced by local executions. Startup installs feature and experiment catalogs, not fabricated learned outcomes; synthetic history used by tests is confined to isolated test graphs.

Use only public or synthetic cases you have permission to use. Never import personal, private, login-protected, paywalled, or otherwise restricted information, including in titles, parameters, or metadata. Import validation checks structure, not ownership or permission. The model-sharing allowlist is a separate safeguard: only exact approved built-in cases and approved connected history may be sent to Gemini. Exclusion from Gemini does not prevent local persistence, so it does not make restricted input suitable for this workspace.

**AI assistance:** I used OpenAI Codex to help write code, review changes, improve the documentation, and run tests. Gemini is part of FaultGlass itself: it requests investigation tools and interprets the evidence with citations. I’m responsible for the code I submit and for understanding and explaining how it works.

### Complete the submission

The [event rules](https://www.wemakedevs.org/hackathons/falkordb/rules) and [Code of Conduct](https://www.wemakedevs.org/coc) govern participation. Before submitting:

- Make the [source repository](https://github.com/alienworld1/faultglass) public and confirm it opens while signed out.
- Upload a working demo video and include its accessible URL in the submission. The [demo walkthrough](demo/script.md) accompanies the local workflow; a script alone is not a video submission.
- Name both tracks above in the submission and include this README's complete local setup if a live deployment is unavailable.
- Confirm team registration, at most four members, and one team per participant; disclose any additional AI tools used.
- Confirm that main coding and design began after October 15, 2026, 12:01 AM IST, and submit before October 18, 2026, 11:59 PM IST. The earliest recorded repository commit is October 15 at 12:25 AM IST; commit timestamps alone cannot establish when work actually began.
- Review the code and rehearse explaining a retrieved graph path, its effect on an experiment, and the resulting verified evidence.

## Run locally

For a free public website, deploy the [browser preview to Vercel](deploy/VERCEL.md).
Visitors can inspect the included cases and use the site's **Run locally** guide;
the preview does not require a hosted backend or a model API key.

### Quick start

On Linux/amd64 (or an x86-64 WSL2 environment with Docker integration), install
Python 3.12+, Git, pnpm 11.25.0, Docker Engine, and Docker Compose v2. Docker must
be available to your user without sudo. Then, from the repository root:

```sh
./deploy/local setup
./deploy/local start
```

Setup installs dependencies and pulls the exact approved engine images. Start
runs the API, worker, and browser app together using persistent investigation
memory. Open [http://127.0.0.1:5173](http://127.0.0.1:5173). The default mode is
deterministic diagnostics without Gemini interpretation or an API key. Keep the
terminal open; Ctrl+C stops the app and preserves evidence. The context container
stays running; `docker compose stop context` stops it without deleting history.

For Gemini-guided investigations, stop the app and run
`./deploy/local start --agent`. The launcher prompts privately for your key unless
`GEMINI_API_KEY` is already exported, and passes it only to the worker. It does not
read or write `.env`. Set `FAULTGLASS_GEMINI_MODEL` to override the default
`gemini-2.5-flash-lite`; access and free quota depend on your provider account.

The launcher uses `monitored_local` storage and loopback networking for personal
use. It does not enable public backend execution. Saved data defaults to
`apps/investigator/evidence` and the existing Compose `context-data` volume.
For an existing installation, preserve its graph/evidence pairing and export its
`FAULTGLASS_ARTIFACT_ROOT` and `FAULTGLASS_CONTEXT_DATA` before launching. Do not
switch to a different root or context volume while recovering existing work.

The manual commands below remain available for running services separately.

Requirements: Python 3.12+, Docker Engine, and Docker Compose v2. The browser app uses pnpm 11.25.0; its package configuration prepares Node 24.19.0. Your account must have Docker access. Keep at least 2 GiB free for evidence in addition to dependencies and images.

### Install the investigator and engines

From the repository root:

```sh
python3 -m venv apps/investigator/.venv
cd apps/investigator
. .venv/bin/activate
python -m pip install -r requirements.lock
export FAULTGLASS_ARTIFACT_ROOT="$PWD/evidence"

docker pull --platform linux/amd64 falkordb/falkordb@sha256:ffc97adebdd027ec71ddf7143f38d95c65846d6abd38404ab452873d045db37b
docker pull --platform linux/amd64 ghcr.io/falkordb/falkordb-server@sha256:9367c99cdc338d752d6976653c5e68d227b5b6b03ab4938d6eaeb3c4e1607e24
```

Images must already be present: execution never pulls an image or substitutes another engine. The approved identities are in [engine-matrix.json](apps/investigator/faultglass/engine-matrix.json).

### Compare a case without a model key

In the same terminal:

```sh
python -m faultglass.execution \
  --case tests/fixtures/call-yield.faultglass.json \
  --pair call-yield-c-rust
```

This runs a fresh baseline and target, prints a JSON report to stdout, and saves evidence under the configured root. Expect `baseline: error`, `target: crash`, and `outcome: reproduced`. A completed comparison exits with `0` whether or not a difference was found; inspect `outcome` to distinguish the results.

For a matching case and an integrity check:

```sh
python -m faultglass.execution \
  --case tests/fixtures/matching.faultglass.json \
  --pair call-yield-c-rust
python -m faultglass.verify "$FAULTGLASS_ARTIFACT_ROOT/<reported-run-id>"
```

Standalone comparisons require neither the persistent context service nor Gemini. See [execution documentation](apps/investigator/README.md) for the case contract, output limits, and recovery commands.

### Start the browser workspace

From the repository root:

```sh
pnpm --dir apps/web install --frozen-lockfile
docker compose up -d --wait context
```

Create a private, git-ignored `.env` at the repository root with:

```dotenv
GEMINI_API_KEY=your-private-key
```

Run the following in three separate terminals, each starting at the repository root. API and worker must run under the same Linux account and use the same absolute evidence directory.

API:

```sh
cd apps/investigator
. .venv/bin/activate
export FAULTGLASS_ARTIFACT_ROOT="$PWD/evidence"
export FAULTGLASS_STORAGE_MODE=monitored_local
export FAULTGLASS_ALLOWED_ORIGINS=http://127.0.0.1:5173
python -m faultglass.context bootstrap
uvicorn faultglass.api:app --host 127.0.0.1 --port 8000
```

Worker:

```sh
cd apps/investigator
. .venv/bin/activate
export FAULTGLASS_ARTIFACT_ROOT="$PWD/evidence"
export FAULTGLASS_STORAGE_MODE=monitored_local
set -a
. ../../.env
set +a
export FAULTGLASS_GEMINI_MODEL=gemini-2.5-flash-lite
export FAULTGLASS_INVESTIGATION_MODE=agent
python -m faultglass.worker
```

Browser app:

```sh
pnpm --dir apps/web dev --host 127.0.0.1
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies `/api` to port 8000. Choose **Trailing MATCH after a procedure call** to start an investigation. Its saved URL survives browser reloads and API restarts; closing the browser does not stop the worker.

The configured model must be available to your API key. Keep the key in the worker environment only. For a credential-free browser session, replace the worker's environment-file loading and model settings with `export FAULTGLASS_INVESTIGATION_MODE=deterministic_diagnostic`. Saved outcomes explicitly identify this mode as diagnostic.

If startup is unavailable, inspect [the health endpoint](http://127.0.0.1:8000/api/health): `contextReady`, `workerReady`, `executionReady`, and `agentReady` report separate prerequisites. `status: ok` alone does not mean investigations are ready.

## What an investigation records

A case contains setup statements, a focal Cypher query, parameters, and an observation policy. The [built-in case](apps/web/src/cases/call-yield.faultglass.json) is a small example. Cases explicitly choose ordered or unordered result comparison and may include read-only state checks and an expected result or error.

The worker first reproduces the case, extracts supported language features, and retrieves compatible history. It then ranks supported experiments using feature overlap, historical outcomes, version compatibility, novelty, cost, and verified semantic contrasts. The current catalog has two transformations for a conservative `CALL … YIELD … MATCH` query shape: replacing the terminal match with `OPTIONAL MATCH`, or inserting a binding-preserving `WITH` before it. Unsupported shapes remain unresolved.

For a reproduced difference, the worker repeats its selected reduction source on fresh engines before trying query cuts and whole setup-statement deletions. Each retained change must be smaller and preserve the exact divergence signature and observation policy. The workspace keeps accepted and rejected attempts inspectable. Bounded reduction finds a smaller verified case when possible; it does not claim a global minimum or independent repeatability of every reduced descendant.

Eligible stable investigations produce a behavioral family assessment and three downloads: the retained `.faultglass.json` case, a pytest scaffold, and an evidence report. The scaffold requires a `faultglass_repository_harness` fixture in the destination test suite and skips until that adapter is provided. Without an explicit expectation, it records baseline compatibility behavior. A crash is never an expected passing result.

Completed, eligible experiments contribute version-scoped history. A later run of **Trailing MATCH with two node labels** can show how that history affected its actual ranking, including a comparison with the ranking without the prior evidence. History may change a score without changing experiment order.

## Execution and persistence

The React workspace reads snapshots and server-sent events from FastAPI. The API saves admissions in FalkorDB; a separate singleton Python worker runs the investigations. Only the worker executes engines, although the API also needs Docker access to verify image readiness.

FalkorDB stores investigation revisions and relationships between cases, features, experiments, runs, divergences, behavioral families, and exported tests. Immutable filesystem artifacts hold input bytes, observations, logs, and receipts. Readers verify those artifacts against the graph's saved references. Preserve the graph and evidence directory together when backing up or restoring an installation.

The main implementation entry points are:

- [History retrieval](apps/investigator/faultglass/queries/history.cypher) connects case features to classified investigations and effective experiments; supporting evidence and version scope constrain what can be reused.
- [Experiment ranking](apps/investigator/faultglass/planner.py) selects applicable transformations deterministically and rejects duplicate outputs.
- [Comparison](apps/investigator/faultglass/comparison.py) uses typed normalized values, preserves duplicate unordered rows, and excludes engine-local identifiers. Explicit expectations are assessed separately from disagreement.
- [Memory publication](apps/investigator/faultglass/memory_writer.py) records eligible contributions idempotently so recovery cannot count an experiment twice.

The [context reference](apps/investigator/CONTEXT.md) documents graph identities and relationships. The [investigation reference](apps/investigator/INVESTIGATIONS.md) covers API endpoints, event replay, cancellation, and recovery.

## Scope and operating limits

This is a shared workspace without authentication or private-case isolation. Use public or synthetic cases and keep the local services on loopback. Model processing is restricted to exact approved built-in cases and approved connected history; importing a public case does not grant permission to transmit it to Gemini. Excluded inputs and provider failures are recorded explicitly, preserving verified execution evidence.

Each disposable engine runs with networking disabled, no host mounts or published ports, a read-only root, dropped privileges, one CPU, and 512 MiB of memory. Queries, output capture, cleanup, and storage are bounded. Unsupported values or incomplete results fail comparison rather than being treated as equal.

Investigations allow at most four experiments, one source repeat, four reduction comparisons, 64 MiB of artifacts, and 15 minutes from admission, including downtime. Gemini is limited to twelve calls, fifteen seconds per call, and sixty total provider seconds. An uncertain provider call is not retried automatically.

For persistent hosting, [deployment setup](deploy/SETUP.md) provides systemd services, same-origin Nginx configuration, bounded storage, and coordinated backup instructions. The supplied ingress listens on loopback; a fresh-host service installation still requires verification before use.

## Development checks

From `apps/investigator`, with the virtual environment activated:

```sh
python -m pytest tests/unit
ruff check .
ruff format --check .
```

With Docker, both approved images, and the context service available:

```sh
python -m pytest tests/context -m context
python -m pytest tests/integration
```

Run backend suites serially with the ordinary worker stopped: some tests acquire its singleton lock. Integration tests use real engines; provider responses are controlled in the deterministic suites. The separate live test requires a configured Gemini key and model:

```sh
python -m pytest tests/live/test_explorer_memory.py -s
```

From the repository root:

```sh
pnpm --dir apps/web test
pnpm --dir apps/web lint
pnpm --dir apps/web build
pnpm --dir apps/web format:check
```

The ingress suite, `python -m pytest tests/deployment` from `apps/investigator`, additionally requires Nginx and a built frontend. See [frontend development](apps/web/README.md) for contract generation and tooling details.
