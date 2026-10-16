# Saved investigations

A persistent Python worker owns investigations independently of the browser and API. Use the same Linux account, absolute private evidence directory, context configuration, and approved engine images for the API and worker. Complete the [execution setup](README.md) and [context setup](CONTEXT.md) first. The Explorer uses a worker-only Gemini key and explicitly configured model. No wallet or end-user account is required. Direct comparisons and an explicit diagnostic mode can run without a model key.

From the repository root, keep the persistent context volume:

```sh
docker compose up -d --wait context
```

In each backend terminal, from `apps/investigator`:

```sh
. .venv/bin/activate
export FAULTGLASS_ARTIFACT_ROOT="$PWD/evidence"
python -m faultglass.context bootstrap
```

Run these in separate terminals with that environment:

```sh
uvicorn faultglass.api:app --host 127.0.0.1 --port 8000
```

In the worker terminal only, load your trusted root environment file without displaying its contents:

```sh
set -a
. ../../.env
set +a
export FAULTGLASS_GEMINI_MODEL=gemini-2.5-flash-lite
export FAULTGLASS_INVESTIGATION_MODE=agent
python -m faultglass.worker
```

The configured model must be available to your key. The [official model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite) documents structured output support and restricted access for new callers. The model name is always recorded; there is no silent substitution. Normal mode defaults to `agent`. For local deterministic checks, explicitly set `FAULTGLASS_INVESTIGATION_MODE=deterministic_diagnostic`; this is visible in saved outcomes and does not prove a working Explorer. Health reports the worker's safe agent configuration independently of engine/context readiness. Keep the key out of the API and browser environments.

From the repository root, start the browser app:

```sh
pnpm --dir apps/web dev
```

Open the printed local URL. Vite proxies `/api` to loopback port 8000. The intake checks canonical case validation and worker/context/engine readiness before enabling **Start investigation**. Choose the built-in case or import a `.faultglass.json` file. Input bytes are preserved. Investigations and evidence are shared in this workspace; use public or synthetic inputs.

## Behavior and recovery

The API saves a queued investigation and returns its URL without running engines. A UUID `Idempotency-Key` identifies one start action; repeating the exact case bytes and pair returns the same investigation. Different bytes or pair under that key return a conflict. `GET /api/investigations/admission/<key>` recovers a lost response. A confirmed outage returns unavailable, never a false missing investigation. The browser retains only the key, request digest, and returned ID in versioned session storage.

The worker fingerprints, reproduces, retrieves actual graph context, and executes each eligible curated experiment once against the immutable original case. It reserves attempts before execution. After at least one completed graph-selected experiment, it prefers the earliest result preserving the exact original difference as its reduction source. Otherwise, it finishes eligible experiments and falls back to the original case. The source runs again on fresh engines before reduction. A changed repeat stops reduction explicitly.

The reducer tries conservative terminal query deletions, then removes whole setup statements, revisiting query edits after accepted changes. Each retained change must be strictly smaller without growing another significant dimension, preserve every observation rule and frozen case field, and reproduce the exact reference signature on fresh baseline and target engines. Rejected changes and paired observations remain inspectable. **Current verified case** stays authoritative while a candidate is pending.

The final validated case is saved under the investigation's private `reduction/reduced.faultglass.json` evidence folder. **Accepted lineage** shows each retained transformation and verification; **Show unsuccessful attempts** reveals rejections. Limits are reported separately from supported-pass exhaustion. No result claims global minimality. Eligible stable evidence advances to behavioral classification. A provisional grouping describes observed boundaries, never a confirmed source-code cause. Near matches, competing families, and contradictions remain unresolved. A retained descendant is verified once; repeating its source does not make every descendant independently stable.

Three immutable downloads provide the retained case, a pytest regression scaffold, and an evidence report. The scaffold uses an explicit disposable repository-harness fixture; it skips until wired. Without an explicit oracle it asserts observed baseline compatibility behavior. It never treats a crash as desired behavior. Download reads verify the saved manifest and hashes without executing engines or changing memory.

