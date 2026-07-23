"""
Vercel Blob storage for shareable kit pages + once-per-domain limiting.

Setup (one time, in Vercel dashboard):
  Project -> Storage -> Create -> Blob. Vercel auto-adds BLOB_READ_WRITE_TOKEN
  to the project env. Redeploy. Done.

Every generated kit is stored as kit-<slug>.html at a public URL. That URL is the
shareable link AND the cache: if a kit already exists for a domain, we serve the
stored one instead of re-running (your once-per-domain limit, durable).
"""
import os, json, urllib.request

API = "https://blob.vercel-storage.com"

def _token():
    return os.environ.get("BLOB_READ_WRITE_TOKEN", "")

def _req(url, method="GET", data=None, headers=None):
    h = {"authorization": "Bearer " + _token(), "x-api-version": "7"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "ignore") or "{}")

def enabled():
    return bool(_token())

def find_kit(slug):
    """Return the public URL of an existing kit page for this slug, else None."""
    if not enabled():
        return None
    try:
        r = _req(f"{API}?prefix=kits/kit-{slug}.html&limit=1")
        blobs = r.get("blobs") or []
        return blobs[0]["url"] if blobs else None
    except Exception:
        return None

def save_kit(slug, html):
    """Upload the share page; returns its public URL (stable path, no random suffix)."""
    if not enabled():
        return None
    try:
        r = _req(f"{API}/kits/kit-{slug}.html", method="PUT",
                 data=html.encode("utf-8"),
                 headers={"content-type": "text/html; charset=utf-8",
                          "x-add-random-suffix": "0",
                          "x-content-type": "text/html; charset=utf-8"})
        return r.get("url")
    except Exception:
        return None
