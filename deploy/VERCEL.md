# Publish the free public preview

Deploy the browser preview to **Vercel Hobby**. Visitors can explore the included
cases, download a case, and follow the built-in **Run locally** guide. Real
investigations run on the visitor's own machine. No backend, database, API key,
custom domain, or paid service is needed for the website.

The Vercel configuration builds an explicit `showcase` mode. The ordinary local
development server and `pnpm build` still provide the complete investigation
workspace. The public preview never contacts a backend or claims to show live
investigation results.

## One-time setup

1. Push this commit to GitHub. Make sure
   [the repository](https://github.com/alienworld1/faultglass) is publicly readable
   so visitors can clone it. Public access has not been verified; check the link
   in a signed-out browser before sharing the website.
2. In [Vercel](https://vercel.com/new), import the GitHub repository and choose
   the **Hobby** plan for a personal, non-commercial project.
3. Set **Root Directory** to **`apps/web`** and **Node.js Version** to **24.x**.
4. Add **`ENABLE_EXPERIMENTAL_COREPACK=1`** to Production and Preview environment
   variables. This selects the pnpm version pinned in `package.json`.
5. Deploy. The committed `vercel.json` supplies the Vite framework, frozen install,
   showcase build, `dist` output, and browser deep-link routing. Leave the build
   and install command overrides at their repository defaults.

Share the production `.vercel.app` address. Git pushes trigger new deployments.
There are no frontend secrets to configure. Never add `GEMINI_API_KEY` to Vercel
or to a `VITE_` variable.

## Verify the website

- The homepage explains that investigations run locally. Both included cases can
  be selected, inspected, and downloaded.
- **Run locally** opens `/run-locally`; refreshing that URL works.
- Browser network tools show no `/api` calls. A direct request to `/api/health`
  returns 404 rather than the app's HTML.
- An old `/investigations/<id>` link shows local setup instructions; the public
  preview cannot reopen evidence saved on someone else's machine.
- Check the layout on a phone-sized viewport and follow the setup guide from a
  clean compatible Linux machine before claiming that setup has been verified.

The local preview is:

```sh
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web build:showcase
pnpm --dir apps/web preview --host 127.0.0.1
```

Vite preview uses port 4173 by default. To return to the full local workspace,
run `./deploy/local start`. For a normal static workspace build, use
`pnpm --dir apps/web build`.

## Why the backend is local

FaultGlass needs a Linux/amd64 Docker daemon to start fresh engine containers,
persistent FalkorDB graph storage, private evidence storage, and an API and
singleton worker sharing the same account and local locks. Its preflight rejects
ARM hosts. A managed FastAPI deployment alone cannot run an investigation.

[Render Free](https://render.com/docs/free) sleeps after inactivity and has no
persistent disk; [Render disks](https://render.com/docs/disks) require paid
services. Docker image hosting is not equivalent to access to a host Docker daemon.
Oracle's [Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
AMD shape has 1 GB RAM, while the larger free A1 shape is ARM. Neither is a
recommended drop-in host for this application. A free always-on cloud backend
has not been established for the current verified engine pair.

The public preview avoids those requirements entirely. For future full hosting,
use the persistent Linux host instructions in [SETUP.md](SETUP.md); size and
verify the host before admitting public investigations.

## Free-tier scope

[Vercel Hobby](https://vercel.com/docs/plans/hobby) is for personal,
non-commercial use and remains subject to its quotas. Local Docker comparisons
need no model account. Optional Gemini-guided investigations use the visitor's
own key; [free API access and limits](https://ai.google.dev/gemini-api/docs/pricing)
depend on their account and model. The website does not promise free model quota.

Provider documentation checked October 18, 2026. No cloud deployment or clean-host
installation is claimed by this guide.
