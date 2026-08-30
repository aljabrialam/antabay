# Deploying Antabay

The backend (FastAPI + SSE + a database) runs on **Render** as an always-on
service. The frontend (React console) runs on **Vercel** as a static site.
They're separate deployments that talk to each other over HTTPS.

## 1. Backend → Render

1. Push this repo to GitHub (already done) with `render.yaml` at the root —
   Render reads it as a **Blueprint** and provisions both the web service
   and a free Postgres database from it in one step.
2. In the Render dashboard: **New +** → **Blueprint** → connect your GitHub
   account (if you signed up with email/Google, you can still link GitHub
   as a separate integration here) → select the `antabay` repo.
3. Render will show two resources from `render.yaml`: the `antabay-backend`
   web service and the `antabay-db` Postgres database. Click **Apply**.
4. Once created, open `antabay-backend` → **Environment** and fill in the
   variables marked `sync: false` (Render leaves these blank on purpose —
   they're secrets, never committed to the repo):
   - `ATLAS_BASE_URL`, `ATLAS_CLIENT_ID`, `ATLAS_CLIENT_SECRET`
   - `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL`, `QWEN_MODEL`
   - `CORS_ALLOWED_ORIGINS` — leave blank for now, you'll set it after step 2
   (copy the values from your local `.env` — never paste `.env` itself
   anywhere, just the individual values)
5. Save — Render redeploys automatically. Note the service URL it gives you,
   e.g. `https://antabay-backend.onrender.com`. Check `/health` on that URL
   returns `{"status": "ok"}`.

**Free tier note**: the service spins down after 15 minutes idle and takes
about a minute to wake back up on the next request. Open it a minute before
you need it live.

## 2. Frontend → Vercel

1. In the Vercel dashboard: **Add New** → **Project** → import the same
   GitHub repo.
2. Set **Root Directory** to `frontend`.
3. Add an environment variable: `VITE_API_BASE_URL` =
   `https://antabay-backend.onrender.com` (the URL from step 1.5, no
   trailing slash).
4. Deploy. Vercel will run `npm run build` and serve the static output.

## 3. Close the loop: CORS

Back in Render, set `CORS_ALLOWED_ORIGINS` on `antabay-backend` to the
Vercel URL Vercel just gave you (e.g.
`https://antabay.vercel.app`) and save to trigger a redeploy. Until this is
set, the browser will block the frontend's requests to the backend.

## 4. Put a journey on it

A fresh database has no journeys. Either:
- Run `backend/scripts/seed_console_fixture.py`'s `replay` scenario against
  the deployed `JOURNEY_DB_URL` (copy the connection string from the Render
  Postgres dashboard, set it locally, run the script once), or
- Point people at `/journey/{id}/replay` for the canonical captured demo
  run once it's seeded — this replays a fixed event history and makes no
  live calls to Atlas or Qwen (FR-012), so it's safe to leave public.

## Local development is unaffected

`VITE_API_BASE_URL` defaults to empty, which keeps using Vite's dev-only
`/api`/`/journeys` proxy to `localhost:8000` exactly as before — none of
this changes local `npm run dev` / `uvicorn ... --reload` workflows.
