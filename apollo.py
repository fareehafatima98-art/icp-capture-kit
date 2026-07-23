"""
Thin Apollo REST client for the report engine.

Cost control (Apollo bills per call on some endpoints):
  - people_count()      -> /mixed_people/api_search  FREE (search, no enrichment)
  - company_count()     -> /mixed_companies/search   1 credit per call that returns >0
  - enrich_org()        -> /organizations/enrich     1 credit if found

The engine runs the FREE calls by default. The paid calls only fire when
spend=True is passed (wired to APOLLO_SPEND in the engine), so a self-serve
run never burns credits unless you opt in.
"""
import os, json, urllib.request, urllib.parse

BASE = "https://api.apollo.io/api/v1"

class Apollo:
    def __init__(self, api_key=None):
        self.key = api_key or os.environ.get("APOLLO_API_KEY", "")

    def _post(self, path, body):
        if not self.key:
            return {}
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            BASE + path, data=data, method="POST",
            headers={"Content-Type": "application/json",
                     "Cache-Control": "no-cache",
                     "X-Api-Key": self.key})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            return {"_error": str(e)}

    def _get(self, path, params):
        if not self.key:
            return {}
        url = BASE + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, method="GET",
            headers={"Cache-Control": "no-cache", "X-Api-Key": self.key})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            return {"_error": str(e)}

    # ---- FREE: how big is the buyer market, plus a small real sample --------
    def people_count(self, titles, employee_ranges=None, keyword_tags=None,
                     seniorities=None, per_page=5):
        body = {"person_titles": titles, "per_page": per_page, "page": 1}
        if employee_ranges: body["organization_num_employees_ranges"] = employee_ranges
        if keyword_tags:     body["q_organization_keyword_tags"] = keyword_tags
        if seniorities:      body["person_seniorities"] = seniorities
        # Public People Search API is /mixed_people/api_search. The bare
        # /mixed_people/search path is Apollo's internal UI route and returns
        # 403 for API keys. Requires a MASTER Apollo API key.
        r = self._post("/mixed_people/api_search", body)
        total = (r.get("pagination") or {}).get("total_entries")
        sample = [{"id": p.get("id"),
                   "first_name": p.get("first_name"),
                   "title": p.get("title"),
                   "company": (p.get("organization") or {}).get("name"),
                   "linkedin_url": p.get("linkedin_url")}
                  for p in (r.get("people") or [])]
        return {"total": total, "sample": sample, "error": r.get("_error")}

    # ---- PAID (1 credit each match): reveal real full name + verified email ----
    def enrich_people(self, ids):
        """Turn masked search results into real, sendable contacts.
        Uses /people/bulk_match. Costs Apollo credits, so only call when you mean it."""
        if not ids:
            return []
        body = {"details": [{"id": i} for i in ids if i],
                "reveal_personal_emails": False}
        r = self._post("/people/bulk_match", body)
        out = []
        for m in (r.get("matches") or []):
            if not m:
                continue
            out.append({
                "name": m.get("name") or " ".join(
                    x for x in [m.get("first_name"), m.get("last_name")] if x),
                "first_name": m.get("first_name"),
                "title": m.get("title"),
                "company": (m.get("organization") or {}).get("name"),
                "email": m.get("email"),
                "email_status": m.get("email_status"),
                "linkedin_url": m.get("linkedin_url"),
            })
        return out

    # ---- PAID (1 credit): live trigger list size --------------------------
    def company_count(self, job_titles, employee_ranges=None, keyword_tags=None,
                      posted_within_days=30):
        from datetime import date, timedelta
        body = {"q_organization_job_titles": job_titles, "per_page": 1, "page": 1}
        if employee_ranges: body["organization_num_employees_ranges"] = employee_ranges
        if keyword_tags:     body["q_organization_keyword_tags"] = keyword_tags
        if posted_within_days:
            since = (date.today() - timedelta(days=posted_within_days)).isoformat()
            body["organization_job_posted_at_range"] = {"min": since}
        r = self._post("/mixed_companies/search", body)
        total = (r.get("pagination") or {}).get("total_entries")
        return {"total": total, "error": r.get("_error")}

    # ---- PAID (1 credit if found): enrich the prospect's own company ------
    def enrich_org(self, domain):
        r = self._get("/organizations/enrich", {"domain": domain})
        org = r.get("organization") or {}
        if not org:
            return {"error": r.get("_error")}
        return {
            "name": org.get("name"),
            "employees": org.get("estimated_num_employees"),
            "industry": org.get("industry"),
            "founded_year": org.get("founded_year"),
            "total_funding": org.get("total_funding_printed"),
            "latest_funding_stage": org.get("latest_funding_stage"),
            "keywords": (org.get("keywords") or [])[:12],
        }
