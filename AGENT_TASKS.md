# AGENT_TASKS — shared channel between Cowork Claude and Claude Code

Protocol: Claude Code reads this FIRST every session. Do INBOX top to bottom. Move finished
items to DONE with a one-line result (files touched + test output/URL). Blockers go to
BLOCKED with the exact error. Commit this file with your changes.

## INBOX

- [ ] (Fareeha) BLOB token VALUE is wrong, not missing: prod says "Cannot get store id from
      token" (403). BLOB_READ_WRITE_TOKEN must contain the token starting with vercel_blob_rw_
      (from the Blob store's Settings), not the store ID or webhook key. Replace the value +
      redeploy, then re-test share_url.
- [ ] (Fareeha, then Claude Code) Push main so the JSON-robustness fix (b8697df) ships. Local
      main is 1 ahead of origin/main. Claude Code still cannot push from here (no creds in its
      env). Fareeha: `git push origin main` from Terminal (the same way 3509b9e went up). After
      that deploys AND the BLOB token value is fixed: Claude Code runs the live re-test —
      POST /api/capture with force on a fresh domain, confirm share_url non-null AND 25/25
      emails, log the share_url here.

## BLOCKED

- [ ] Push from Claude Code's env: still fails ("could not read Username ... terminal prompts
      disabled") for both https and ssh — no cached creds, no ~/.ssh key, no gh CLI, and `!` has
      no interactive prompt. Pushes must come from Fareeha's Terminal.app (that is how 3509b9e
      reached prod). Local commits are always staged and ready; see the INBOX push item.

## DONE

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
