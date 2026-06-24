# Deployment Guide — Spotify Review Discovery Engine

This project ships as two independent services:

| Service | Stack | Hosted on |
|---|---|---|
| `backend/` | FastAPI + pandas + Groq | **Railway** |
| `frontend/` | Next.js 14 (App Router) | **Vercel** |

Deploy the backend first so you can wire its public URL into the frontend.

---

## 1. Prerequisites

- A GitHub repository containing this project (already set up at `origin`).
- A Railway account: <https://railway.app>
- A Vercel account: <https://vercel.com>
- A Groq API key: <https://console.groq.com/keys>

The bundled review data (`backend/data/insights_*.csv`, `themes_*.json`, `discovery_insights_report_*.md`) ships with the repo so the backend works out of the box on Railway — no separate database is required.

---

## 2. Deploy the backend to Railway

### 2.1 Create the service

1. Log in to Railway and click **New Project → Deploy from GitHub repo**.
2. Pick this repository.
3. After Railway creates the project, open the service’s **Settings** tab.
4. **Root Directory** — choose **one** of these (both work now):
   - **Option A (recommended):** leave Root Directory **empty** (repo root). Railway uses the root `Dockerfile` which copies `backend/` into the image.
   - **Option B:** set Root Directory to `backend`. Railway uses `backend/Dockerfile` directly.
5. In **Settings → Build**, confirm the builder is **Dockerfile** (set automatically via `railway.toml`).
6. If the build still fails, add a service variable: `RAILWAY_DOCKERFILE_PATH` = `Dockerfile` (repo root) or `backend/Dockerfile` (if root dir is `backend`).

### 2.2 Set environment variables

In the Railway service → **Variables**, add:

| Variable | Value | Notes |
|---|---|---|
| `GROQ_API_KEY` | `gsk_...` | Required for the Chat endpoint. |
| `GROQ_CHAT_MODEL` | `llama-3.1-8b-instant` | Smaller model with much higher rate limits. |
| `ALLOWED_ORIGINS` | `https://<your-app>.vercel.app` | Comma-separate multiple origins. Set after you know the Vercel URL (you can come back and update). |
| `DATA_DIR` | `./data` | Default; leave as is. |
| `PYTHONUNBUFFERED` | `1` | Ensures logs stream live. |

Railway sets `PORT` automatically — do **not** override it.

### 2.3 Verify

After the first deploy:

- Open the Railway URL Railway gives you (e.g. `https://spotify-engine-production.up.railway.app`).
- `GET /api/health` should return `{"status":"ok","data":{...}}`.
- `GET /docs` shows the FastAPI Swagger UI.
- `POST /api/chat` with `{"question":"Why do users struggle to discover new music?"}` returns a 5-section answer.

Copy the **public URL** — you’ll need it for Vercel.

---

## 3. Deploy the frontend to Vercel

### 3.1 Create the project

1. In Vercel click **Add New → Project** and import the same GitHub repo.
2. When Vercel asks for the **Root Directory**, set it to `frontend`.
3. Vercel auto-detects Next.js. Leave the build/install commands at the defaults (`npm run build` / `npm install`).

### 3.2 Set environment variables

In Vercel → **Settings → Environment Variables**, add (Production + Preview):

| Variable | Value |
|---|---|
| `BACKEND_URL` | `https://<your-railway-app>.up.railway.app` |
| `NEXT_PUBLIC_API_URL` | `https://<your-railway-app>.up.railway.app` |

**Important:** `NEXT_PUBLIC_API_URL` must be set before the Vercel build — it is baked into the client bundle. After changing it, trigger a **Redeploy**.

The browser calls Railway directly for API requests (avoids Vercel serverless timeouts on chat). Railway CORS automatically allows any `*.vercel.app` origin.

### 3.3 Deploy

Click **Deploy**. After the first build:

- Open the Vercel URL.
- The dashboard should load 1,876 indexed reviews.
- Visit the Chat tab and ask a question — you should see the 5-section professional response.

### 3.4 Tighten CORS on the backend (one-time)

Once you know the Vercel domain, go back to Railway → Variables and set:

```
ALLOWED_ORIGINS=https://<your-app>.vercel.app,https://<your-app>-<branch>.vercel.app
```

Redeploy the backend. This locks down API access to your frontend.

---

## 4. Custom domains (optional)

- **Vercel**: Settings → Domains → add your custom domain (e.g. `discovery.yourdomain.com`). Update CNAME at your registrar.
- **Railway**: Settings → Domains → Generate Domain or attach a custom subdomain (e.g. `api.yourdomain.com`).

If you add a backend custom domain, update both `BACKEND_URL` and `NEXT_PUBLIC_API_URL` in Vercel, plus `ALLOWED_ORIGINS` to include the new frontend domain.

---

## 5. CI / future updates

Both Railway and Vercel auto-redeploy on `git push origin main`:

- Push backend changes → Railway rebuilds and rolls out.
- Push frontend changes → Vercel rebuilds and rolls out (zero-downtime).

To refresh the indexed review dataset:

1. Re-run the pipeline locally: `python run_pipeline.py`
2. Copy the new outputs into `backend/data/` (see `backend/data/README.md`).
3. Commit and push — Railway will pick up the new files on the next deploy.

---

## 6. Troubleshooting

**Backend cold start is slow.** First request after idle can take 10–15s while pandas loads the CSV. Subsequent requests are fast.

**Chat returns the local fallback even when Groq is up.** Check Railway logs for `Groq model '...' unavailable`. Most common cause is a rate-limit on the 70B model — confirm `GROQ_CHAT_MODEL=llama-3.1-8b-instant` is set.

**`CORS error` in browser console.** `ALLOWED_ORIGINS` on Railway must include the exact Vercel URL (including `https://`). Update and redeploy the backend.

**Frontend shows "Cannot reach the API".** Either `BACKEND_URL` is unset/wrong in Vercel, or the Railway service is down. Hit `<railway-url>/api/health` directly to check.

**Bundle size too large for Vercel free tier.** Confirm `frontend/.next` is in `.gitignore` and the repo isn’t committing build output.
