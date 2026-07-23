"""
Vercel serverless entrypoint.

Vercel serves Python functions from the `api/` directory and looks for an
ASGI/WSGI app named `app`. We add the project root to sys.path and re-export
the FastAPI app defined in app.py. All routes are rewritten to this function
by vercel.json.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app import app  # noqa: E402  (re-exported for Vercel's Python runtime)
