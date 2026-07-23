"""
ICP Capture Kit server v3.

  GET  /             -> the page
  POST /api/capture  -> {domain} -> kit JSON + share_url
                        Once-per-domain: if a kit page already exists in Blob storage,
                        returns the stored share_url instead of re-running.
  GET  /k/{slug}     -> redirects to the stored share page for a domain

Env: ANTHROPIC_API_KEY, APOLLO_API_KEY, APOLLO_ENRICH=1,
     BLOB_READ_WRITE_TOKEN (auto-added when you enable Blob storage on Vercel).
"""
import re, pathlib
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
import capture, storage, report_html

HERE = pathlib.Path(__file__).resolve().parent
app = FastAPI(title="ICP Capture Kit")

class Req(BaseModel):
    domain: str
    force: bool = False    # you can pass force:true yourself to regenerate

@app.get("/", response_class=HTMLResponse)
def home():
    html = (HERE / "web" / "index.html").read_text(encoding="utf-8")
    # no-store so a new deploy's UI is served immediately instead of a stale
    # cached copy (the page is tiny, so there's nothing to gain from caching).
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})

@app.post("/api/capture")
def make(req: Req):
    slug = re.sub(r"[^a-z0-9]", "", req.domain.strip().lower()
                  .replace("https://", "").replace("http://", "")
                  .replace("www.", "").split("/")[0].split(".")[0])
    # once-per-domain limit: serve the stored kit if it exists
    if not req.force:
        existing = storage.find_kit(slug)
        if existing:
            return JSONResponse({"cached": True, "share_url": existing, "slug": slug})
    try:
        kit = capture.build_kit(req.domain)
        share = None
        if storage.enabled():
            share = storage.save_kit(kit["slug"], report_html.render(kit))
        kit["share_url"] = share
        # Surface why a share link is missing instead of silently returning null.
        if not share:
            kit["share_error"] = (storage.last_error() if storage.enabled()
                                  else "blob storage not enabled (BLOB_READ_WRITE_TOKEN missing at runtime)")
        kit["cached"] = False
        return JSONResponse(kit)
    # Catch SystemExit too: the engine raises it for missing keys / deps, and
    # SystemExit is NOT an Exception subclass, so a bare `except Exception`
    # would let it escape as a hard 500 the page can't parse.
    except (Exception, SystemExit) as e:
        return JSONResponse({"error": str(e) or e.__class__.__name__}, status_code=500)

@app.get("/k/{slug}")
def share(slug: str):
    url = storage.find_kit(re.sub(r"[^a-z0-9]", "", slug.lower()))
    if url:
        return RedirectResponse(url)
    return JSONResponse({"error": "no kit found for that domain"}, status_code=404)
