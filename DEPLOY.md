# Deploying Insurance PoC V2.0 — GitHub + hosted backend + StackBlitz frontend

Why this shape: StackBlitz's WebContainer runs Node.js only (in-browser, WASM) — it
cannot run `backend_v2`, which depends on DuckDB's native Python bindings and LanceDB's
Rust bindings. So the backend needs a real host; the frontend can then be opened anywhere,
including StackBlitz.

## 0. Prerequisites

- Docker Desktop running locally (`docker info` should not error).
- A Docker Hub (or GitHub Container Registry) account to host the built image.
- A free account on a container host — these steps use **Render**; Railway/Fly.io work
  the same way (build image → push to registry → point host at the image).
- `GEMINI_API_KEY` (already in your local `.env`).

## 1. Push the source to GitHub

Already done locally: `git init`, `.gitignore` excludes secrets and the large regenerable
data files (`database/insurance_v2.duckdb`, `lance_store/`), initial commit made.

```powershell
git remote add origin <your-empty-repo-url>
git branch -M main
git push -u origin main
```

## 2. Build the backend image locally (bakes in your validated DuckDB + LanceDB data)

From the project root, with Docker Desktop running:

```powershell
docker build -f Dockerfile.backend -t <your-dockerhub-username>/insurance-poc-v2-backend:latest .
```

This must run from a machine that already has `database/insurance_v2.duckdb` and a
populated `lance_store/` (i.e. one where `setup_v2.bat` has already been run) — a
git-connected "build from source" host will NOT have these, since they're intentionally
gitignored (476 MB, regenerable).

## 3. Push the image to a registry

```powershell
docker login
docker push <your-dockerhub-username>/insurance-poc-v2-backend:latest
```

## 4. Deploy the image on Render

1. Render dashboard → **New → Web Service → Deploy an existing image**.
2. Image URL: `docker.io/<your-dockerhub-username>/insurance-poc-v2-backend:latest`.
3. Environment variables:
   - `GEMINI_API_KEY` = your key
   - `CORS_ORIGINS` = `*` (needed — StackBlitz preview URLs are dynamic/random per session,
     so they can't be allowlisted individually; the backend now reads this from env, see
     `backend_v2/config.py`)
4. Render sets `$PORT` automatically; the image's `CMD` already binds to it.
5. Deploy, then confirm: `https://<your-service>.onrender.com/api/v2/health` returns
   `duckdb.status: ok` and `lancedb.status: ok`.

**Free-tier note:** Render's free web services spin down after inactivity and take ~30-60s
to wake on the next request — fine for a demo you're about to use, just expect the first
`/api/v2/ask` after idle time to be slow. Upgrade to a paid instance if you need it always
warm.

## 5. Open the frontend anywhere, pointed at the hosted backend

**Via StackBlitz (no local setup needed, no config required):**

Just open:
```
https://stackblitz.com/github/nitinbajpai84/Insurance-Decision-Intelligence-Platform-v1.0/tree/main/frontend_v2
```

It works out of the box — `frontend_v2/.env` is committed and already points at the hosted
Render backend. Wait for `npm install` + first compile (can take 1-2 min on a cold
WebContainer boot), then open the preview and use `/ai-intelligence-v2` as normal.

The repo must be **public** for StackBlitz's GitHub import to find it (a private repo
returns "Repository not found" unless you connect a StackBlitz account with repo access).

### Two things that had to be fixed for this to work (2026-07-23)

1. **Next.js 15.5.x is broken in WebContainer.** Every route 500s with
   `Invariant: Expected workUnitAsyncStorage to have a store`. This is a Next.js
   regression, not app code — tracked in
   [vercel/next.js#84026](https://github.com/vercel/next.js/issues/84026) and
   [stackblitz/webcontainer-core#1978](https://github.com/stackblitz/webcontainer-core/issues/1978).
   15.4.x is unaffected. `package.json` previously said `"next": "^15.0.0"`, which resolved
   to the broken 15.5.19. Now pinned to exactly `15.4.1`, and **the lockfile was
   regenerated** — StackBlitz installs from `package-lock.json`, so pinning `package.json`
   alone would not have changed anything. If you ever bump Next again, re-test in
   WebContainer before relying on it for a demo.

2. **The API URL fell back to localhost.** `services/*.ts` default to
   `http://127.0.0.1:3001` when `NEXT_PUBLIC_API_V2_URL` is unset, and `.env.local` is
   gitignored — so a cloud IDE would have called the *viewer's own machine*. Fixed with a
   committed `frontend_v2/.env` holding the public Render URL, plus a narrow
   `!frontend_v2/.env` exception in `.gitignore`. Next.js loads `.env.local` over `.env`, so
   **local development is unchanged** — your local `.env.local` still points at
   `127.0.0.1:3001`. Never put secrets in `frontend_v2/.env`; `NEXT_PUBLIC_*` values are
   compiled into the browser bundle and are public by definition.

**Or deploy the frontend properly (Vercel), StackBlitz becomes optional:**

```powershell
cd frontend_v2
npx vercel --prod
```
Set the same `NEXT_PUBLIC_API_V2_URL` env var in the Vercel project settings.

## Notes

- The DuckDB file is read/write at runtime (glossary edits, query history, agent reasoning
  log). On Render's free tier the filesystem is ephemeral — writes persist until the
  service restarts/redeploys, then reset to what's baked into the image. Fine for a demo;
  if you want writes to persist long-term, add a persistent disk (Render/Fly/Railway all
  support this) and set `DUCKDB_PATH`/`LANCEDB_PATH` to point at it.
- Do NOT use `--reload` on the hosted backend (see `DEMO_RUNBOOK.md` — it's an unnecessary
  CPU-runaway risk in production, not just locally).
