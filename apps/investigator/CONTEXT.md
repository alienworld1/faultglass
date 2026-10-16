# Investigation memory

Save verified comparisons as reusable context in a separate persistent FalkorDB graph. Recording never executes the case. A fingerprint describes structural similarity; it does not establish equivalent behavior or a shared root cause.

## Prepare the service

Complete the [execution setup](README.md), including both approved images and the Python environment. From the repository root, with Docker Compose available:

```sh
docker compose up -d --wait context
cd apps/investigator
. .venv/bin/activate
export FAULTGLASS_ARTIFACT_ROOT="$PWD/evidence"
python -m faultglass.context bootstrap
python -m faultglass.context bootstrap
```

Both bootstrap calls report readiness, 12 indexes, and 24 controlled features. Bootstrap creates only missing indexes and catalog entries; it never resets data. The service pins the independently tested C 4.22.0 image at `sha256:ffc97adebdd027ec71ddf7143f38d95c65846d6abd38404ab452873d045db37b`, separately from either disposable engine. It binds only `127.0.0.1:6380`, with data in the Compose `context-data` volume at `/data`. Redis uses AOF, `appendfsync always`, and a `60 1` snapshot policy. Preserve the volume when recreating the service.

FalkorDB is started with `TIMEOUT_MAX 10000 TIMEOUT_DEFAULT 2000`. These settings are required: the tested release otherwise applies a command timeout to reads only. Real tests verify rollback of runtime failures and timed-out writes with these settings. See the [official timeout configuration](https://docs.falkordb.com/getting-started/configuration#query-timeout).

Configuration comes only from the trusted process environment:

| Variable                      | Default                              |
| ----------------------------- | ------------------------------------ |
| `FAULTGLASS_CONTEXT_HOST`     | `127.0.0.1`                          |
| `FAULTGLASS_CONTEXT_PORT`     | `6380`                               |
| `FAULTGLASS_CONTEXT_GRAPH`    | `faultglass__falkordb_core`          |
| `FAULTGLASS_CONTEXT_USERNAME` | Unset                                |
| `FAULTGLASS_CONTEXT_PASSWORD` | Unset                                |
| `FAULTGLASS_ARTIFACT_ROOT`    | `./evidence` relative to the command |

Credentials stay in environment variables. Never put them in cases, artifacts, logs, or command examples. The supported runtime has one local writer admission path per OS account. All commands using a workspace must use the same artifact root. The engines retain disabled networking and receive neither context configuration nor context volume access. This loopback setup is for trusted local use.

## Save and inspect evidence

```sh
python -m faultglass.execution --case tests/fixtures/call-yield.faultglass.json --pair call-yield-c-rust
```

Copy the returned `runId` and use it in place of `<evidence-id>`:

```sh
python -m faultglass.verify "$FAULTGLASS_ARTIFACT_ROOT/<evidence-id>"
python -m faultglass.context record --evidence-id <evidence-id>
python -m faultglass.context inspect --evidence-id <evidence-id>
python -m faultglass.context record --evidence-id <evidence-id>
```

The first record reports `reused: false`; replay reports `reused: true` with the same identities and phase digest. Inspect returns the case, fingerprint, controlled features, baseline/target runs, exact engine identities, observed difference if present, and relative artifact references. A difference remains `stable: false`; one observation does not prove stability or correctness. Run the matching fixture to save `NOT_REPRODUCED` with two runs and no divergence.

Copy `fingerprint_id` from the saved receipt:

```sh
python -m faultglass.context history --fingerprint <fingerprint-id> --limit 25
```

A fresh workspace correctly reports “No related investigation evidence yet.” Comparison-only recording does not create families, probes, or learned statistics. Completed saved investigations create provisional or matched behavioral profiles and publish verified contribution statistics through the worker. The separate [experiment planner](PROBES.md) adds its versioned probe/feature catalog when used; it never bootstraps learned history. Unknown fingerprints fail distinctly from valid empty history. The repository accepts an optional ordered engine scope and excluded episode for later callers; it returns facts and provenance, never a probe score or selection.

Progress goes to stderr; successful commands emit one bounded JSON object on stdout. Exit codes: `0` success including empty history, `2` invalid arguments, `1` unavailable/incompatible context or invalid evidence, `130` interruption. Routine errors omit credentials, submitted queries, and tracebacks.

## Identities and evidence

The three identities have separate meanings:

- The original report's `caseContentHash` hashes the imported file bytes.
- `case-v1` hashes executable content and observation policy after expanding defaults and removing recognized statement whitespace/comments and one terminal semicolon. It preserves token boundaries, literal values, spelling, and statement order. Titles, descriptions, external IDs, and metadata do not affect this identity.
- `fingerprint-v1` hashes the bounded shape and sorted catalog features. Tested simple pattern bindings can share variable placeholders; standalone scalar return lists can share literal placeholders while preserving type, zero, and repeated-value patterns. Alias/subquery/list scopes, parameters, property-equality literals, limits, and other uncertain contexts retain exact values and conservative diagnostics. Labels, property keys, procedure names, result aliases, path bounds, and directions remain significant.

The original six-artifact manifest stays immutable. A separate `context/manifest.json` verifies `case.faultglass.json`, `identity.json`, and `fingerprint.json`. Each sidecar is limited to 1 MiB, with a 4 MiB total budget. References are owner-relative, hash/length checked, bounded to 2 KiB, and reject traversal and symbolic links. Full queries, result rows, and logs remain in files rather than graph properties.

Graph engine IDs hash repository, commit, and immutable image digest. Each paired comparison is one investigation with two deterministic role-specific run IDs. Fresh comparisons remain separate episodes even when canonical identities or divergence signatures match. Run `started_at`/`finished_at` are explicitly marked `timing_basis: paired_bounds`; observed durations are stored to six decimal places in milliseconds to round-trip through the official client, while the exact observations and their hashes remain authoritative.

## Graph model and reviewed queries

The ten allowed labels are `EngineVersion`, `Investigation`, `FaultCase`, `Fingerprint`, `Feature`, `Probe`, `Run`, `Divergence`, `FaultFamily`, and `RegressionTest`. Family, probe, and export records require actual producers; bootstrap installs no synthetic history.

The saved path is:

```text
Investigation → STARTED_FROM → FaultCase → HAS_FINGERPRINT → Fingerprint → USES_FEATURE → Feature
Investigation → EXECUTED_AS → Run → ON_VERSION → EngineVersion
Run → PRODUCED → Divergence
```

Both runs reference the same paired divergence when one exists. Additional typed links are `TARGETS_FEATURE`, `SELECTED_PROBE`, `REDUCED_TO`, `MATCHES_FAMILY`, `INVOLVES_FEATURE`, `EFFECTIVE_FOR`, and `DERIVED_TEST`. Every relationship has a stable ID and source provenance. Shared canonical properties retain their first representative title, artifact reference, and creation time.

[Checked-in Cypher](faultglass/queries/) supplies index creation/introspection, catalog merge, canonical recording, inspection, and history. The history traversal follows fingerprint/features to families and effective probes, requiring a complete classified episode in the same workspace and ordered engine scope. It deduplicates overlapping features, excludes disabled probes and superseded families, and orders by overlap, family, probe, and scope before expanding at most five supporting episodes. Limits range from 1–100, default 25. Missing or malformed supporting evidence fails integrity validation rather than becoming a candidate.

Useful read-only diagnostic queries are in `counts.cypher`, `indexes.cypher`, `lookup.cypher`, `investigation.cypher`, `history.cypher`, and `history-provenance.cypher`. Queries use official-client parameter maps; connection settings and arbitrary Cypher are not accepted through the product command. All ten labels have `.id` indexes; investigation and family status are also indexed. Bootstrap verifies operational index status and an indexed lookup plan. Indexes do not enforce uniqueness: the local writer lock serializes conflict checking and the single seed-phase mutation.

## Recovery and verification

A phase is at most 256 KiB. The mutation writes the two runs, episode links, optional divergence, and receipt atomically. Files are persisted before graph references. A connection lost after submission is an uncertain outcome: the command reconnects and checks the receipt before any replay. Retry with the same evidence ID; never rerun engines merely to recover a context write. There are no invisible transport retries.

If the service is unavailable, start it and retry. If evidence changed, restore the original files; do not edit a manifest to bless changed evidence. Conflicting immutable identities or incompatible schemas stop writes. Do not delete indexes or reset the graph to suppress a conflict. Fully written orphan sidecars after an interrupted write are safe to reuse after verification.

From the repository root, with a previously recorded ID:

```sh
docker compose stop context
# inspect/history/record must now report unavailable.
docker compose up -d --wait context
# inspect the same saved ID; record it again and expect reused: true.
docker compose up -d --wait --force-recreate context
# inspect again; the same volume retains the graph.
```

Never remove the context volume as part of normal recovery. Process restarts, shell exits, and frontend refreshes leave evidence and graph history intact.

From `apps/investigator`, run:

```sh
python -m pytest tests/unit
python -m pytest tests/context -m context
python -m pytest tests/integration
ruff check .
ruff format --check .
```

The context suite requires Docker, approved images, and the running context service. Missing prerequisites fail with setup guidance; explicitly selected integration tests do not skip. Each test creates an isolated `faultglass__test_…` graph and deletes only that graph. Synthetic family/probe history is installed explicitly by tests, tied to verified observations, and never loaded by normal startup. Tests cover query-driven traversal changes, provenance, bounds, exact/cross/reversed scopes, rollback, acknowledgment loss, concurrent CLI writers, immutable conflicts, and disposable copies of damaged evidence.
