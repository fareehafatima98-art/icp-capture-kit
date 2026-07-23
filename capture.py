#!/usr/bin/env python3
"""
ICP Capture Kit engine (the agent). Self-contained.

  python3 capture.py <domain>

Given a domain, it produces a hyper-specific, ready-to-send outbound kit for THAT company to
send to ITS buyers:
  1. Reads the site broadly (case-study / customer / resources / pricing pages).
  2. Uses Claude to extract REAL assets, not placeholders: product, true ICP, best named case
     study, and the actual lead magnet(s) / free tool.
  3. Pulls real named prospects in that ICP from Apollo (live).
  4. Writes a 5-email sequence that USES the real case study, lead magnet, and free trial.

Output: output/<slug>/kit.json  (feeds the page).
Requires ANTHROPIC_API_KEY and APOLLO_API_KEY. Prospect enrichment is OFF by default
(first names only, no credits); set APOLLO_ENRICH=1 to reveal full names + emails.
"""
import os, re, json, sys, pathlib
import scrape_llm as core            # self-contained scrape + LLM helpers
from apollo import Apollo

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
 "keyword_tags": ["3-6 industry/segment tags for their ICP's employers, e.g. SaaS, Insurance"],
 "case_studies": [{{"customer":"named customer","result":"the concrete result or what they did"}}],
 "lead_magnets": [{{"name":"the free tool/calculator/guide","url":"its url if shown"}}],
 "free_trial_url": "url to try/sign up if present, else empty",
 "proof_points": ["named logos or hard results found in the copy"]
}}

SCRAPED COPY:
{site_text[:16000]}
"""
    return core.extract_json(core.llm(client, prompt, max_tokens=1600))

def find_prospects(assets, enrich=False, top_n=5):   # default OFF: first names only, no credits
    ap = Apollo()
    titles = assets.get("buyer_titles") or assets.get("icp_personas") or []
    r = ap.people_count(titles,
                        employee_ranges=assets.get("employee_ranges"),
                        keyword_tags=assets.get("keyword_tags"),
                        per_page=max(top_n, 8))
    sample = r.get("sample", [])
    prospects = sample
    if enrich and sample:
        real = ap.enrich_people([p["id"] for p in sample[:top_n] if p.get("id")])
        if real:
            prospects = real
    return {"market_size": r.get("total"), "prospects": prospects[:top_n], "enriched": bool(enrich)}

def write_sequence(client, assets, market):
    prompt = f"""You are Fareeha's outbound agent. Write a 5-email sequence that {assets.get('company')}
would send to ITS buyers, using the REAL assets below. This must be sendable, not generic.

REAL ASSETS:
{json.dumps(assets, indent=2)}

SAMPLE REAL PROSPECTS (their ICP):
{json.dumps(market.get('prospects', []), indent=2)}

The 5 emails, in order and by role:
1. HOOK: open with the pressure this buyer personally carries, then the core value.
2. LEAD MAGNET: lead with their single best real lead magnet (use its real name; include the url in
   an "asset" field). If none, use their strongest proof point and set asset null.
3. CASE STUDY: use a REAL named case study from case_studies (name the customer and result). Put the
   customer name(s) in "asset". If none exist, use proof_points honestly, no fabrication.
4. PRODUCT / TRIAL: plain text. Point to the real free trial or show what the product does. Put the
   trial url in "asset" if present.
5. BREAKUP: warm close, door open.

VOICE: warm, human, specific. No em dashes. No exclamation marks. No jargon (avoid self-healing,
end-to-end, combinatorial, robust, leverage). Each body 40-60 words. Every subject starts with {{first_name}}.
Include one honest human nod to the recipient's role. Bodies open with "Hi {{first_name}},".

Return ONLY a JSON array of 5 objects:
{{"n":1,"role":"hook","subject":"{{first_name}} ...","body":"Hi {{first_name}}, ...","asset":{{"label":"Pulled from your site: ...","url":"..."}}|null}}
"""
    text = core.llm(client, prompt, max_tokens=2600)
    m = re.search(r"\[.*\]", text, re.S)
    return json.loads(m.group(0)) if m else []

def build_kit(domain):
    domain = core.clean_domain(domain)
    slug = re.sub(r"[^a-z0-9]", "", domain.split(".")[0])
    site = core.scrape_site(domain)
    client = core.anthropic_client()
    assets = extract_assets(client, domain, site)
    market = find_prospects(assets, enrich=os.environ.get("APOLLO_ENRICH") == "1")
    sequence = write_sequence(client, assets, market)
    kit_obj = {"domain": domain, "slug": slug, "assets": assets,
               "market": market, "sequence": sequence}
    out = pathlib.Path(__file__).resolve().parent / "output" / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / "kit.json").write_text(json.dumps(kit_obj, indent=2), encoding="utf-8")
    return kit_obj

if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "foreai.co"
    k = build_kit(d)
    print(json.dumps(k, indent=2)[:2000])
    print("\n... wrote output/%s/kit.json" % k["slug"])
