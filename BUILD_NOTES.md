# Build Notes

A running log of changes made to this repo. A new line is appended every time
something changes. Newest entries at the bottom.

- 2026-07-23 — Unpacked ICP Capture Kit v1 sources into the repo root (app.py, capture.py, apollo.py, scrape_llm.py, web/index.html, ick-foreai.html, deploy/config files) and removed the packaged icp-capture-kit-v1.zip.
- 2026-07-23 — Added render.yaml (Render blueprint) as a Python-host deploy option.
- 2026-07-23 — Wired up Vercel serverless deploy: added api/index.py entrypoint and vercel.json (catch-all rewrite to the function, maxDuration 60s, bundles web/**); made capture.build_kit tolerate a read-only filesystem; documented the Vercel path in README.
- 2026-07-23 — Merged PR #1 into main (main was empty, which caused the Vercel 404).
- 2026-07-23 — Fixed /api/capture to catch (Exception, SystemExit) so a missing API key returns readable JSON instead of a hard "Internal Server Error"; merged as PR #2 into main.
- 2026-07-23 — Added BUILD_NOTES.md to track repo changes going forward.
