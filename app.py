"""
Your hosted ICP Capture Kit agent.

  GET  /             -> the page (enter domain, watch it run, get the kit)
  POST /api/capture  -> {domain} -> runs the agent, returns the kit JSON

Run:
  pip install -r requirements.txt
  cp .env.example .env         # add ANTHROPIC_API_KEY + APOLLO_API_KEY
  uvicorn app:app --port 8000
  open http://localhost:8000

Env: ANTHROPIC_API_KEY (required), APOLLO_API_KEY (real prospects),
     APOLLO_ENRICH=1 to reveal real names + verified emails (costs Apollo credits).
"""
import pathlib
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import capture

HERE = pathlib.Path(__file__).resolve().parent
app = FastAPI(title="ICP Capture Kit")

class Req(BaseModel):
    domain: str
    email: str | None = None

@app.get("/", response_class=HTMLResponse)
def home():
    return (HERE / "web" / "index.html").read_text(encoding="utf-8")

@app.post("/api/capture")
def make(req: Req):
    try:
        return JSONResponse(capture.build_kit(req.domain))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
