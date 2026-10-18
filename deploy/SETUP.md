# Setup and operations

For the free public preview with visitor local-run instructions, follow
[the Vercel guide](VERCEL.md). This document is for hosting the complete backend
on a persistent Linux machine.

This installation uses host systemd services and Nginx with a private pinned Docker context. It requires persistent Linux/amd64, cgroup v2, Python 3.12+, Docker Engine with Compose v2, Nginx at `/usr/sbin/nginx`, pnpm 11.25.0 and systemd journal namespaces. Use supported Ubuntu packages. Initial resource ceilings below require clean-host measurement before public capacity is chosen. See [verification](../VERIFICATION.md).

## Prerequisites

Prepare a dedicated `faultglass` account in the `docker` group. Clone the repository to `/opt/faultglass`, owned by that account. Docker access is trusted host execution authority; the private API retains it for image checks and only the worker executes experiments. Never expose Docker remotely.

As the service account, from `/opt/faultglass`:

```sh
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web build
python3 -m venv apps/investigator/.venv
apps/investigator/.venv/bin/python -m pip install -r apps/investigator/requirements.lock
docker pull --platform linux/amd64 falkordb/falkordb@sha256:ffc97adebdd027ec71ddf7143f38d95c65846d6abd38404ab452873d045db37b
docker pull --platform linux/amd64 ghcr.io/falkordb/falkordb-server@sha256:9367c99cdc338d752d6976653c5e68d227b5b6b03ab4938d6eaeb3c4e1607e24
```

Make built static files and parent directories readable/traversable by Nginx's `www-data` account. Keep evidence and secrets private. No key belongs in Vite variables, browser storage, engine environments or built assets.

Provision **separate persistent bounded filesystems**: at most 8 GiB mounted at `/var/lib/faultglass/evidence`, and at most 4 GiB at `/var/lib/faultglass/context`. Use actual block volumes, dedicated partitions or persistent size-limited filesystems with `/etc/fstab` mounts. A subdirectory on an unbounded host filesystem does not qualify. Do not format an existing data volume. Evidence must be owned by `faultglass`, mode 0700. Inspect the pinned context image's service identity and make `/data` writable by that identity; verify the actual mount, not merely the shell user's access. Preserve existing matched graph/evidence before changing mounts or ownership.

`runtime up` checks mountpoints and actual filesystem capacities. API and runner independently require at least 2 GiB available and free inodes on evidence before new work. They verify the filesystem capacity when `FAULTGLASS_STORAGE_MODE=bounded`. Races/write failure fail closed without publishing partial output; existing evidence reads do not require free-space admission. No data is auto-deleted. Development on an ordinary disk may explicitly use `monitored_local`, which retains reserve checks but needs operator storage monitoring and must never enable public execution.

Compose's development default is the persistent `context-data` volume. The orchestration script explicitly chooses the bounded host mount. Always export `FAULTGLASS_CONTEXT_DATA=/var/lib/faultglass/context` before operating production Compose directly; selecting another volume would select another context history.

## Configure and install

Create `/etc/faultglass` as an administrator, mode 0700. Copy `deploy/runtime.env.example` to `/etc/faultglass/runtime.env` and `deploy/worker.env.example` to `/etc/faultglass/worker.env`, both root-owned mode 0600. Edit privately with a trusted editor. Supply a real worker-only key and the explicit model available to that key. The example model is a choice, not an access/quota promise. Provider preflight uses the existing configuration validation; only real typed tool execution proves live access. No silent model substitution occurs.

Keep one absolute evidence root, context graph/host/port in the shared runtime file. The initial trusted origin is exactly `http://127.0.0.1:8080`. `GEMINI_API_KEY` belongs only in `worker.env`. systemd reads these files before dropping to the service account; no key is loaded into the API environment.

Install the reviewed units and bounded journals:

```sh
sudo install -m 0644 deploy/faultglass-api.service deploy/faultglass-worker.service deploy/faultglass-ingress.service /etc/systemd/system/
sudo install -m 0644 deploy/journald.conf /etc/systemd/journald@faultglass-api.conf
sudo install -m 0644 deploy/journald.conf /etc/systemd/journald@faultglass-worker.conf
sudo install -m 0644 deploy/journald.conf /etc/systemd/journald@faultglass-ingress.conf
sudo systemctl daemon-reload
sudo /opt/faultglass/deploy/runtime up
```

Startup never pulls images or resets storage. Worker preflight checks platform, Docker/images, safe writable evidence storage, provider configuration, explicit origins, graph timeouts/indexes/features and probe catalog. Bootstrap is idempotent and never seeds learning. API preflight checks the same dependencies without receiving the key. Both use the same account, `/tmp` locks and evidence path: do not add `PrivateTmp` or additional API processes. Worker presence binds the evidence root and graph and becomes ready after owned recovery. Readiness does not promise future provider quota.

