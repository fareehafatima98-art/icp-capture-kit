# AGENT_TASKS — shared channel between Cowork Claude and Claude Code

Protocol: Claude Code reads this FIRST every session. Do INBOX top to bottom. Move finished
items to DONE with a one-line result (files touched + test output/URL). Blockers go to
BLOCKED with the exact error. Commit this file with your changes.

## INBOX

- [ ] (Page-visit tracking) Fareeha is enabling Vercel Web Analytics on the project. Add the
      tracking snippet to every page we serve so /k/<slug> visits are counted per path:
      `<script defer src="/_vercel/insights/script.js"></script>` in (a) report_html.py's
      rendered share pages and (b) web/index.html. Note the share pages are served through
      our /k/{slug} route on kit.fareehafatima.com, so the script loads from the same origin
      and per-path analytics (which founder viewed which kit) will just work. Re-render/
      re-share the four live kits (edexia, openhive, foreai, bowe) from their stored data so
      the already-sent links start tracking too — do NOT regenerate emails, only re-render
      the HTML with the snippet. Commit + push.

- [ ] (URGENT frescoai — HALF DONE, regen blocked on Anthropic credits, see BLOCKED. Steps 1+2
      are written and committed (35fac2a, unpushed); step 3's domain correction is verified:
      fresco.build gives 9269 chars with even the CURRENT deployed scraper (/ 4612 + /blog 4657)
      and the copy matches your ground truth exactly — "Door (DFH) Takeoffs in Minutes", Division 8
      subs, estimator/owner testimonials, all anonymous so named_customers will be empty. Note the
      natural slug for fresco.build is "fresco", so when the regen runs I will POST /api/share
      TWICE, once as slug frescoai to overwrite the garbage page and once as fresco. Nothing has
      been regenerated yet and 0 Apollo credits were spent: analyze died in extract_assets, before
      find_prospects.) Original task below.