Verified complete probe selections contribute version-scoped attempts. Success requires a repeated preserving source or a documented semantic distinction. Seeds, repeats, and reducer candidates do not inflate counters. Cost averages use six decimal places in milliseconds for the pinned graph client’s numeric round-trip; receipts retain the measured probe duration and precision policy. Aggregate updates and their runtime receipt publish atomically; uncertain acknowledgements reconcile without incrementing again. Ready exports survive a subsequent memory failure. A fresh related built-in case shows its actual saved ranking with and without the eligible prior evidence, including source investigations and graph paths. An unchanged order is shown honestly.

Reopen `/investigations/<id>` or refresh to read the same saved job. Closing the browser and restarting only the API do not stop work. **Retry connection** repeats reads. **New investigation** explicitly returns to intake. **Cancel investigation** saves intent; the current comparison finishes and cleans up before the investigation becomes cancelled. Evidence is preserved. Once classification/export begins, cancellation returns 409 because the investigation is finishing.

On worker restart, complete verified comparison manifests reconcile with the same reserved child ID, without starting engines again. A started comparison without complete evidence is cleaned up and fails with an explicit recovery reason. Start another investigation explicitly when ready. The worker refuses a second singleton and refuses execution when unknown owned containers remain. If startup reports cleanup trouble, inspect owned resources and use the existing targeted command only for the reported comparison identity:

```sh
docker ps -a --filter label=faultglass.run
python -m faultglass.recover --run-id <comparison-id>
```

Do not delete context volumes, edit receipts, or regenerate missing evidence. Missing or altered committed artifacts are integrity failures. Preserve the investigation for inspection. Context outages pause new work at durable boundaries; restoration reconciles complete evidence before continuing. Waiting and downtime count against the fixed admission deadline.

## API and limits

- `POST /api/cases/validate`: canonical validation only, body `{caseFile,pairId}`.
- `POST /api/investigations`: the same body and UUID `Idempotency-Key`; returns 202 plus `Location`.
- `GET /api/investigations/admission/<key>`: read-only admission recovery.
- `GET /api/investigations/<id>`: coherent saved snapshot and event watermark.
- `POST /api/investigations/<id>/cancel`: no options; repeated/terminal cancellation is a no-op.
- `GET /api/investigations/<id>/evidence`: verified, bounded evidence pages. Optional `sequence=0..4` and `cursor`.
- `GET /api/investigations/<id>/reduction?cursor=0`: saved reduction summary, paired verification, and at most ten attempts within 240 KiB. `caseId` selects only a referenced case; `setupCursor` pages complete setup statements, at most eight per page. Follow `nextCursor` and `nextSetupCursor`; a partial setup view is explicitly counted. Reads never execute work.
- `GET /api/investigations/<id>/conclusion?cursor=0`: conclusion, agent receipts, immutable export manifest, memory delta, historical influence, and ten family candidates per page.
- `GET /api/investigations/<id>/export/<artifact>`: exact keys `case`, `regression-test`, `report`; bounded verified attachment bytes with private/no-store caching. Unpublished downloads return 404, invalid keys 422, and failed integrity 409.
- `GET /api/investigations/<id>/events?after=0`: bounded chronological SSE replay, then live updates. `Last-Event-ID: <id>:<sequence>` takes precedence over `after`. Ahead cursors return 409; malformed or foreign cursors return 422. Terminal replay ends. IDs and timestamps never change on replay.

One active investigation, eight queued, four reserved probes, one source repeat, four reserved reduction comparisons, 32 considered reduction proposals, 900 seconds from admission, 64 MiB owned artifacts, and 512 events with 4 KiB frames are enforced server policies. Actual owned storage is counted with reserved capacity checked before execution; interruption does not refund execution reservations. The worker protects time and storage for a source repeat plus a candidate before further probing, and keeps finalization headroom. Comparisons retain the existing 60-second pair, cleanup allowances, 8 MiB evidence cap, and isolation profile. The API allows one new start per client address per ten seconds and sixteen concurrent streams. These transient counters reset on API restart; durable queue and work limits do not.

