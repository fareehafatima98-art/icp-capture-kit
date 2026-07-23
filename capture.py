#!/usr/bin/env python3
"""
ICP Capture Kit engine v3.

v3 upgrades over v2:
  - Emails are fuller and more specific (v1-grade): 60-90 words, each must carry a
    concrete detail from the company's real assets. Generic filler is rejected in-prompt.
  - Prospect selection prefers people with verified emails: enrich up to 8, keep the 5
    with emails first, so kits are ready-to-send.
  - Filters out the company's own named customers (never pitch their customers back).
  - Location targeting inferred from the site (e.g. Australia for AU curricula).
  - Explicit MODEL guard: refuses haiku for email writing (quality floor).

Requires ANTHROPIC_API_KEY, APOLLO_API_KEY. APOLLO_ENRICH=1 for real names + emails.
"""
import os, re, json, sys, pathlib
from concurrent.futures import ThreadPoolExecutor
import scrape_llm as core
from apollo import Apollo

# quality floor: never write emails with a haiku-class model
if "haiku" in os.environ.get("MODEL", "").lower():
    os.environ["MODEL"] = "claude-sonnet-5"
    core.MODEL = "claude-sonnet-5"

def extract_assets(client, domain, site_text):
    prompt = f"""You are a sharp B2B go-to-market analyst reading {domain}. From the scraped
copy below, extract REAL, specific assets. Do not invent. If something isn't present, return an
empty list for it, do not fabricate.

Return ONLY JSON:
{{
 "company": "display name",
 "product_summary": "2 plain sentences on what it does",
 "icp_personas": ["5-7 exact buyer titles who buy this"],
 "buyer_titles": ["4-6 job titles to search for prospects"],
 "employee_ranges": ["Apollo size buckets for their ICP, from 1,10 11,50 51,200 201,500 501,1000 1001,5000"],
 "keyword_tags": ["3-6 industry/segment tags for their ICP's employers"],
 "target_locations": ["countries/regions their site implies they sell into, e.g. Australia; empty if global"],
 "named_customers": ["every customer named anywhere in the copy"],
 "case_studies": [{{"customer":"named customer","result":"the concrete result or what they did"}}],
 "lead_magnets": [{{"name":"the free tool/calculator/guide","url":"its url if shown"}}],
 "free_trial_url": "url to try/sign up if present, else empty",
 "proof_points": ["named logos or hard results found in the copy"]
}}

SCRAPED COPY:
{site_text[:16000]}
"""
    return core.extract_json(core.llm(client, prompt, max_tokens=1700))

def find_prospects(assets, enrich=False, top_n=5):
    """Fallback search -> enrich up to 8 -> prefer prospects WITH verified emails ->
    filter out the company's own named customers. Surfaces errors."""
    if not os.environ.get("APOLLO_API_KEY"):
        return {"market_size": None, "prospects": [], "enriched": False,
                "error": "APOLLO_API_KEY is not set on the server"}
    ap = Apollo()
    titles = assets.get("buyer_titles") or assets.get("icp_personas") or []
    locs = assets.get("target_locations") or None
    attempts = [
        dict(employee_ranges=assets.get("employee_ranges"), keyword_tags=assets.get("keyword_tags"),
             person_locations=locs),
        dict(employee_ranges=assets.get("employee_ranges"), keyword_tags=None, person_locations=locs),
        dict(employee_ranges=None, keyword_tags=None, person_locations=locs),
        dict(employee_ranges=None, keyword_tags=None, person_locations=None),
    ]
    r, err = {}, None
    for a in attempts:
        r = ap.people_count(titles, per_page=10, **a)
        err = r.get("error")
        if r.get("sample"):
            break
    sample = r.get("sample", [])

    # never pitch their own customers
    known = {c.strip().lower() for c in (assets.get("named_customers") or []) if c}
    def is_customer(p):
        co = (p.get("company") or "").strip().lower()
        return bool(co) and any(co in k or k in co for k in known)
    sample = [p for p in sample if not is_customer(p)]

    prospects = sample
    if enrich and sample:
        real = ap.enrich_people([p["id"] for p in sample[:8] if p.get("id")])
        if real:
            real = [p for p in real if not is_customer(p)]
            with_email = [p for p in real if p.get("email")]
            without = [p for p in real if not p.get("email")]
            prospects = with_email + without
    return {"market_size": r.get("total"), "prospects": prospects[:top_n],
            "enriched": bool(enrich), "error": err}

