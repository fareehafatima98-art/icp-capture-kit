#!/usr/bin/env python3
"""
ICP Capture Kit engine v2 (the agent). Self-contained.

  python3 capture.py <domain>

v2 upgrades:
  - Prospect search has progressive fallback (tight filters -> looser) and surfaces
    errors instead of silently returning an empty "first five".
  - PER-PROSPECT SEQUENCES: each of the 5 real prospects gets their own 5-email
    sequence (25 emails total), personalized with a short researched line about
    that person's company/role. No invented facts.

Output: output/<slug>/kit.json.
Requires ANTHROPIC_API_KEY and APOLLO_API_KEY. Enrichment OFF by default
(first names only, no credits); APOLLO_ENRICH=1 to reveal full names + emails.
"""
import os, re, json, sys, pathlib
from concurrent.futures import ThreadPoolExecutor
import scrape_llm as core
from apollo import Apollo

# ---------------------------------------------------------------------------
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
 "keyword_tags": ["3-6 industry/segment tags for their ICP's employers, e.g. SaaS, Insurance, Education"],
 "case_studies": [{{"customer":"named customer","result":"the concrete result or what they did"}}],
 "lead_magnets": [{{"name":"the free tool/calculator/guide","url":"its url if shown"}}],
 "free_trial_url": "url to try/sign up if present, else empty",
 "proof_points": ["named logos or hard results found in the copy"]
}}

SCRAPED COPY:
{site_text[:16000]}
"""
    return core.extract_json(core.llm(client, prompt, max_tokens=1600))

# ---------------------------------------------------------------------------
def find_prospects(assets, enrich=False, top_n=5):   # default OFF: first names only, no credits
    """Progressive fallback: full filters -> drop keyword tags -> drop size ranges.
    Niche ICPs (schools, clinics) often match zero on tight filters; better to return
    real people than an empty list. Surfaces errors instead of failing silently."""
    if not os.environ.get("APOLLO_API_KEY"):
        return {"market_size": None, "prospects": [], "enriched": False,
                "error": "APOLLO_API_KEY is not set on the server"}
    ap = Apollo()
    titles = assets.get("buyer_titles") or assets.get("icp_personas") or []
    attempts = [
        dict(employee_ranges=assets.get("employee_ranges"), keyword_tags=assets.get("keyword_tags")),
        dict(employee_ranges=assets.get("employee_ranges"), keyword_tags=None),
        dict(employee_ranges=None, keyword_tags=None),
    ]
    r, err = {}, None
    for a in attempts:
        r = ap.people_count(titles, per_page=max(top_n, 8), **a)
        err = r.get("error")
        if r.get("sample"):
            break
    sample = r.get("sample", [])
    prospects = sample
    if enrich and sample:
        real = ap.enrich_people([p["id"] for p in sample[:top_n] if p.get("id")])
        if real:
            prospects = real
    return {"market_size": r.get("total"), "prospects": prospects[:top_n],
            "enriched": bool(enrich), "error": err}

# ---------------------------------------------------------------------------
VOICE = """VOICE: warm, human, specific. No em dashes. No exclamation marks. No jargon
(avoid self-healing, end-to-end, combinatorial, robust, leverage as a verb). Each body
40-60 words. Bodies open with "Hi {first}," using the prospect's REAL first name. One honest
human nod to what this person's role actually feels like. Never invent facts about the person
or their company; if unsure, stay role-level."""

def write_prospect_sequence(client, assets, prospect):
    """One tailored 5-email sequence for ONE real prospect."""
    first = prospect.get("first_name") or "there"
    prompt = f"""You are Fareeha's outbound agent. Write a 5-email sequence that
{assets.get('company')} would send to THIS SPECIFIC prospect. Personalize to their company and
role using only what is given or safely known; do not invent facts.

SELLER'S REAL ASSETS (ground every claim here):
{json.dumps(assets, indent=2)}

THE PROSPECT:
{json.dumps(prospect, indent=2)}

First, write "about": 1-2 sentences on who this prospect is and why they fit, based on their
title and company (what that company does, if you reliably know it; otherwise what their role
implies). Honest, useful, no guessing dressed as fact.

Then the 5 emails, personalized to them, in order:
1. HOOK: the pressure {first} personally carries in this role at their company, then the core value.
2. LEAD MAGNET: the seller's single best real lead magnet (real name, url in "asset"). If none,
   strongest proof point, asset null.
3. CASE STUDY: a REAL named case study from case_studies with the concrete result, chosen for its
   relevance to this prospect. Customer name(s) in "asset". If none exist, use proof_points honestly.
4. PRODUCT / TRIAL: plain text, concrete, pointed at their situation. Trial url in "asset" if present.
5. BREAKUP: warm close, door open.

{VOICE}

Return ONLY JSON:
{{"about":"...","emails":[{{"n":1,"role":"hook","subject":"...","body":"Hi {first}, ...","asset":{{"label":"...","url":"..."}}|null}}, ...5 total]}}
"""
    return core.extract_json(core.llm(client, prompt, max_tokens=2200))

# ---------------------------------------------------------------------------
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
    print("wrote output/%s/kit.json" % k["slug"])