Commands reject extra fields and use bounded safe error envelopes. The command envelope is limited to 320 KiB and decoded case bytes to 256 KiB. A graph outage is 503, invalid input 422, oversized input 413, conflicts 409, and queue/rate pressure 429 with `Retry-After`. No endpoint accepts host paths or arbitrary engines.

FalkorDB `Investigation` nodes contain typed runtime versions, revisions, admission identities, and verified receipt heads. Linked immutable filesystem receipts contain full snapshots, bounded events, reservations, and output references. A single parameterized graph mutation publishes domain nodes/edges and the corresponding revision/receipt/event head together. Readers never scan staging files to discover work. Existing comparison-only episodes and CLI receipts remain unchanged; runtime endpoints return an unsupported-record conflict for legacy-only IDs.

## Same-origin hosting

Serve the built Vite app and API under one trusted origin. Deep links must fall back to `index.html`; `/api` must route to the persistent API without SPA fallback. Disable proxy buffering for SSE. For example, inside an existing trusted Nginx server configuration:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 60s;
}
location / {
    try_files $uri $uri/ /index.html;
}
```

Set `FAULTGLASS_ALLOWED_ORIGINS` to the explicit comma-separated trusted browser origins on hosted installations. Local defaults allow localhost and 127.0.0.1 on ports 5173 and 8000. There is no wildcard CORS or forwarded-header trust. Keep backend ports private. This shared workspace has no authentication or private-data boundary.

## Verification

Use the built-in case to observe real seed, experiment, and reduction evidence. Expand each verified change and inspect its parent, candidate, sizes, and paired observations; the reference signature must remain fixed. Confirm the saved final case preserves that signature through the execution CLI. Then expand **Evidence** and **Why this experiment?**, refresh its URL, then reopen it after an API restart. The matching fixture must stop with two saved observations and no experiment. Cancel queued and active cases; inspect that no owned engines remain. Check 375px, 1024px, and 1440px, keyboard controls, visible focus, and last-confirmed evidence during disconnect.

From `apps/investigator`, with context and approved Docker images available:

```sh
python -m pytest tests/unit
python -m pytest tests/context -m context
python -m pytest tests/integration
ruff check .
ruff format --check .
```

The Explorer transmits only exact approved built-in cases and approved connected history. Imported cases or private connected history produce a visible data-excluded result. The model requests allowlisted reads/ranking/execution; deterministic planning, isolated engines, classification, exports and memory remain trusted operations. Every call is reserved durably before inference, validated before dispatch, capped at five seconds and bounded payloads, with twelve calls and sixty provider seconds per investigation. An uncertain call degrades; it is never repeated invisibly.

Default test discovery covers deterministic unit/context/integration checks. With the same worker-only key/model configured, explicitly run the separate live acceptance check:

```sh
python -m pytest tests/live/test_explorer_memory.py -s
```

This requires an actual complete Explorer tool loop and a changed fresh related-case ranking attributable to the earlier contribution. Missing credentials, provider degradation, or an unchanged order fails explicitly. It preserves its isolated proof graph and prints only public case/provenance identities. Runtime cost affects the existing planner, so an increased score without an order change is not proof of improved action.

The live check spaces provider calls by twenty seconds. Both investigations use `FAULTGLASS_GEMINI_MODEL` by default. To spread free-tier usage across two available models, explicitly set `FAULTGLASS_LIVE_RELATED_MODEL` for the second admission. Each investigation still requires its own complete live tool loop, records its configured model, and uses the same deterministic planner and evidence checks. This option applies only to the live check; the worker never silently changes models.

Recovery tests inject barriers only in test subprocesses. They cover complete-child reconciliation without execution, incomplete work failure, real graph rollback and lost acknowledgment, admission/cancel races, replay cursors, queue/deadline controls, and existing CLI compatibility. The worker has no production crash switches.
