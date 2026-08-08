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

**Via StackBlitz (no local setup needed):**

1. Go to `https://stackblitz.com/github/<your-username>/<your-repo>/tree/main/frontend_v2`.
2. Once it boots, set the env var StackBlitz uses for the dev server: create/edit
   `frontend_v2/.env.local` in the StackBlitz editor:
   ```
   NEXT_PUBLIC_API_V2_URL=https://<your-service>.onrender.com
   ```
3. StackBlitz auto-runs `npm run dev`; open the preview and use `/ai-intelligence-v2` etc.
   as normal.

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
