# FaultGlass web

A minimal, accessible product shell for comparing reproducible cases across FalkorDB engines.

```sh
pnpm install --frozen-lockfile
pnpm dev
pnpm lint
pnpm build
pnpm format:check
```

Use pnpm 11.25.0. `pnpm install` prepares the pinned Node 24.19.0 runtime for project commands through [pnpm runtime management](https://pnpm.io/package_json#devenginesruntime). The frontend uses React, Vite, the React compiler, Tailwind, and oxlint. Semantic color and font tokens live in `src/globals.css`; system fonts keep the shell usable without a remote font service.

Execution is currently available through the [local comparison command](../investigator/README.md). Reloading the shell does not start a comparison. Shared contracts are generated from the authoritative Python models.
