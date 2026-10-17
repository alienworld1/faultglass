# Evidence-backed experiments

Choose one supported experiment for a saved, reproduced comparison, then execute it on fresh baseline and target engines. The selection uses verified graph relationships and deterministic utility, without a model or generated queries.

## Run an experiment

Complete the [execution setup](README.md) and [investigation memory setup](CONTEXT.md). Start the persistent context service, activate `.venv`, and use the same `FAULTGLASS_ARTIFACT_ROOT` for every command. Run and record an original comparison:

```sh
python -m faultglass.context bootstrap
python -m faultglass.execution --case tests/fixtures/call-yield.faultglass.json --pair call-yield-c-rust
python -m faultglass.context record --evidence-id <seed-id>
python -m faultglass.probe plan --evidence-id <seed-id>
python -m faultglass.probe inspect --evidence-id <seed-id>
python -m faultglass.probe execute --evidence-id <seed-id>
python -m faultglass.probe inspect --evidence-id <seed-id>
```

Replace `<seed-id>` with the original execution report's `runId`. Planning starts no engines. Execution runs only the committed selection, once. Inspection includes the decision, ranking, frozen source snapshot, transformed-case reference, journal, result, artifact references, and graph receipts. Progress goes to stderr; stdout contains one JSON object with copyable IDs and references. No color is required.

A fresh graph reports `novel: true` and structural ranking. An unavailable, corrupt, unknown, or overflowing history read fails; it never becomes empty history. A matching original comparison returns `not_reproduced`. Unsupported reproduced queries return `unresolved` with `no_applicable_probe`.

Only two versioned transformations are supported. Both recognize a single procedure call with scalar literal arguments or no arguments, one explicit yielded binding, and a terminal required match with a single bare node binding. One replaces the terminal match with an optional match; the other inserts `WITH` carrying the yielded binding before it. Comments, strings, and escaped identifiers are tokenized before recognizing source spans. Additional clauses, paths, predicates, properties, aliases, nested scopes, and ambiguous bindings are rejected. Every other case field is preserved. Saved edit spans and before/after text explain the exact change in private artifacts.

## Ranking and provenance

The graph supplies registered probe enablement and target features. Its history traversal follows:

```text
Fingerprint → USES_FEATURE → Feature ← INVOLVES_FEATURE ← FaultFamily ← EFFECTIVE_FOR ← Probe
Investigation → EXECUTED_AS → Run → PRODUCED → Divergence → MATCHES_FAMILY → FaultFamily
Probe → TARGETS_FEATURE → Feature
```

Historical counters must reference readable artifacts and verified classified episodes in their ordered engine scope. Current investigations, disabled probes, and superseded families cannot supply usable history. Unknown tools are recorded as exclusions and cannot install executable code. A conflicting registered definition fails integrity validation. Catalog bootstrap adds only probes and feature-target relationships, without classified history or effectiveness counters.

`planner-v2` uses the following rules. Let `F` be the original fingerprint's features, `T` the probe's targets, and `H` the shared family features. All feature weights are one:

| Factor                  | Rule                                                                                                                                                                   |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Feature fit             | With history: `0.5 × count(F ∩ T) / count(T) + 0.5 × count(F ∩ H) / count(F)`; otherwise `count(F ∩ T) / count(T)`.                                                    |
| Historical yield        | `(successes + 1) / (attempts + 2)`; absent history uses zero counters.                                                                                                 |
| Version affinity        | `1` for an exact ordered pair and comparator; `0.5` for matching ordered lineages and comparator. Reversed roles or different comparators are excluded.                |
| Novelty                 | `1 / sqrt(attempts + 1)`.                                                                                                                                              |
| Normalized cost         | Small `0.25`, medium `0.5`, large `1`. With historical attempts, average the class cost with `min(avg_cost_ms / 60000, 1)`.                                            |
| Verified boundary value | `1` only when the selected graph memory's latest verified contribution records a successful semantic contrast for this probe, family and ordered scope; otherwise `0`. |
| Utility                 | `0.35 × feature_fit + 0.30 × historical_yield + 0.20 × version_affinity + 0.10 × novelty − 0.05 × normalized_cost + 0.10 × boundary_value`.                            |

