"""
Vercel Blob storage for shareable kit pages + once-per-domain limiting.

Setup (one time, in Vercel dashboard):
  Project -> Storage -> Create -> Blob. Vercel auto-adds BLOB_READ_WRITE_TOKEN
  to the project env. Redeploy. Done.

Every generated kit is stored as kits/kit-<slug>.html at a public URL. That URL is
the shareable link AND the cache: if a kit already exists for a domain, we serve the
stored one instead of re-running (the once-per-domain limit, durable).

Errors are captured (not swallowed) in last_error() so the API can report exactly
why a share link could not be produced.
"""
import os, json, urllib.request, urllib.error

API = "https://blob.vercel-storage.com"

_LAST_ERROR = None

def _token():
    return os.environ.get("BLOB_READ_WRITE_TOKEN", "")

def enabled():
    return bool(_token())

def last_error():
    return _LAST_ERROR

def _req(url, method="GET", data=None, headers=None):
    h = {"authorization": "Bearer " + _token(), "x-api-version": "7"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "ignore") or "{}")

def _capture(where, exc):
    """Record a readable reason for a Blob failure and return None."""
    global _LAST_ERROR
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read().decode("utf-8", "ignore")
        except Exception:
            body = ""
        _LAST_ERROR = f"{where}: HTTP {exc.code} {exc.reason} {body[:400]}".strip()
    else:
        _LAST_ERROR = f"{where}: {type(exc).__name__}: {exc}"
    return None

def find_kit(slug):
    """Return the public URL of an existing kit page for this slug, else None."""
    global _LAST_ERROR
    _LAST_ERROR = None
    if not enabled():
        _LAST_ERROR = "BLOB_READ_WRITE_TOKEN not set at runtime"
        return None
    try:
        r = _req(f"{API}?prefix=kits/kit-{slug}.html&limit=1")
        blobs = r.get("blobs") or []
        return blobs[0]["url"] if blobs else None
    except Exception as e:
        return _capture("find_kit", e)

def save_kit(slug, html):
    """Upload the share page; returns its public URL (stable path, overwrite allowed)."""
    global _LAST_ERROR
    _LAST_ERROR = None
    if not enabled():
        _LAST_ERROR = "BLOB_READ_WRITE_TOKEN not set at runtime"
        return None
    try:
        r = _req(f"{API}/kits/kit-{slug}.html", method="PUT",
                 data=html.encode("utf-8"),
                 headers={"content-type": "text/html; charset=utf-8",
                          "x-content-type": "text/html; charset=utf-8",
                          "x-add-random-suffix": "0",
                          "x-allow-overwrite": "1"})
        url = r.get("url")
        if not url:
            _LAST_ERROR = f"save_kit: no url in Blob response: {json.dumps(r)[:400]}"
        return url
    except Exception as e:
        return _capture("save_kit", e)
