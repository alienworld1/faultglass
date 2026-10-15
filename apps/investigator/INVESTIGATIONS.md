# Saved investigations

A persistent Python worker owns investigations independently of the browser and API. Use the same Linux account, absolute private evidence directory, context configuration, and approved engine images for the API and worker. Complete the [execution setup](README.md) and [context setup](CONTEXT.md) first. No model key, wallet, or account is required.

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

```sh
python -m faultglass.worker
```

From the repository root, start the browser app:

```sh
pnpm --dir apps/web dev
```

Open the printed local URL. Vite proxies `/api` to loopback port 8000. The intake checks canonical case validation and worker/context/engine readiness before enabling **Start investigation**. Choose the built-in case or import a `.faultglass.json` file. Input bytes are preserved. Investigations and evidence are shared in this workspace; use public or synthetic inputs.

## Behavior and recovery

The API saves a queued investigation and returns its URL without running engines. A UUID `Idempotency-Key` identifies one start action; repeating the exact case bytes and pair returns the same investigation. Different bytes or pair under that key return a conflict. `GET /api/investigations/admission/<key>` recovers a lost response. A confirmed outage returns unavailable, never a false missing investigation. The browser retains only the key, request digest, and returned ID in versioned session storage.

The worker fingerprints, reproduces, retrieves actual graph context, and executes each eligible curated experiment once against the immutable original case. It reserves attempts before execution. The current supported pipeline ends with **No difference observed** or **Investigation ended without a supported conclusion** when experiments are exhausted. It cannot claim a completed finding, stability, classification, or export.

Reopen `/investigations/<id>` or refresh to read the same saved job. Closing the browser and restarting only the API do not stop work. **Retry connection** repeats reads. **New investigation** explicitly returns to intake. **Cancel investigation** saves intent; the current comparison finishes and cleans up before the investigation becomes cancelled. Evidence is preserved.

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
- `GET /api/investigations/<id>/events?after=0`: bounded chronological SSE replay, then live updates. `Last-Event-ID: <id>:<sequence>` takes precedence over `after`. Ahead cursors return 409; malformed or foreign cursors return 422. Terminal replay ends. IDs and timestamps never change on replay.

One active investigation, eight queued, four reserved probes, 900 seconds from admission, 64 MiB owned artifacts, and 512 events with 4 KiB frames are enforced server policies. Actual owned storage is counted with reserved capacity checked before execution; interruption does not refund probe attempts. Comparisons retain the existing 60-second pair, cleanup allowances, 8 MiB evidence cap, and isolation profile. The API allows one new start per client address per ten seconds and sixteen concurrent streams. These transient counters reset on API restart; durable queue and work limits do not.

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

Use the built-in case to observe real seed and experiment evidence, expand **Evidence** and **Why this experiment?**, refresh its URL, then reopen it after an API restart. The matching fixture must stop with two saved observations and no experiment. Cancel queued and active cases; inspect that no owned engines remain. Check 375px, 1024px, and 1440px, keyboard controls, visible focus, and last-confirmed evidence during disconnect.

From `apps/investigator`, with context and approved Docker images available:

```sh
python -m pytest tests/unit
python -m pytest tests/context -m context
python -m pytest tests/integration
ruff check .
ruff format --check .
```

Recovery tests inject barriers only in test subprocesses. They cover complete-child reconciliation without execution, incomplete work failure, real graph rollback and lost acknowledgment, admission/cancel races, replay cursors, queue/deadline controls, and existing CLI compatibility. The worker has no production crash switches.
