"""
Self-contained helpers: .env loading, website scraping, and Claude calls.
No external files needed. Used by capture.py.
"""
import os, re, json, html, urllib.request, pathlib

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

def llm(client, prompt, max_tokens=2000):
    msg = client.messages.create(model=MODEL, max_tokens=max_tokens,
                                 messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

def extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("No JSON found in model output:\n" + text[:500])
    return json.loads(m.group(0))
