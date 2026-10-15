# FaultGlass execution

Compare the same reproducible Cypher case across two isolated FalkorDB engines. An observed difference is evidence of disagreement; it does not establish which engine is correct.

## Local setup

Verified on Linux/amd64 with Python 3.12.3, Node 24.19.0, pnpm 11.25.0, and Docker Engine 29.9.0. `pnpm install` prepares the pinned Node runtime for frontend commands. The trusted investigator needs local Docker API access. Tested engines have no network, published ports, host mounts, socket, or inherited application credentials. An LLM key is not required. Execution can run independently of investigation memory. See [persistent investigation memory](CONTEXT.md) for the separate context service, commands, graph model, and recovery.

From the repository root:

```sh
pnpm --dir apps/web install --frozen-lockfile
python3 -m venv apps/investigator/.venv
cd apps/investigator
. .venv/bin/activate
python -m pip install -r requirements.lock
export FAULTGLASS_ARTIFACT_ROOT="$PWD/evidence"
docker pull --platform linux/amd64 falkordb/falkordb@sha256:ffc97adebdd027ec71ddf7143f38d95c65846d6abd38404ab452873d045db37b
docker pull --platform linux/amd64 ghcr.io/falkordb/falkordb-server@sha256:9367c99cdc338d752d6976653c5e68d227b5b6b03ab4938d6eaeb3c4e1607e24
```

Only the approved `call-yield-c-rust` pair is supported. `faultglass/engine-verification.json` records the verified source/platform identities, official release binary hash, and three local evidence receipt hashes. Raw execution evidence remains local and is never used as a runtime substitute. Pulling images is an explicit setup step; execution never pulls, retries a query, or switches an engine. `DOCKER_HOST` may configure the trusted Docker SDK connection; it is never passed to the engines.

Run the API in one terminal:

```sh
uvicorn faultglass.api:app --host 127.0.0.1 --port 8000
```

In another terminal with the environment activated:

```sh
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/engine-matrix
python -m faultglass.execution --case tests/fixtures/call-yield.faultglass.json --pair call-yield-c-rust
```

The command prints a JSON report to stdout and a paired receipt to stderr. Expect baseline `error`, target `crash`, and “Difference observed.” Repeat twice more: each run must save a new directory and have the same material signature. This is a verified historical version-scoped difference, based on [FalkorDB issue #3279](https://github.com/FalkorDB/FalkorDB/issues/3279).

```sh
python -m faultglass.execution --case tests/fixtures/matching.faultglass.json --pair call-yield-c-rust
python -m faultglass.verify evidence/<reported-run-id>
docker ps -a --filter label=faultglass.run
```

The matching case should report `not_reproduced`, with no divergence. Verification checks the final manifest, all required artifact hashes, and byte lengths. A run folder without `manifest.json` is incomplete. Evidence persists across frontend reload and API restart; interrupted runs are not resumed.

Exit codes are `0` for either completed outcome, `2` for invalid input, `1` for execution/storage failure, and `130` for interruption. Inspect `outcome` to distinguish equality from a difference. Invalid cases and unknown pairs fail before connecting to Docker.

## Case support and limits

Python models are authoritative. Extra contract fields, duplicate JSON keys, non-finite numbers, multiple statements, unsupported versions, and inconsistent expectations are rejected. Focal parse/semantic errors remain observable evidence. Cypher bytes are preserved; the official client serializes parameters separately in its supported parameter header.

Use explicit `ordered` or `unordered` comparison. Automatic ordering is rejected until a compatible final-result analyzer is proven. State checks accept a conservative lexical subset beginning with `MATCH`, `OPTIONAL`, `RETURN`, `WITH`, or `UNWIND`, with no writes or procedure calls. They also execute using the verified engine `GRAPH.RO_QUERY` command. Ambiguous forms fail closed before provisioning.

Typed normalization supports null, boolean, integer, float, string, list, map, node, relationship, and unambiguous directed paths. It excludes engine-local IDs. Unsupported temporal/vector/spatial values, non-finite responses, ambiguous paths, or incomplete output fail comparison. Unfamiliar error wording stays `UNKNOWN`; only the version-tested trailing-MATCH error maps to `SEMANTIC`. Raw errors and logs remain inspectable independently of equality.

Defaults: 256 KiB case, 32 setup statements, 16 KiB per statement, 8 state checks, 20-second startup, 5-second query, 60-second paired execution, and up to 10 seconds of cleanup per engine. Each engine has 1 CPU, 512 MiB memory without swap, 128 PIDs, and one private 128 MiB tmpfs. Root is read-only, privileges are dropped, and networking is disabled. The Linux local command owns cleanup on its main thread and uses a hard alarm deadline per engine. Engines run sequentially within one paired run. Capture is bounded while reading; each observation permits 1,000 rows and 1 MiB, logs permit 256 KiB, and complete artifacts permit 8 MiB. Output is never truncated and called equal. The local log driver also caps retention, so historical log lines may be unavailable; captured truncation is explicitly marked.

One paired run is admitted per local account, across evidence roots. If interrupted cleanup leaves owned engines, inspect the reported run ID and remove only that run:

```sh
python -m faultglass.recover --run-id <reported-run-id>
```

A new comparison refuses to start while an earlier run still owns engines. The recovery command never sweeps unrelated containers. SIGINT/SIGTERM are handled with bounded cleanup; SIGKILL or a host failure may require this explicit recovery.

## Evidence-backed experiments

After recording a reproduced comparison in investigation memory, use `python -m faultglass.probe plan --evidence-id <seed-id>` and `python -m faultglass.probe execute --evidence-id <seed-id>` to choose and run one supported experiment. See [experiments and recovery](PROBES.md) for inspection, scoring, provenance, limits, and safe reconciliation.

## Checks

From this directory, with Docker and both approved images ready:

```sh
python -m pytest tests/unit
python -m pytest tests/integration
python -m pytest
ruff check .
ruff format --check .
```

Real Docker tests are required and fail on missing prerequisites rather than quietly skipping. They cover three fresh seed runs, matching observations, graph values/parameters/state checks, fixture reset, forbidden connectivity, caps, setup/output/storage failures, injected query deadlines, cleanup failure/recovery, and interruption of an actual command. Unit tests cover schema consistency, lexical boundaries, type preservation, duplicate rows, postcondition divergence, oracle separation, and artifact integrity.

From the repository root:

```sh
pnpm --dir apps/web lint
pnpm --dir apps/web build
pnpm --dir apps/web format:check
pnpm --dir apps/web dev
```

Open the frontend at the printed address and check 375px, 1024px, and 1440px. The static shell has no execution control; refreshing starts no run. To regenerate the shared contracts after changing Python models:

```sh
cd apps/investigator
. .venv/bin/activate
python -m faultglass.schema --output ../web/src/contracts/evidence.schema.json
pnpm --dir ../web contracts
pnpm --dir ../web format
```

The frontend JSON Schema and TypeScript are generated from the Python contracts. CLI execution remains local; the API exposes only health and curated matrix reads. Browser execution, planning, reduction, and durable jobs are intentionally absent. Context storage is available separately through `python -m faultglass.context`; it does not change execution or the read-only API.
