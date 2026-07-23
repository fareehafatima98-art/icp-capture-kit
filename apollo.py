"""
Apollo REST client for the Capture Kit agent (v3).
- people_count: FREE search, now with location filters (person + employer HQ).
- enrich_people: PAID (1 credit per match), reveals full name + verified email.
"""
import os, json, urllib.request

BASE = "https://api.apollo.io/v1"

class Apollo:
    def __init__(self, api_key=None):
        self.key = api_key or os.environ.get("APOLLO_API_KEY", "")

    def _post(self, path, body):
        if not self.key:
            return {"_error": "no APOLLO_API_KEY"}
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

    def people_count(self, titles, employee_ranges=None, keyword_tags=None,
                     seniorities=None, person_locations=None,
                     organization_locations=None, per_page=8):
        body = {"person_titles": titles, "per_page": per_page, "page": 1}
        if employee_ranges:        body["organization_num_employees_ranges"] = employee_ranges
        if keyword_tags:           body["q_organization_keyword_tags"] = keyword_tags
        if seniorities:            body["person_seniorities"] = seniorities
        if person_locations:       body["person_locations"] = person_locations
        if organization_locations: body["organization_locations"] = organization_locations
        r = self._post("/mixed_people/search", body)
        total = (r.get("pagination") or {}).get("total_entries")
        sample = [{"id": p.get("id"),
                   "first_name": p.get("first_name"),
                   "title": p.get("title"),
                   "company": (p.get("organization") or {}).get("name"),
                   "linkedin_url": p.get("linkedin_url")}
                  for p in (r.get("people") or [])]
        return {"total": total, "sample": sample, "error": r.get("_error")}

    def enrich_people(self, ids):
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