```sh
curl http://127.0.0.1:8080/api/health
curl http://127.0.0.1:8080/api/engine-matrix
sudo /opt/faultglass/deploy/runtime status
sudo /opt/faultglass/deploy/runtime logs worker
sudo /opt/faultglass/deploy/runtime logs api
sudo /opt/faultglass/deploy/runtime stop
sudo /opt/faultglass/deploy/runtime up
```

Inspect context, worker, execution, agent readiness and safe issue codes separately. Preflight lists actionable failures without secrets/raw errors. To verify bootstrap twice under the actual worker account/environment, restart the worker twice and inspect its preflight journal and retained history. Do not print its environment. After reboot, Docker restarts an already started context; run `runtime up` to start application services. Ordinary stop preserves every volume.

## Networking and limits

Nginx listens on loopback 8080; API 8000 and context 6380 stay loopback-only. Deep investigation URLs load `index.html`; `/api/` always proxies without SPA fallback. SSE stays unbuffered/uncached with a 60-second read timeout, exceeding fifteen-second heartbeats. Read/download endpoints never execute experiments.

For public hosting, configure actual DNS/TLS in the reviewed Nginx server, bind only that ingress publicly, and set exact HTTPS `FAULTGLASS_ALLOWED_ORIGINS`. Retain all body/rate/connection/header/streaming directives. Do not add cross-origin API access or visitor forwarding-header trust. Put source limits at the actual public edge: adding another proxy without verified source handling makes these aggregate limits. No hosted deployment is claimed until its edge is verified.

The command ceiling is exactly 327,680 bytes including chunked uploads. Nginx's fifteen-second inactivity timeout is complemented by the API's total fifteen-second body deadline, with request buffering disabled. Validation, admission and cancellation are bounded. One POST/second with burst five returns 429/`Retry-After: 10`. Concurrent requests are capped at 64/source. Reads/replay/exact-key recovery do not consume command rate. Non-JSON errors receive safe browser feedback.

Uvicorn ignores proxy headers; API admission accounting conservatively groups ingress requests into one source (one new start/ten seconds). The edge uses its actual remote address and strips visitor forwarding headers. Transient ingress/admission/stream counters reset on restart; durable queue, reservations, memory receipts and deadlines do not.

| Service | Memory / CPU / tasks          | Logs and storage                                                                     |
| ------- | ----------------------------- | ------------------------------------------------------------------------------------ |
| Context | 1 GiB, no swap / 1 CPU / 128  | 4 GiB disk, Docker local logs 4 × 64 MiB; AOF always, 768 MiB maxmemory, no eviction |
| API     | 1 GiB, no swap / 1 CPU / 128  | Private evidence root; bounded journal namespace                                     |
| Worker  | 1 GiB, no swap / 1 CPU / 128  | Same evidence/account; bounded journal namespace                                     |
| Ingress | 256 MiB, no swap / 1 CPU / 64 | Static files; access logs disabled; bounded journal namespace                        |

Each journal namespace caps persistent/runtime retention at 128 MiB each (256 MiB combined), with 16 MiB files; allow a current-file rotation margin. These are initial ceilings, not measured VM sizing. Separately constrained engines run sequentially within a serialized pair. Measure peak memory/disk and finalization headroom during clean-host verification. Context memory pressure rejects writes without eviction; full persistence must block work and be repaired with matched preserved state, never reset. The dedicated filesystem bounds disk growth; monitor context disk/AOF health.

## Recovery and upgrades

Use `runtime stop`, deploy reviewed source/dependencies and rebuild static files, then `runtime up`. Preserve mounted filesystems. API-only restart is `sudo systemctl restart faultglass-api`; jobs continue. `sudo systemctl restart faultglass-worker` owns bounded cleanup and reconciles complete reserved children without rerunning. Downtime counts against admission deadlines.

For unknown owned engines, inspect `docker ps -a --filter label=faultglass.run`. Use only the saved comparison identity with `python -m faultglass.recover --run-id <comparison-id>` under the same service account/environment. Never blanket-prune, remove volumes, alter receipts or rebuild missing manifests. Changed committed bytes remain integrity failures. Published exports survive later memory failure.

## Coordinated backup and restore

1. `runtime stop` closes admissions, stops API/worker and stops context. Verify no remaining owned engines or manual CLI writers.
2. Copy/snapshot stopped context and matching evidence as **one generation**, preserving owners, modes and structure. Record source commit, image digests, graph and both backup identities together. Keep private configuration separately.
3. Restore both halves to an isolated installation using the same images/configuration and account/mount paths. Keep ingress and worker stopped.
4. Start only context with its explicit restored bind path. Verify read-only snapshots/conclusions/downloads for known IDs and compare lengths/hashes with saved manifests. Run `python -m faultglass.verify` for known paired evidence. Never choose whichever backup half appears newer.
5. Only after coherent saved reads succeed, run preflight and enable services. Keep the original backup until the isolated restore drill passes.

Do not use `down -v` for normal recovery. A backup is not a tested restore until isolated read/hash verification actually passes.
