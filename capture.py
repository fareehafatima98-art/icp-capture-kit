#!/usr/bin/env python3
"""
ICP Capture Kit engine v3.

v3 upgrades over v2:
  - Emails are fuller and more specific (v1-grade): 60-90 words, each must carry a
    concrete detail from the company's real assets. Generic filler is rejected in-prompt.
  - Prospect selection prefers people with verified emails: enrich up to 8, keep the 5
    with emails first, so kits are ready-to-send.
  - Filters out the company's own named customers (never pitch their customers back).
  - Truth rules: a brand only counts as a customer when the site explicitly presents it as one
    (CUSTOMER_EVIDENCE_RULE), and emails may state only the bare fact that a named_customer is
    a customer unless case_studies gives a real pairing (CUSTOMER CLAIM RULE).
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

# A brand appearing anywhere on a site is NOT evidence it is a customer. Sites routinely
# show third-party brands inside product demos, sample test cases, screenshots and
# illustrations (e.g. foreai.co demos "Apply for CITI card" as a test case; Citi is not a
# customer). Claiming those as customers puts a fabricated claim in a cold email, so the
# bar is explicit presentation as a customer.
CUSTOMER_EVIDENCE_RULE = """CUSTOMER EVIDENCE RULE (strict, do not bend):
Only list a company under named_customers, case_studies or proof_points when the copy
EXPLICITLY presents it as a customer of this company: a "trusted by" / "our customers" /
logo-wall label, a testimonial or quote, or a named case study or success story.
EXCLUDE any brand that appears only inside demo or product content, sample or example
test cases, interactive "see it in action" walkthroughs, screenshots, integration lists,
supported-platform lists, or illustrations. Those brands are subject matter, not customers.
If you are not certain a brand is presented as a customer, leave it out."""

def extract_assets(client, domain, site_text):
    prompt = f"""You are a sharp B2B go-to-market analyst reading {domain}. From the scraped
copy below, extract REAL, specific assets. Do not invent. If something isn't present, return an
empty list for it, do not fabricate.

{CUSTOMER_EVIDENCE_RULE}

Return ONLY JSON:
{{
 "company": "display name",
 "product_summary": "2 plain sentences on what it does",
 "icp_personas": ["5-7 exact buyer titles who buy this"],
 "buyer_titles": ["4-6 job titles to search for prospects"],
 "employee_ranges": ["Apollo size buckets for their ICP, from 1,10 11,50 51,200 201,500 501,1000 1001,5000"],
 "keyword_tags": ["3-6 industry/segment tags for their ICP's employers"],
 "target_locations": ["countries/regions their site implies they sell into, e.g. Australia; empty if global"],
 "named_customers": ["only companies the copy explicitly presents as customers (see rule above)"],
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
- Subjects: concrete and curiosity-pulling, 5-9 words, no clickbait.
- Write the about text, every subject and every body in ENGLISH, even when the prospect's name
  or company is written in another script. (Without this, a prospect whose company carries e.g.
  Hebrew or Japanese text made the model answer in that language: far more tokens per character,
  slow enough to blow the 60s serverless cap, so that prospect's tab came back empty.)"""

# JSON schema for structured outputs: forces the model to return valid JSON in
# exactly this shape, so a stray unescaped quote can't break the sequence. Every
# object sets additionalProperties:false with an explicit required list (both
# required by structured outputs); asset is an object OR null via anyOf.
SEQUENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "about": {"type": "string"},
        "emails": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "n": {"type": "integer"},
                    "role": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "asset": {
                        "anyOf": [
                            {"type": "object", "additionalProperties": False,
                             "properties": {"label": {"type": "string"}, "url": {"type": "string"}},
                             "required": ["label", "url"]},
                            {"type": "null"},
                        ]
                    },
                },
                "required": ["n", "role", "subject", "body", "asset"],
            },
        },
    },
    "required": ["about", "emails"],
}

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
3. CASE STUDY: a REAL named case study from case_studies, with its concrete result, chosen for
   relevance to this prospect. Name the customer in the body prose. Never fabricate. If
   case_studies is empty, do NOT invent one and do not turn a named_customer into a case
   study: use the hard aggregate proof from proof_points instead (real numbers, security
   posture, deployment options) and keep the email concrete that way.
4. PRODUCT / TRIAL: plain text, concrete, pointed at their situation.
5. BREAKUP: warm close, door open.