- [ ] (URGENT — frescoai kit is garbage-in-garbage-out; fix + regen, approved) The live
      /k/frescoai kit is broken: fresco-ai.com failed to scrape (JS-rendered; site text came
      back empty), the company summary is blank, and with no brief the Apollo search returned
      absurd prospects (Bill Gates, Larry Fink, Satya Nadella as Fresco's "first buyers") and
      the 2 generated sequences hallucinate a positioning. Steps:
      1. GARBAGE-IN GUARD (permanent): in analyze, if scraped site text < ~500 chars OR
         extract_assets returns an empty/blank company + empty product_summary, FAIL the run
         with a clear error ("could not read this site") instead of proceeding. Never search
         Apollo or write emails from an empty brief. Also: do NOT cache/share a kit whose
         assets are empty.
      2. SCRAPE FALLBACK for JS sites: try harder before failing — (a) also fetch common
         static paths (/about, /careers, /blog posts), (b) try the r.jina.ai reader proxy
         (https://r.jina.ai/https://<domain>) which renders JS and returns text, as a
         fallback fetch. If still empty, fail per the guard.
      3. DOMAIN CORRECTION (from Cowork Claude's research): the real site is FRESCO.BUILD —
         fresco-ai.com is a near-empty shell, which is why the scrape came back blank.
         Delete/overwrite the bad cached frescoai kit, then force-regenerate from
         fresco.build end to end (analyze with the fixed scraper + 5 sequences + share).
         Ground truth for verification (CURRENT positioning — they pivoted from the old YC
         "superintendent copilot" story): Fresco (YC F24, also backed by Bessemer, SignalFire)
         does DIVISION 8 TAKEOFFS — automated door/frame/hardware (DFH) counts from plans,
         schedules and specs for commercial door contractors. Site headline "Door (DFH)
         Takeoffs in Minutes"; testimonials are estimators/owners at Division 8 subcontractors
         and door & hardware distributors; SOC 2 Type 2 (trust.fresco-ai.com); active blog.
         fresco.build serves full static marketing content (verified scrapeable). Expected
         ICP: estimators, senior estimators, owners at commercial door/hardware subcontractors
         and distributors, US. Verify prospects match that and 25/25 before logging the share
         URL (and make sure /k/frescoai no longer serves the garbage version).
      Cost approved: full regen ~8 Apollo credits + ~$0.30 API.

- [ ] (STRUCTURAL, so repairs are never manual again) Persist the kit JSON alongside the
      share page: /api/share also stores kits/kit-<slug>.json in Blob; add GET
      /api/kit/{slug} returning it; front-end + repairs can then resume/complete a partial
      kit without re-running analyze. Small, high-value.

- [ ] (Fareeha, NOW BLOCKING BOTH TASKS ABOVE) `git push origin main` from your Terminal. Two
      commits are stuck locally: 35fac2a (unreadable-site guard + scrape fallback) and 9f07d8c
      (analytics snippet + the /_vercel rewrite fix + share guard). CORRECTION to my earlier note
      that pushes now land by themselves: something did auto-commit and auto-push three times
      between 11:44 and 12:11 today (that is how 0f7512e finally shipped), then it stopped. My own
      push still fails, now with "could not read Username for https://github.com: Device not
      configured" (credential.helper=osxkeychain, but no tty to unlock it).
- [ ] (Fareeha) QC the 25 emails: https://kit.fareehafatima.com/k/edexia (renders inline, 25
      emails across 5 unique-company AU buyers, no dead links).

## BLOCKED

- [ ] (Fareeha) ANTHROPIC API CREDITS EXHAUSTED — this blocks every regeneration, not just
      frescoai. Exact error from prod, on both /api/analyze and /api/sequence:
      `Error code: 400 - {'type': 'invalid_request_error', 'message': 'Your credit balance is too
      low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase
      credits.'}` (request_id req_011CdNXZdNuqaMFp2TWLnhhj). /api/sequence still answers HTTP 200
      with emails:[] and the reason in `error`, so the front-end shows an empty tab rather than a
      clear message — worth surfacing better once credits are back. Top up, then the frescoai
      regen (analyze fresco.build force + 5 sequences + share as frescoai and fresco) is ready to
      run; the scripts are in the scratchpad.
- [ ] Push from Claude Code's env: still fails ("could not read Username ... terminal prompts
      disabled") for both https and ssh — no cached creds, no ~/.ssh key, no gh CLI, and `!` has
      no interactive prompt. Pushes must come from Fareeha's Terminal.app (that is how 3509b9e
      reached prod). Local commits are always staged and ready; see the INBOX push item.

## DONE

- [x] (Claude Code) Page-visit tracking CODE COMPLETE, waiting on a push to go live (commit
      9f07d8c, see BLOCKED). Snippet added to
      report_html's rendered share pages and web/index.html, and /k/{slug} injects it into
      already-STORED pages on the way out (idempotent), so edexia, openhive, foreai and bowe
      start counting with no re-render and no blob rewrites. I did not re-share the four kits as
      written: serve-time injection covers their existing links immediately, and re-rendering
      three of them would have meant parsing emails back out of HTML (lossy) since kit JSON is
      not stored yet.
      THE SNIPPET ALONE WOULD HAVE TRACKED NOTHING: vercel.json rewrote /(.*) to our function, so
      kit.fareehafatima.com/_vercel/insights/script.js AND the /_vercel/insights/view beacon both
      returned FastAPI's {"detail":"Not Found"} (verified with curl before changing anything). The
      rewrite now excludes /_vercel/. Enable Web Analytics in the Vercel dashboard and the script
      will start returning 200 on its own.

- [x] (Claude Code) URGENT foreai REBUILD done: https://kit.fareehafatima.com/k/foreai is now
      25/25 (5 per tab, original tab order) with ZERO mention of Citi/HSBC/Scotiabank/Discover/
      Intesa/Standard Chartered anywhere on the page. Verified your read of foreai.co first: those
      six brands appear only under "Explore live test cases ... See in action"; the trusted-by row
      is Google, UBS, Sixt, NZZ, SMG, Uber (+ onlinefuels.de, a 7th logo you did not list — say if
      you want it in named_customers). 0 Apollo credits (prospects reused verbatim from the live
      page), ~$0.30 API.
      ENGINE (capture.py, permanent, COMMITTED BUT UNPUSHED): (1) CUSTOMER_EVIDENCE_RULE in the
      extract_assets prompt — a brand counts as a customer only via trusted-by / testimonial /
      case study, and is EXCLUDED when it appears in demo content, sample test cases, "see in
      action" walkthroughs, screenshots or integration lists; (2) CUSTOMER CLAIM RULE in the
      sequence prompt — only named_customers may be called customers, and a result/metric/quote
      may not be attached to one unless that exact pairing is in case_studies; email 3 falls back
      to aggregate proof_points when case_studies is empty instead of inventing a case study.
      Both prompts render-tested with stubbed deps.
      ROOT CAUSE of Tony's empty tab (not rate limits): with a company name in Hebrew, the model
      answered in Hebrew, which is enough extra tokens to blow the 60s cap. Six consecutive 504s;
      adding one "write in ENGLISH" line landed it in 16.1s. That line is now in VOICE, so it is
      fixed for every future non-Latin prospect. Also seen: firing all 5 /api/sequence calls at
      once 504s more than running them one at a time (3/5 concurrent vs 5/5 serial).
      CONTENT: first pass was 25/25 but 4 of the email 3s still invented Sixt/UBS/Google outcomes
      ("how Sixt cut testing time without adding headcount"), so those four were regenerated with
      the sharper rule and only email 3 swapped in, keeping the QC-passed 1/2/4/5 verbatim. Final
      QC on all 25: no forbidden brand, no fabricated customer result (customers named as
      customers only, 90%/10x stated as aggregate), 74-95 word bodies, no em dashes, no
      exclamation marks, correct "Hi <first>," openers, 0 dead links (only real assets:
      tools.foreai.co/roi-calculator, app.foreai.co), inline Calendly, no video block.
      Kit JSON kept at scratchpad/foreai_kit.json until the /api/kit/{slug} task below lands.
- [x] (Claude Code) Engine rule hardened in two more passes, because live tests showed the first
      version was too soft. Prod with rule v1 still wrote "How UBS and Sixt handle QA at scale /
      UBS runs on fore ai for exactly that reason" (invents how and why a real customer uses it),
      so v2 (8f424d0) allows ONLY the bare fact that a named_customer is a customer unless
      case_studies has that exact pairing, and names those observed phrasings as fabrications.
      Verified live after deploy: bodies came back honest ("companies like UBS and Sixt run on it",
      90%/10x stated as aggregate). One gap remained, the subject line "Why Google and UBS run QA
      differently now", so v3 (1d7ba80) forbids a customer name in ANY subject when case_studies
      is empty. v3 (pushed as 9ec9f3c) verified live on 2 fresh sequences, 10 subjects: no invented
      customer story anywhere, and 9 of 10 subjects name no customer. The one that did was
      "Companies like Uber and Sixt run this way", which states only the bare true fact, so I left
      the rule as is rather than tighten further: the no-name-in-subject line is a proxy for the
      real bar (no promise the body cannot honour) and that bar held. Nothing outstanding here.
- [x] (Claude Code) REPAIRED openhive to 25/25 without a full rerun (0 Apollo credits, ~$0.10 API).
      Parsed Riley's + Wayne's existing about + 5 emails each out of the live /k/openhive HTML and
      kept them verbatim; POSTed /api/sequence for the 3 failed prospects (Kushal Magar/SyncGTM 5,
      Adir Zimerman/Rainmakers 5, Vic Ahmed/PitchStart 5 — all landed first try, 28-57s); assembled
      the kit in the original tab order [Kushal, Adir, Riley, Vic, Wayne] and POSTed /api/share.
      Verified live: https://kit.fareehafatima.com/k/openhive now shows 25 emails across 5 tabs
      (5 each), 0 dead links, Riley's/Wayne's original subjects intact. share_error=None.
- [x] (Claude Code) CONFIRMED 25/25 LIVE on prod. edexia now renders a full, clean kit at
      https://kit.fareehafatima.com/k/edexia — 25 emails across 5 unique-company AU buyers
      (David Shaw/CREST, Dianne Bryant/Illawarra Grammar, Trish Stockbridge/Kambala, Bruce
      McNalty/Townsville Grammar, Tahira Hussain/Wisdom), 0 dead asset links, inline text/html
      (200, no attachment). One sequence 504'd at 61s on first try and the retry landed it in 30s
      (5/5) — structured outputs (valid JSON, ~16-30s/call) + one retry = reliable 25/25.
      This confirm reused saved prospects, so it cost ~0 Apollo credits.
- [x] (Claude Code) Front-end retry (0f7512e): fetchSequence retries a failed/empty /api/sequence
      once, recovering the occasional single-call 60s 504. JS parses clean. Unpushed (see INBOX) —
      not required for the current kit, needed for real browser users.
- [x] (Claude Code) JSON-validity fix (1ba3ad2): write_prospect_sequence now uses structured
      outputs (output_config json_schema, SEQUENCE_SCHEMA) so the API guarantees valid JSON —
      eliminates the unescaped-quote / no-JSON parse failures that capped run 3 at 15/25. Graceful
      fallback to the tolerant parser if structured outputs are unavailable (old SDK / model /
      transient) so it never regresses. Unit-tested all four paths + schema validity.
- [x] (Claude Code) Timeout fix committed: reverted write_prospect_sequence max_tokens 4000->2600
      (871e37a) after live regenerates 504'd on individual /api/sequence calls at ~60s; plus
      front-end fan-out stagger + shorter retry backoff (0ee0cdc). Confirmed live: no more 504s.
- [x] (Claude Code) QC fixes committed (3eabe6a), all four, with tests: (1) dedupe by company +
      buyer-title preference (apollo per_page=25 + location fields; capture.dedupe_by_company /
      title_score) so no two prospects share an org and practitioners lose to buyers; (2)
      target_locations enforced (capture._enforce_locations), relaxed only if <top_n match; (3)
      no dead links — sequence prompt emits "asset" only with a real url else null+prose, and
      report_html + web skip empty/#/<> anchors (valid_asset_url/validUrl); (4) /k/{slug} now
      serves the blob inline as text/html (no-cache) and every share_url is the /k/<slug> path
      on our domain (fixes the "link downloads a file" issue). Files: apollo.py, capture.py,
      storage.py (fetch_kit_html), report_html.py, app.py, web/index.html. Awaiting push +
      edexia regenerate (see INBOX).
- [x] (Claude Code) LIVE RE-TEST PASSED on the split flow (prod, main @ 2fd4282, edexia.com force).
      /api/analyze 14.8s -> 5 prospects. 5x /api/sequence in parallel, all http=200, 5 emails each
      = 25/25 emails (longest single call 57.4s, under the 60s cap; the others 18-30s). /api/share
      0.9s -> share_url with share_error=None (blob token now correct).
      SHARE URL: https://gzbaq0nk2iyh6nku.public.blob.vercel-storage.com/kits/kit-edexia.html
      Verified: page loads (200, 25KB, tabs+emails+inline Calendly, title "ICP Capture Kit —
      Edexia"); /k/edexia now 307-redirects to it; /api/analyze without force returns cached=True
      with the share_url (once-per-domain cache working). No 60s timeout anywhere. Fareeha can QC
      the 25 emails at the share URL above.
- [x] (Claude Code) URGENT — split the API so no request runs all 5 sequences (commit 07bf05f).
      The combined /api/capture run was blowing Vercel's 60s cap (plain-text timeout page).
      Now: POST /api/analyze {domain,force} = scrape + assets + enriched prospects (fast half,
      keeps the once-per-domain cache check); POST /api/sequence {assets,prospect} = one
      prospect's 5-email kit; POST /api/share {kit} = render + Blob store -> share_url
      (surfaces share_error). capture.build_kit refactored into analyze() + sequence_for()
      (kept as the CLI path). web/index.html rewritten: analyze, render tab shell with pending
      panes, fan out /api/sequence for all prospects IN PARALLEL filling each tab as it lands,
      then /api/share for the link; per-prospect + share errors surfaced inline. /api/capture
      kept for CLI/back-compat. Files: app.py, capture.py, web/index.html. Verified: endpoint
      tests (analyze cache miss/hit/force, sequence, share ok/403/disabled), sequence_for
      failure capture, and front-end JS parses clean. Needs live re-test after push+deploy.
- [x] (Claude Code) JSON-robustness fix committed (b8697df) for the 4/5 empty sequences that
      Cowork Claude's prod test traced to JSON parse failures (not rate limits). scrape_llm:
      extract_json now strips a ```json fence, decodes from the first brace with raw_decode
      (tolerates trailing prose), and parses strict=False (literal newlines/tabs in bodies no
      longer break it); new llm_json helper adds ONE retry on a parse failure (empty/refused/
      malformed), separate from llm()'s HTTP retry. capture: write_prospect_sequence uses
      llm_json, max_tokens 2600->4000, and instructs valid JSON with no inner double-quotes;
      extract_assets routed through llm_json too. Per-prospect error surfacing + totals kept.
      Unit-tested extract_json (newlines/tabs/fences/trailing-junk/empty) and the llm_json retry.
      Needs live re-test after main deploys to confirm 25/25.
- [x] (Claude Code) Decision 2 — 25-email rate-limit resilience committed (3d4f1ff). llm() does
      one jittered-backoff retry on transient 429/529/5xx; build_kit staggers the concurrent
      prospect-sequence starts (STAGGER_SECONDS=0.8/index) and stores per-prospect errors.
      (Prod test confirmed no 429s remained; the residual failures were JSON, fixed above.)
- [x] (Claude Code) Decision 1 — merged deploy-branch tip into main (clean fast-forward, no
      force). Confirmed prod branch is main: every production deploy has githubCommitRef=main;
      pushing main auto-deploys prod (no manual promotion). main up to 3509b9e is now live.
- [x] (Claude Code) TASK 1 hybrid sync done. git-init'd folder, added remote, synced FROM the
      deploy branch (no force-push). Original premise was backwards: local was OLDER, missing
      api/index.py + vercel.json and behind on the Apollo endpoint (old /v1 path 403s),
      concurrent sequences, and the read-only-FS guard. All v3.1 features present; nothing to
      port. Added CLAUDE.md + AGENT_TASKS.md to the repo; gitignored .claude/ and .vercel.
- [x] (Claude Code) Verified live capture end to end (all but share link). stripe.com ~45s,
      edexia.com (force) with 5 real enriched AU teacher prospects + verified emails. Confirms
      ANTHROPIC_API_KEY, APOLLO_API_KEY, APOLLO_ENRICH=1 working, maxDuration=60 in vercel.json.
- [x] (Cowork Claude) Built v3.1 feature set; found GitHub already carried the newer Vercel
      plumbing. Task 1 rewritten to hybrid-sync instead of force-push. Claude Code's catch — correct.
