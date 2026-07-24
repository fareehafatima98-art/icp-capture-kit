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
import os, re, json, sys, time, pathlib
from concurrent.futures import ThreadPoolExecutor
import scrape_llm as core
from apollo import Apollo

# Delay between each concurrent prospect-sequence start, to spread the burst
# across the API rate limit without serializing the calls (see build_kit).
STAGGER_SECONDS = 0.8

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
    return core.llm_json(client, prompt, max_tokens=1700)

# Title heuristics: prefer people who actually BUY (leaders/heads) over
# practitioners (e.g. a classroom teacher rather than a principal).
BUYER_WORDS = ("chief", "head", "director", "vp", "vice president", "principal", "president",
               "founder", "owner", "ceo", "cto", "coo", "cfo", "cmo", "superintendent", "dean",
               "partner", "lead", "manager", "coordinator", "deputy")
PRACTITIONER_WORDS = ("teacher", "engineer", "developer", "analyst", "specialist", "associate",
                      "assistant", "representative", "intern", "clerk", "tutor", "aide", "nurse")

def title_score(title):
    t = (title or "").lower()
    s = 0
    if any(w in t for w in BUYER_WORDS):
        s += 2
    if any(w in t for w in PRACTITIONER_WORDS):
        s -= 2
    if any(w in t for w in ("chief", "head", "principal", "director", "vice president",
                            "superintendent", "founder", "ceo", "cto", "president", "owner")):
        s += 1   # unambiguous leadership
    return s

def _loc_haystack(p):
    return " ".join(str(p.get(k) or "") for k in ("country", "state", "city", "org_country")).lower()

def loc_match(p, locs):
    """True if the prospect's person/org location mentions any target location."""
    hay = _loc_haystack(p)
    return any(str(l).strip().lower() in hay for l in (locs or []) if str(l).strip())

def dedupe_by_company(people):
    """One prospect per organization, keeping the highest-scoring (most buyer-like)
    title within each company. Order follows first appearance."""
    best, order = {}, []
    for p in people:
        k = (p.get("company") or "").strip().lower() or ("obj:" + str(id(p)))
        if k not in best:
            best[k] = p
            order.append(k)
        elif title_score(p.get("title")) > title_score(best[k].get("title")):
            best[k] = p
    return [best[k] for k in order]

def _enforce_locations(people, locs, top_n):
    """Require a location match when target_locations is set; relax to include
    non-matching prospects only if too few match to fill top_n."""
    if not locs:
        return people
    matching = [p for p in people if loc_match(p, locs)]
    if len(matching) >= top_n:
        return matching
    return matching + [p for p in people if not loc_match(p, locs)]

def find_prospects(assets, enrich=False, top_n=5):
    """Search -> one per company (buyer titles preferred) -> enforce target
    locations -> enrich up to 8 -> prefer prospects WITH verified emails ->
    never pitch the company's own named customers. Surfaces errors."""
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
        # Pull a wider net (25) so there's room to drop duplicate companies,
        # off-location people, and practitioners and still reach top_n.
        r = ap.people_count(titles, per_page=25, **a)
        err = r.get("error")
        if r.get("sample"):
            break
    sample = r.get("sample", [])

    # never pitch their own customers
    known = {c.strip().lower() for c in (assets.get("named_customers") or []) if c}
    def is_customer(p):
        co = (p.get("company") or "").strip().lower()
        return bool(co) and any(co in k or k in co for k in known)

    def refine(people):
        people = [p for p in people if not is_customer(p)]
        people = dedupe_by_company(people)              # one per organization
        people = _enforce_locations(people, locs, top_n)  # target locations first
        people.sort(key=lambda p: -title_score(p.get("title")))  # buyers first (stable)
        return people

    candidates = refine(sample)

    prospects = candidates
    if enrich and candidates:
        real = ap.enrich_people([p["id"] for p in candidates[:8] if p.get("id")])
        if real:
            # enrichment can reveal truer titles/companies/locations, so refine again
            real = refine(real)
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
2. LEAD MAGNET: their single best real lead magnet. If it has a real url, put it in "asset".
   If none, use the strongest proof point and set asset null.
3. CASE STUDY: a REAL named case study with its concrete result, chosen for relevance to this
   prospect. Name the customer in the body prose. Never fabricate.
