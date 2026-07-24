"""
Self-contained helpers: .env loading, website scraping, and Claude calls.
No external files needed. Used by capture.py.
"""
import os, re, json, html, time, random, urllib.request, pathlib

HERE = pathlib.Path(__file__).resolve().parent

def load_env():
    envf = HERE / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
load_env()

MODEL = os.environ.get("MODEL", "claude-sonnet-5")

# broad crawl so we land on proof + lead magnets
CANDIDATE_PATHS = ["", "/customers", "/case-studies", "/success-stories", "/customer-stories",
                   "/resources", "/tools", "/product", "/products", "/platform", "/pricing",
                   "/why", "/roi", "/blog"]

def clean_domain(raw):
    raw = raw.strip().lower()
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.split("/")[0]
    return raw.lstrip("www.")

def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; CaptureKit/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype:
                return ""
            return r.read(400_000).decode("utf-8", "ignore")
    except Exception:
        return ""

def strip_html(h):
    h = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer).*?</\1>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    text = re.sub(r"(?s)<[^>]+>", " ", h)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

def scrape_site(domain):
    base = "https://" + domain
    seen, chunks = set(), []
    for path in CANDIDATE_PATHS:
        raw = fetch(base + path)
        if not raw:
            continue
        text = strip_html(raw)
        if len(text) < 120:
            continue
        key = text[:200]
        if key in seen:
            continue
        seen.add(key)
        chunks.append(f"--- {base + path} ---\n{text[:4000]}")
        if len(chunks) >= 7:
            break
    return "\n\n".join(chunks)

def anthropic_client():
    try:
        import anthropic
    except ImportError:
        raise SystemExit("Missing dependency. Run: pip install anthropic")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("Set ANTHROPIC_API_KEY (in env or .env). See .env.example.")
    return anthropic.Anthropic(api_key=key)

def _is_transient(exc):
    """429 rate limit, 529 overloaded, or a 5xx. These spike when several
    per-prospect sequences hit the API at once, and they clear on a short wait."""
    status = getattr(exc, "status_code", None)
    if status in (429, 500, 502, 503, 529):
        return True
    msg = str(exc).lower()
    return any(w in msg for w in ("overloaded", "rate limit", "rate_limit", "too many requests"))

def llm(client, prompt, max_tokens=2000, retries=1):
    # One retry with jittered backoff on a transient rate-limit/overload. The
    # jitter keeps parallel prospect sequences from retrying in lockstep and
    # colliding again. Kept short so a retry still fits Vercel's 60s cap.
    for attempt in range(retries + 1):
        try:
            msg = client.messages.create(model=MODEL, max_tokens=max_tokens,
                                         messages=[{"role": "user", "content": prompt}])
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        except Exception as e:
            if attempt < retries and _is_transient(e):
                # short, jittered: a retry must still leave room under the 60s cap
                time.sleep(1 + random.uniform(0, 1))
                continue
            raise

def extract_json(text):
    """Pull a JSON object out of a model response, tolerantly.

    The model occasionally wraps the JSON in a ```json fence, appends a stray
    sentence after the closing brace, or leaves literal newlines/tabs inside
    string values (e.g. multi-line email bodies), all of which strict json.loads
    rejects. So: drop a fence if present, decode from the first brace with
    raw_decode (which ignores trailing junk), and use strict=False (which allows
    control chars inside strings, preserving body line breaks)."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON found in model output:\n" + text[:500])
    snippet = text[start:]
    try:
        obj, _ = json.JSONDecoder(strict=False).raw_decode(snippet)
        return obj
    except json.JSONDecodeError:
        # Last resort: greedy outermost {...}, still non-strict.
        m = re.search(r"\{.*\}", snippet, re.S)
        if not m:
            raise ValueError("No JSON found in model output:\n" + text[:500])
        return json.loads(m.group(0), strict=False)

def llm_json(client, prompt, max_tokens=2000, schema=None):
    """Get a JSON object from the model.

    When `schema` is given, use structured outputs (output_config json_schema),
    which makes the API guarantee the response is valid JSON matching the schema.
    This is what eliminates the intermittent parse failures (unescaped quotes,
    empty/refused output) that even a retry couldn't recover from. Supported on
    current models (Sonnet 5 / Opus 4.8 / Haiku 4.5).

    If structured outputs aren't available at runtime for ANY reason (older
    anthropic SDK that doesn't accept output_config, an unsupported model, or a
    transient error), we fall through to the tolerant extract_json path with one
    retry — i.e. never worse than before.
    """
    if schema is not None:
        try:
            msg = client.messages.create(
                model=MODEL, max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": schema}})
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            return json.loads(text)  # guaranteed valid JSON under structured outputs
        except Exception:
            pass  # unavailable/failed -> tolerant fallback below

    # Tolerant path: extract_json + ONE retry on a parse or transient failure.
    for attempt in range(2):
        try:
            return extract_json(llm(client, prompt, max_tokens=max_tokens))
        except Exception as e:
            parse = isinstance(e, (ValueError, json.JSONDecodeError))
            if attempt == 0 and (parse or _is_transient(e)):
                time.sleep(1.0)
                continue
            raise
