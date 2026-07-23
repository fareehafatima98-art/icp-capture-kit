# Build Notes

A running log of changes made to this repo. A new line is appended every time
something changes. Newest entries at the bottom.

- 2026-07-23 — Unpacked ICP Capture Kit v1 sources into the repo root (app.py, capture.py, apollo.py, scrape_llm.py, web/index.html, ick-foreai.html, deploy/config files) and removed the packaged icp-capture-kit-v1.zip.
- 2026-07-23 — Added render.yaml (Render blueprint) as a Python-host deploy option.
- 2026-07-23 — Wired up Vercel serverless deploy: added api/index.py entrypoint and vercel.json (catch-all rewrite to the function, maxDuration 60s, bundles web/**); made capture.build_kit tolerate a read-only filesystem; documented the Vercel path in README.
- 2026-07-23 — Merged PR #1 into main (main was empty, which caused the Vercel 404).
- 2026-07-23 — Fixed /api/capture to catch (Exception, SystemExit) so a missing API key returns readable JSON instead of a hard "Internal Server Error"; merged as PR #2 into main.
- 2026-07-23 — Added BUILD_NOTES.md to track repo changes going forward.
- 2026-07-23 — Upgraded engine + UI to v2: per-prospect sequences (each of 5 prospects gets its own tailored 5-email sequence, ~25 emails), progressive Apollo fallback that surfaces errors, and a tabbed results UI. Re-applied the read-only-filesystem guard to build_kit (v2 had dropped it) so it still runs on Vercel. Note: v2 makes ~6 sequential Claude calls, which risks exceeding Vercel's 60s function limit.
- 2026-07-23 — Parallelized the 5 per-prospect Claude calls in build_kit (ThreadPoolExecutor) so wall-clock is ~1 call instead of 5 in a row, keeping the request under Vercel's 60s limit. Output and ordering unchanged.
- 2026-07-23 — Served the home page with Cache-Control: no-store so a fresh deploy's UI shows immediately instead of a stale browser-cached copy.
- 2026-07-23 — Fixed Apollo 403: corrected the API base to https://api.apollo.io/api/v1 and the people search path to /mixed_people/api_search (the bare /mixed_people/search is Apollo's internal UI route and 403s for API keys). Note: this endpoint requires a MASTER Apollo API key.
- 2026-07-23 — Applied v3: shareable kit pages via Vercel Blob (storage.py, report_html.py) with once-per-domain caching and a /k/{slug} redirect route, richer 60-90 word emails, verified-email-preferred prospect selection, own-customer filtering, and location targeting. Reverted the Apollo endpoint to /v1/mixed_people/search per the working mixed-search key (no master key needed) and turned enrichment on. Re-applied four repo-only fixes that v3's local base lacked: read-only-FS guard and parallel per-prospect generation in capture.py, and Cache-Control: no-store + (Exception, SystemExit) handling in app.py.
- 2026-07-23 — Re-fixed Apollo 403 (v3's /v1/mixed_people/search 403'd again in production): base back to https://api.apollo.io/api/v1 and search path to /mixed_people/api_search. Per Apollo docs this is the public People Search endpoint, consumes 0 credits, and requires a MASTER Apollo API key (a master key does not itself spend credits; only enrichment does).
- 2026-07-23 — Removed the "video lands here this week" placeholder from web/index.html and report_html.py (CTA now flows heading -> Calendly); kept VIDEO_EMBED="" in report_html.py to switch a video on later (renders nothing while empty). Made storage.py surface the real Blob error via last_error() instead of swallowing it, allowed overwrite on upload, and had app.py return share_error when no share link is produced. (Storage backend decision — local folder vs Blob — still open; not yet merged/deployed.)
