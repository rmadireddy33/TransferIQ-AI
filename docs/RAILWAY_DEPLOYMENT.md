# Railway deployment alternative

Railway is **not the current TransferIQ AI production platform**. Production runs on Render; use [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) for the authoritative deployment procedure.

This file is retained only as a portability note. No current Railway deployment, volume, public URL, portal webhook, or 1.1.1 acceptance is claimed.

If Railway is deliberately selected later, preserve the same architecture:

- one application service, one replica, one Uvicorn worker;
- repository root as the build root;
- frontend production build plus backend requirements installation;
- start command python -m backend.start;
- persistent volume mounted at /data;
- health check /health;
- all current backend and controlled portal environment variables from the Render guide;
- no external database and no DATABASE_URL;
- UiPath secrets stored only in service environment settings.

The checked-in railway.json and railpack.json were created during an earlier backend-only milestone. They must be reviewed against the current combined frontend/backend build before reuse. Do not treat their presence as deployment evidence.

Storage must keep the private database/documents, isolated demo-run registry/directories, and portal tracking registry together under /data. Back up SQLite and PDFs consistently, retain one writer, and never delete the volume to repair a failed release.

Any future Railway rollout requires fresh verification of:

1. the frontend production build and portal deep-link fallback;
2. schema v4 private database migration;
3. demo registry v2 and portal registry v2 persistence;
4. restart/redeployment preservation of SQLite and PDF checksums;
5. controlled portal session, CSRF, idempotency, and webhook configuration;
6. one bounded real UiPath run only after the target webhook and reviewer assignment are valid.

No Git initialization, commit, push, or release procedure is prescribed here. Source control is managed by the project owner outside this workspace.
