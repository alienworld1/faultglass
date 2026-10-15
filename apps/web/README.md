# FaultGlass web

Start a case against approved FalkorDB engines, follow its saved investigation, and inspect paired evidence.

```sh
pnpm install --frozen-lockfile
pnpm dev
pnpm lint
pnpm build
pnpm format:check
```

Use pnpm 11.25.0. `pnpm install` prepares the pinned Node 24.19.0 runtime for project commands through [pnpm runtime management](https://pnpm.io/package_json#devenginesruntime). The frontend uses React, Vite, the React compiler, Tailwind, and oxlint. Semantic color and font tokens live in `src/globals.css`; system fonts keep the shell usable without a remote font service.

Start the loopback API and separate persistent worker using the [saved investigation setup](../investigator/INVESTIGATIONS.md). Vite proxies `/api` to `127.0.0.1:8000`. Open `/` to select or import a case, then reopen the returned `/investigations/<id>` URL to recover saved progress. Reload and back/forward navigation only read state. Shared contracts are generated from the authoritative Python models. The setup guide also documents same-origin hosting, deep-link fallback, and SSE proxy configuration.