4. PRODUCT / TRIAL: plain text, concrete, pointed at their situation.
5. BREAKUP: warm close, door open.

ASSET RULE (strict, prevents dead links): set "asset" ONLY when you have a real, non-empty URL
copied verbatim from the seller's assets above (a lead_magnets url, the free_trial_url, or a
real case-study page url that is actually present). Never invent a URL, never use "#", "<>", or
an empty string. If there is no real URL, set "asset" to null and refer to the lead magnet /
case study / trial BY NAME in the body prose instead. Most emails will have asset null.

{VOICE}

Return ONLY valid, parseable JSON, nothing before or after it. Do not use double-quote
characters inside any string value (use single quotes if you must quote something), so the
JSON never breaks.
{{"about":"...","emails":[{{"n":1,"role":"hook","subject":"...","body":"Hi {first}, ...","asset":{{"label":"...","url":"..."}}|null}}, ...5 total]}}
"""
    # 2600 is ample for a 5-email sequence (~950 tokens of content). It was briefly
    # 4000 "for headroom", but that let some sequences generate long enough to blow
    # the 60s serverless cap (504 FUNCTION_INVOCATION_TIMEOUT). Cap it so a single
    # /api/sequence call stays comfortably under 60s, even if the parse-retry fires.
    return core.llm_json(client, prompt, max_tokens=2600)

def slugify(domain):
    return re.sub(r"[^a-z0-9]", "", core.clean_domain(domain).split(".")[0])

def analyze(domain):
    """The fast half of a run: scrape the site, extract assets, and pull enriched
    prospects. No per-prospect Claude calls, so this stays well inside a 60s
    serverless cap. The slow half (one Claude call per prospect) is sequence_for,
    which the front-end fans out across separate /api/sequence requests so no
    single call approaches the timeout."""
    domain = core.clean_domain(domain)
    site = core.scrape_site(domain)
    client = core.anthropic_client()
    assets = extract_assets(client, domain, site)
    market = find_prospects(assets, enrich=os.environ.get("APOLLO_ENRICH") == "1")
    return {"domain": domain, "slug": slugify(domain), "assets": assets, "market": market}

def sequence_for(assets, prospect):
    """One prospect's 5-email sequence, as a prospect-kit. Never raises for a
    sequence failure: the reason is captured on the kit (error) so a short run
    is debuggable and the other prospects still render."""
    client = core.anthropic_client()
    err = None
    try:
        seq = write_prospect_sequence(client, assets, prospect)
        err = seq.get("error")
    except Exception as e:
        seq, err = {"about": "", "emails": []}, str(e)
    pk = {"prospect": prospect, "about": seq.get("about", ""),
          "emails": seq.get("emails", [])}
    if err:
        pk["error"] = err
    return pk

def build_kit(domain):
    """Whole-run convenience for the CLI. The hosted API does NOT use this (it
    would run all five sequences in one request and risk the 60s cap); it splits
    the work across /api/analyze + /api/sequence + /api/share instead."""
    base = analyze(domain)
    assets, prospects = base["assets"], base["market"].get("prospects", [])

    # Independent sequences, run concurrently with staggered starts so the burst
    # does not trip the API rate limit (see STAGGER_SECONDS).
    def one_kit(i, p):
        time.sleep(i * STAGGER_SECONDS)
        return sequence_for(assets, p)

    if prospects:
        with ThreadPoolExecutor(max_workers=len(prospects)) as ex:
            prospect_kits = list(ex.map(one_kit, range(len(prospects)), prospects))
    else:
        prospect_kits = []

    kit_obj = {**base, "prospect_kits": prospect_kits,
               "total_emails": sum(len(pk["emails"]) for pk in prospect_kits)}
    # Best-effort local persistence for the CLI. Serverless hosts (e.g. Vercel)
    # have a read-only filesystem, so skip quietly if we cannot write.
    try:
        out = pathlib.Path(__file__).resolve().parent / "output" / base["slug"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "kit.json").write_text(json.dumps(kit_obj, indent=2), encoding="utf-8")
    except OSError:
        pass
    return kit_obj

if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "foreai.co"
    k = build_kit(d)
    print(f"{k['total_emails']} emails across {len(k['prospect_kits'])} prospects")
