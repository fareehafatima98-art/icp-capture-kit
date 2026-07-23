# ICP Capture Kit — your hosted agent

One agent, hosted by you at **kit.fareehafatima.com**. Someone enters a domain. It reads the
site, works out who actually buys, pulls real prospects, and writes a ready-to-send 5-email
sequence built around that company's own case study, lead magnet, and product.

It is *your* agent. You run companies through it and hand founders the output. For the generic
tier, you give founders the link and let them run their own domain.

## What makes it real (not placeholder)
- **Claude** reads the site and writes the emails.
- **Apollo** supplies real prospects. Enrichment is **OFF by default** (first names only, no
  credits), which is how you want it.
- Every email is grounded in a **real asset pulled from the site**: their actual lead magnet
  (email 2), their actual named case study (email 3), their actual free trial (email 4). If an
  asset genuinely isn't on the site, the agent skips it and uses a real proof point. It never
  invents a customer or a result.

## Files (all self-contained, nothing external)
| file | role |
|------|------|
| `app.py` | server: `GET /` serves the page, `POST /api/capture {domain}` runs the agent |
| `web/index.html` | the page: enter a domain, watch it run, get the kit (copy-paste ready) |
| `capture.py` | the agent: scrape -> extract real assets -> Apollo prospects -> write sequence |
| `apollo.py` | Apollo client (search + optional enrich) |
| `scrape_llm.py` | website scraping + Claude helpers |
| `ick-foreai.html` | a pre-generated example for fore ai, to hand-deliver as-is |
| `Procfile` / `Dockerfile` | host config |

## Run locally first (to check it works)
```bash
pip install -r requirements.txt
cp .env.example .env         # add ANTHROPIC_API_KEY + APOLLO_API_KEY (leave APOLLO_ENRICH blank)
uvicorn app:app --port 8000
```
Open http://localhost:8000, type a domain, watch it run.

## Put it live at kit.fareehafatima.com (about 10 minutes)
This is a Python web app, so use a host that runs Python (Render is the simplest free one).

1. **Push this folder to your ICP Capture Kit git repo** (you already made the repo):
   ```bash
   cd capture-kit
   git init && git add . && git commit -m "ICP Capture Kit agent"
   git remote add origin <your-repo-url>
   git push -u origin main
   ```
   (`.gitignore` keeps your `.env` and keys out of the repo.)

2. **Create the service on Render** (render.com):
   - New -> Web Service -> connect the repo.
   - Environment: Python. Start command is auto-detected from `Procfile`
     (`uvicorn app:app --host 0.0.0.0 --port $PORT`).
   - Under **Environment**, add: `ANTHROPIC_API_KEY`, `APOLLO_API_KEY`. Leave `APOLLO_ENRICH` unset.
   - Deploy. Render gives you a URL like `icp-capture-kit.onrender.com`. Test it there first.

3. **Point your subdomain at it:**
   - In Render, open the service -> Settings -> Custom Domains -> add `kit.fareehafatima.com`.
   - Render shows a CNAME target. In your domain's DNS (where fareehafatima.com is managed),
     add a **CNAME** record: name `kit`, value = the target Render gave you.
   - Wait for it to verify (usually minutes). Done: kit.fareehafatima.com is live.

Any Python host works the same way (Railway, Fly.io). The keys always live on the host as
environment variables, never in the repo.

## Deploy on Vercel (free, no card)
This repo is also wired for Vercel's free Hobby tier (`vercel.json` + `api/index.py` run the
FastAPI app as a serverless function).

1. Push this repo to GitHub.
2. On vercel.com: **Add New -> Project**, import the repo. Framework Preset: **Other** (the
   `vercel.json` handles routing; there's no build step).
3. **Settings -> Environment Variables**, add: `ANTHROPIC_API_KEY`, `APOLLO_API_KEY`. Leave
   `APOLLO_ENRICH` unset.
4. Deploy, then test the `*.vercel.app` URL. Add `kit.fareehafatima.com` under
   **Settings -> Domains** and point a CNAME at Vercel (set the record to **DNS only** in
   Cloudflare while it verifies).

Note: serverless functions cap at **60s** per request (Hobby ceiling). The agent runs two
Claude calls plus a site crawl, so a slow target site can occasionally hit that limit; just
retry, or move to a Python host (Render/Railway/Fly.io) for no time limit.

## Credit control
Prospect **search** is free. **Enrichment** (real names + emails) is off and stays off unless you
set `APOLLO_ENRICH=1`. You're running first-names-only, so leave it blank.