CUSTOMER CLAIM RULE (strict, prevents fabricated claims): the ONLY companies you may describe
as customers, users, or clients of {assets.get('company')} are the ones listed in
named_customers above. Never call any other company a customer, and never imply one, however
plausible it looks. Any brand you saw elsewhere (in demos, examples, test cases, screenshots)
is off limits. About a named_customer you may state ONLY the bare fact that they are a
customer. Unless that exact pairing appears in case_studies, you may not say or imply, in a
subject line or a body, what they achieved, how or why they use it, what it replaced for them,
or any metric, quote or motivation of theirs. Numbers in proof_points are aggregate product
results, never one customer's result. So "Sixt cut testing time without adding headcount",
"UBS runs on fore ai for exactly that reason", and "How UBS handles QA at scale" are all
fabrications; "companies like UBS and Sixt run on it" is fine. When case_studies is empty:
do not put a customer's name in ANY subject line (a subject that promises their story cannot
be honoured by the body), make email 3's case from aggregate proof_points plus this prospect's
own situation, and never announce that no case study exists.

ASSET RULE (strict, prevents dead links): set "asset" ONLY when you have a real, non-empty URL
copied verbatim from the seller's assets above (a lead_magnets url, the free_trial_url, or a
real case-study page url that is actually present). Never invent a URL, never use "#", "<>", or
an empty string. If there is no real URL, set "asset" to null and refer to the lead magnet /
case study / trial BY NAME in the body prose instead. Most emails will have asset null.

QUOTE RULE: proof_points may contain verbatim testimonial quotes, often anonymous and often
hedged. Keep the hedge exactly as strong as the source, and on the same clause: if the quote is
"this might have saved us on a job where we missed 200 doors", then they DID miss the doors and
the product MIGHT have caught it, so "they might have missed 200 doors" and "it would have saved
them" are both wrong. Never carry a quote's first person into your own voice: "an estimator told
us THEY missed 200 doors", never "we missed 200 doors", which reads as if the sender made the
mistake. Attribute anonymous quotes by role and company type, never invent a company name for
one, and paraphrase in clean grammatical sentences.

STATISTICS RULE: the only numbers, rates and aggregates you may state are the ones in
proof_points or case_studies, worded as strongly as they appear there and no stronger. Never
invent a statistic and never invent a source for one: no "our data shows", no "our aggregate
data", no "most customers", no "on average", no made-up percentages. If you want to generalise
beyond a single quote, say plainly that it is what users tell us, without a fabricated number.

{VOICE}

Return ONLY valid, parseable JSON, nothing before or after it. Do not use double-quote
characters inside any string value (use single quotes if you must quote something), so the
JSON never breaks.
{{"about":"...","emails":[{{"n":1,"role":"hook","subject":"...","body":"Hi {first}, ...","asset":{{"label":"...","url":"..."}}|null}}, ...5 total]}}
"""
    # 2600 is ample for a 5-email sequence (~950 tokens of content). It was briefly
    # 4000 "for headroom", but that let some sequences generate long enough to blow
    # the 60s serverless cap (504 FUNCTION_INVOCATION_TIMEOUT). Cap it so a single
    # /api/sequence call stays comfortably under 60s.
    # SEQUENCE_SCHEMA makes the API return guaranteed-valid JSON (structured
    # outputs), which is what fixed sequences intermittently failing to parse.
    return core.llm_json(client, prompt, max_tokens=2600, schema=SEQUENCE_SCHEMA)

def slugify(domain):
    return re.sub(r"[^a-z0-9]", "", core.clean_domain(domain).split(".")[0])

class SiteUnreadable(Exception):
    """The site produced no usable brief, so the run must stop before it spends
    Apollo credits and writes emails from nothing."""

def has_brief(assets):
    """True when the extracted assets are a real brief: a company name AND a
    product summary. Everything downstream (Apollo titles/tags, every email)
    is grounded in these, so empty means garbage in."""
    a = assets or {}
    return bool(str(a.get("company") or "").strip()
                and str(a.get("product_summary") or "").strip())

def analyze(domain):
    """The fast half of a run: scrape the site, extract assets, and pull enriched
    prospects. No per-prospect Claude calls, so this stays well inside a 60s
    serverless cap. The slow half (one Claude call per prospect) is sequence_for,
    which the front-end fans out across separate /api/sequence requests so no
    single call approaches the timeout.

    Raises SiteUnreadable rather than proceeding on an empty brief. fresco-ai.com
    (client-rendered, so the scrape came back empty) previously ran all the way
    through and produced a kit that searched Apollo with no ICP at all: Bill Gates,
    Larry Fink and Satya Nadella as a construction startup's first buyers, with
    sequences that invented the positioning. An unreadable site must fail loudly."""
    domain = core.clean_domain(domain)
    site = core.scrape_site(domain)
    if len(site) < core.MIN_SITE_TEXT:
        raise SiteUnreadable(
            f"Could not read this site: {domain} returned "
            f"{len(site)} characters of readable copy (need "
            f"{core.MIN_SITE_TEXT}). It may be blocking us or rendering entirely "
            "in the browser. Nothing was searched or written.")
    client = core.anthropic_client()
    assets = extract_assets(client, domain, site)
    if not has_brief(assets):
        raise SiteUnreadable(
            f"Could not read this site: {domain} gave no usable company name or "
            "product summary, so there is no ICP to search on. Nothing was "
            "searched or written.")
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