A semantic contrast changes observed behavior and helps locate the fault family's boundary. Prioritizing a verified contrast lets a later related case check that boundary first. The value comes from the graph-linked, hash-verified memory receipt and its provenance chain, never from a model claim or a probe name. Counts and execution costs remain unchanged. This avoids relying on small execution-time differences when two strategies have equal success rates. Saved `planner-v1` decisions retain their original scores and immutable bytes; their boundary value is zero.

Each family/probe/scope row is scored separately. Counters are never summed across overlapping paths. The best row represents a probe; equal rows use family ID and canonical ordered scope. Probe ties use ascending probe ID. Identical transformed cases keep the smallest probe ID. Selection uses unrounded values; graph numeric summaries use six decimal places to round-trip through the pinned server. The immutable plan retains exact inputs and scores. Scores are utility, never confidence or probability. History is bounded to 100 rows and five supporting episodes per row; a 101st row fails explicitly.

The decision and graph selection receipt exist before engines can start. An observation adds two probe runs to the original investigation, with role, child comparison ID, probe identity, version links, and an optional shared divergence. Original seed inspection and recording receipts remain unchanged. Completed experiments never update effectiveness counters, classify a family, mark evidence stable, or export a regression test.

The result reports `preserved`, `eliminated`, or `changed` from verified child signatures. “Eliminated” means no difference was observed for this experiment; it does not establish a fix or a correct engine. Original explicit expectations remain attached to the case for provenance; experiment conclusions use only the differential comparator, without treating those expectations as an established oracle for the transformed query.

## Persistence, limits, and recovery

The original six-artifact evidence and three-file context manifest remain immutable. Each original comparison gains a separate private `planning/` folder containing the plan, frozen snapshot, changed cases, manifests, receipts, execution journal, and result or failure. Documents are capped at 1 MiB and the set at 4 MiB. References are bounded to 2 KiB; graph phase payloads to 256 KiB. References reject traversal, unsafe owners, symbolic links, changed hashes, and changed lengths. The journal may advance, but it cannot replace the selection or reserved child ID.

One local writer lock serializes planning and execution, and the existing execution lease still limits engine comparisons. Each selection admits at most one child comparison within 120 seconds, reserving the 60-second pair budget and up to 10 seconds of cleanup per engine before provisioning. Startup remains capped at 20 seconds and each query at 5 seconds, with the existing CPU, memory, PID, output, isolation, and cleanup restrictions. There are no engine or query retries.

Repeated `plan`, `execute`, and `commit` reuse verified evidence and graph receipts. Historical counter changes do not rewrite an old explanation. Disabled or changed selected definitions block new execution. Acknowledgment loss checks the saved phase receipt before considering another write. Both phase writes commit their required links and receipt atomically on the pinned context server.

If complete child evidence was saved but investigation memory could not be updated, restore the context service and run:

```sh
python -m faultglass.probe commit --evidence-id <seed-id>
python -m faultglass.probe inspect --evidence-id <seed-id>
```

`commit` never starts an engine. It can also reconstruct a result from the same verified complete child manifest after an interruption during result saving. Preserve the persistent context volume and the original artifact root.

If a reserved child has incomplete evidence, execution refuses to restart it. Inspection returns its journal and saved failure when available. Use its exact `child_evidence_id` for targeted cleanup:

```sh
python -m faultglass.recover --run-id <child-id>
```

This removes only engines owned by that child. Keep the incomplete evidence. To try again after irrecoverably incomplete work, create and record a new original comparison; do not erase the journal or recycle its ID.

Exit codes: `0` for verified completed or nonselected outcomes, `1` for failure or pending graph commit, `2` for invalid arguments, and `130` for interruption. A comparable engine crash or timeout may be a completed observation. Infrastructure, cleanup, normalization, or incomplete-output failures never become a completed relationship.

## Verification

With the approved images and persistent context service ready:

```sh
python -m pytest tests/unit
python -m pytest tests/context -m context
python -m pytest tests/integration
ruff check .
ruff format --check .
```

Context tests use isolated graphs with explicit synthetic classified history backed by real saved episodes. They verify that relevant graph evidence changes the action executed by the real Docker runner, that removing the path removes its influence, and that production bootstrap installs no such history. Recovery tests cover lost acknowledgments, post-execution write outages, interrupted incomplete children, complete-manifest reconciliation, storage and normalization failures, and cleanup failures.
