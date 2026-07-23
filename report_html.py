"""
Renders a kit as a single self-contained shareable HTML page:
prospect tabs, copy-paste emails (with real addresses when enriched),
inline Calendly booking (no redirect), video slot, contact fallback.
Used for the stored share page at the blob URL.
"""
import html as H

CALENDLY = "https://calendly.com/hifareeha/discovery-meeting-with-fareeha"
CONTACT_LINE = "Or just reply to my email, hello@fareehafatima.com, and we'll find a time."
VIDEO_EMBED = ""   # paste a Loom/YouTube embed URL when the video is ready

CSS = """
:root{--ink:#12100E;--ink2:#1B1815;--card:#1E1A16;--line:#332C25;--cream:#FAF7F2;
--muted:#A79C90;--accent:#E8531A;--accent2:#FF7A45;--ok:#4ADE80}
*{box-sizing:border-box}
body{margin:0;background:var(--ink);color:var(--cream);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif;line-height:1.55}
.wrap{max-width:820px;margin:0 auto;padding:44px 22px 90px}
.kicker{color:var(--accent);font-weight:700;letter-spacing:.14em;text-transform:uppercase;font-size:12px}
h1{font-size:clamp(24px,4vw,34px);line-height:1.12;margin:.35em 0 .5em;font-weight:800}
.lead{background:linear-gradient(145deg,#241d17,#1a1613);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:16px;padding:20px 22px;margin:8px 0 22px}
.lead b{color:var(--accent)}
.h2{font-size:13px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:28px 0 12px}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.tab{background:var(--ink2);border:1px solid var(--line);color:var(--muted);border-radius:999px;padding:8px 16px;font-size:14px;cursor:pointer}
.tab.on{border-color:var(--accent);color:var(--cream);background:#241d17}
.pk{display:none}.pk.on{display:block}
.about{background:var(--ink2);border:1px solid var(--line);border-radius:12px;padding:13px 16px;margin-bottom:14px;font-size:14px;color:#DBD2C7}
.about b{color:var(--cream)}.about .em{color:var(--ok)}
.email{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:14px;position:relative}
.email .tag{color:var(--accent);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em}
.email .subj{font-weight:650;margin:6px 0 8px}.email .body{color:#DBD2C7;font-size:14.5px;white-space:pre-wrap}
.email .asset{display:inline-block;margin-top:10px;color:var(--accent);font-size:13px;text-decoration:none;border:1px solid var(--line);border-radius:8px;padding:5px 10px}
.copy{position:absolute;top:14px;right:14px;background:var(--ink2);border:1px solid var(--line);color:var(--muted);font-size:12px;border-radius:8px;padding:5px 10px;cursor:pointer}
.copy:hover{color:var(--cream);border-color:var(--accent)}
.cta{margin-top:28px;background:linear-gradient(145deg,#2a2017,#1c1713);border:1px solid var(--line);border-radius:16px;padding:24px}
.cta h3{margin:0 0 .3em;font-size:20px;text-align:center}.cta p{color:#DBD2C7;text-align:center;margin:.2em 0 14px}
.vid{margin:0 0 18px;aspect-ratio:16/9;background:#000;border:1px solid var(--line);border-radius:12px;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:13px;overflow:hidden}
.vid iframe{width:100%;height:100%;border:0}
.contact{color:var(--muted);font-size:13px;text-align:center;margin-top:10px}
.foot{color:var(--muted);font-size:12px;margin-top:36px;text-align:center}
"""

JS = """
function pick(i){document.querySelectorAll('.tab').forEach((t,j)=>t.classList.toggle('on',i===j));
document.querySelectorAll('.pk').forEach((p,j)=>p.classList.toggle('on',i===j));}
function cp(b){const e=b.parentElement;const t=e.querySelector('.subj').textContent+'\\n\\n'+e.querySelector('.body').textContent;
navigator.clipboard.writeText(t).then(()=>{b.textContent='Copied';setTimeout(()=>b.textContent='Copy',1500);});}
"""

def esc(s):
    return H.escape(str(s if s is not None else ""))

def render(kit):
    a = kit.get("assets") or {}
    m = kit.get("market") or {}
    pks = kit.get("prospect_kits") or []
    company = a.get("company") or kit.get("domain", "")

    lead = f"<b>{esc(company)}</b> — {esc(a.get('product_summary',''))}"
    if m.get("market_size"):
        lead += f" <b>({m['market_size']:,} buyers in range)</b>"

    tabs, panes = [], []
    for i, pk in enumerate(pks):
        p = pk.get("prospect") or {}
        nm = p.get("name") or p.get("first_name") or f"#{i+1}"
        tabs.append(f"<button class='tab{' on' if i==0 else ''}' onclick='pick({i})'>{esc(nm)} · {esc(p.get('company',''))}</button>")
        em = f" · <span class='em'>{esc(p['email'])}</span>" if p.get("email") else \
             " · <span style='color:var(--muted)'>no verified email found, LinkedIn instead</span>"
        li = f" · <a style='color:var(--accent)' href='{esc(p['linkedin_url'])}'>LinkedIn</a>" if p.get("linkedin_url") else ""
        emails = ""
        for e in pk.get("emails", []):
            asset = ""
            if e.get("asset"):
                asset = f"<a class='asset' href='{esc(e['asset'].get('url','#'))}' target='_blank'>{esc(e['asset'].get('label','from your site'))}</a>"
            emails += (f"<div class='email'><button class='copy' onclick='cp(this)'>Copy</button>"
                       f"<div class='tag'>Email {esc(e.get('n'))} · {esc(e.get('role',''))}</div>"
                       f"<div class='subj'>{esc(e.get('subject',''))}</div>"
                       f"<div class='body'>{esc(e.get('body',''))}</div>{asset}</div>")
        panes.append(f"<div class='pk{' on' if i==0 else ''}'><div class='about'><b>{esc(nm)}</b> — "
                     f"{esc(p.get('title',''))}{', '+esc(p.get('company','')) if p.get('company') else ''}{em}{li}"
                     f"<br>{esc(pk.get('about',''))}</div>{emails}</div>")

    # Render the video only when VIDEO_EMBED is set; nothing (no placeholder) otherwise.
    video = (f"<div class='vid'><iframe src='{esc(VIDEO_EMBED)}' allowfullscreen></iframe></div>"
             if VIDEO_EMBED else "")

    total = kit.get("total_emails", sum(len(pk.get("emails", [])) for pk in pks))
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ICP Capture Kit — {esc(company)}</title><style>{CSS}</style></head><body>
<div class="wrap">
  <div class="kicker">ICP Capture Kit</div>
  <h1>{esc(company)} · your first {len(pks)} buyers, and the {total} emails to land them</h1>
  <div class="lead">{lead}</div>
  <div class="h2">Your first {len(pks)}, each with their own sequence</div>
  <div class="tabs">{''.join(tabs)}</div>
  {''.join(panes)}
  <div class="cta">
    <h3>Want this built and run for you every week?</h3>
    {video}
    <p>Pick a time right here, no redirects.</p>
    <div class="calendly-inline-widget" data-url="{CALENDLY}?hide_gdpr_banner=1"
         style="min-width:320px;height:660px;"></div>
    <script src="https://assets.calendly.com/assets/external/widget.js" async></script>
    <div class="contact">{esc(CONTACT_LINE)}</div>
  </div>
  <div class="foot">Generated from {esc(kit.get('domain',''))} + live prospect data · by Fareeha's outbound agent</div>
</div>
<script>{JS}</script>
</body></html>"""