VOICE = """VOICE AND QUALITY BAR (strict):
- Each body is 60 to 90 words. Substantial, not thin. Every email must carry at least one
  CONCRETE detail from the real assets (a named customer, a real number, the actual lead
  magnet name, a specific feature). An email that could be sent by any company is a failure.
- Warm, human, specific. No em dashes. No exclamation marks. No jargon (never: self-healing,
  end-to-end, robust, seamless, leverage as a verb, streamline, cutting-edge).
- One honest human nod to what this person's role actually feels like. Never invent facts
  about the person; stay role-level unless a fact is given.
- Bodies open with "Hi {first}," using the REAL first name. One soft CTA per email, at the end.
- Subjects: concrete and curiosity-pulling, 5-9 words, no clickbait."""

def write_prospect_sequence(client, assets, prospect):
    first = prospect.get("first_name") or "there"
    prompt = f"""You are Fareeha's outbound agent. Write a 5-email sequence that
{assets.get('company')} would send to THIS SPECIFIC prospect. It must read like a sharp human
SDR who studied both companies, not a template.

SELLER'S REAL ASSETS (ground every claim here):
{json.dumps(assets, indent=2)}

THE PROSPECT:
{json.dumps(prospect, indent=2)}

First "about": 1-2 sentences on who this prospect is and why they fit, from their title and
company (only what is given or reliably known; no guessing dressed as fact).

The 5 emails, personalized to them:
1. HOOK: the pressure {first} personally carries in this role at their company, then the core value.
2. LEAD MAGNET: their single best real lead magnet (real name, url in "asset"). If none, the
   strongest proof point, asset null.
3. CASE STUDY: a REAL named case study with its concrete result, chosen for relevance to this
   prospect. Customer name(s) in "asset". Never fabricate.
4. PRODUCT / TRIAL: plain text, concrete, pointed at their situation. Trial url in "asset" if present.
5. BREAKUP: warm close, door open.

{VOICE}

Return ONLY JSON:
{{"about":"...","emails":[{{"n":1,"role":"hook","subject":"...","body":"Hi {first}, ...","asset":{{"label":"...","url":"..."}}|null}}, ...5 total]}}
"""
    return core.extract_json(core.llm(client, prompt, max_tokens=2600))

def build_kit(domain):
    domain = core.clean_domain(domain)
    slug = re.sub(r"[^a-z0-9]", "", domain.split(".")[0])
    site = core.scrape_site(domain)
    client = core.anthropic_client()
    assets = extract_assets(client, domain, site)
    market = find_prospects(assets, enrich=os.environ.get("APOLLO_ENRICH") == "1")

    # The per-prospect sequences are independent, so run them concurrently.
    # This keeps wall-clock roughly at one Claude call instead of five in a
    # row, which is what lets the whole request finish inside a serverless
    # time limit (e.g. Vercel's 60s cap). Output/order is unchanged.
    def one_kit(p):
        try:
            seq = write_prospect_sequence(client, assets, p)
        except Exception as e:
            seq = {"about": "", "emails": [], "error": str(e)}
        return {"prospect": p, "about": seq.get("about", ""),
                "emails": seq.get("emails", [])}

    prospects = market.get("prospects", [])
    if prospects:
        with ThreadPoolExecutor(max_workers=len(prospects)) as ex:
            prospect_kits = list(ex.map(one_kit, prospects))  # map preserves order
    else:
        prospect_kits = []

    kit_obj = {"domain": domain, "slug": slug, "assets": assets, "market": market,
               "prospect_kits": prospect_kits,
               "total_emails": sum(len(pk["emails"]) for pk in prospect_kits)}
    # Best-effort local persistence for the CLI. Serverless hosts (e.g. Vercel)
    # have a read-only filesystem, so skip quietly if we cannot write; the kit
    # is returned directly either way.
    try:
        out = pathlib.Path(__file__).resolve().parent / "output" / slug
        out.mkdir(parents=True, exist_ok=True)
        (out / "kit.json").write_text(json.dumps(kit_obj, indent=2), encoding="utf-8")
    except OSError:
        pass
    return kit_obj

if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "foreai.co"
    k = build_kit(d)
    print(f"{k['total_emails']} emails across {len(k['prospect_kits'])} prospects")
