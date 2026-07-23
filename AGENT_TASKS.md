# AGENT_TASKS — shared channel between Cowork Claude and Claude Code

Protocol: Claude Code reads this FIRST every session. Do INBOX top to bottom. Move finished
items to DONE with a one-line result (files touched + test output/URL). Blockers go to
BLOCKED with the exact error. Commit this file with your changes.

## INBOX

- [ ] Fix null share_url in PRODUCTION. Code fix (storage.last_error + x-allow-overwrite +
      app.py share_error) already exists on this branch tip. Production (kit.fareehafatima.com)
      serves an OLDER intermediate deploy that lacks it and swallows Blob errors, so share_url
      comes back null with no reason. Needs branch tip promoted to production (see BLOCKED),
      then re-run a domain and read share_url / share_error to confirm the real Blob status.
- [ ] Only 1 of 5 prospects got emails on the edexia run (5 emails, not 25). The 4 failures are
      swallowed: build_kit catches the per-prospect exception but does NOT store the error on
      the prospect kit, so we can't see why. Likely rate-limiting from firing 5 concurrent
      Claude calls (ThreadPoolExecutor, max_workers=len(prospects)). Surface the per-prospect
      error and/or add a small retry/stagger, then re-run to confirm 25 emails.

## BLOCKED

- [ ] Push the local commit (52c95b5, docs + gitignore). No GitHub credentials in Claude Code's
      environment: no gh CLI, no GH_TOKEN/GITHUB_TOKEN, no git credential helper. Commit is made
      and ready. To push, Fareeha can either run `! git push -u origin claude/push-files-t6r4u2`
      in the prompt (if her machine has GitHub creds/keychain), or provide a PAT with repo write
      scope, or switch the remote to SSH (git remote set-url origin git@github.com:...).
- [ ] Promote branch tip to production + confirm production branch. Needs Fareeha: decide
      whether production tracks `main` (currently BEHIND this branch) or this deploy branch,
      and authorize promoting the deploy so the share_url fix goes live. Also: Claude Code
      cannot read Vercel env vars via MCP — confirm BLOB_READ_WRITE_TOKEN is set for the
      Production environment (suspected root cause of null share_url).

## DONE

- [x] (Claude Code) TASK 1 hybrid sync done. git-init'd the folder, added remote
      fareehafatima98-art/icp-capture-kit, and synced FROM the deploy branch
      claude/push-files-t6r4u2 (tip 06d1c2b). No force-push. Confirmed the original premise was
      backwards: local was OLDER, missing api/index.py + vercel.json and behind on the Apollo
      endpoint (/api/v1 + /mixed_people/api_search; old /v1 path 403s for API keys), concurrent
      per-prospect sequences (fits Vercel 60s cap), and the read-only-FS guard. Verified all
      v3.1 features present in the synced code (per-prospect 25 emails, email-first enrichment,
      own-customer filter, location targeting, Blob share pages + share_url with error
      surfacing, cache + force, inline Calendly calendly.com/hifareeha/discovery-meeting-with-
      fareeha, no video placeholder, 60-90 word bar, haiku guard). Nothing missing to port.
      Added CLAUDE.md + AGENT_TASKS.md to the repo; gitignored .claude/ and .vercel.
- [x] (Claude Code) Verified live capture end to end (all but the share link). POST
      /api/capture on kit.fareehafatima.com returned full real kits: stripe.com ~45s, edexia.com
      (force) with 5 real enriched AU teacher prospects + verified emails. Confirms
      ANTHROPIC_API_KEY, APOLLO_API_KEY, APOLLO_ENRICH=1 working at runtime, maxDuration=60 in
      vercel.json (env-var task item done except BLOB, which is in BLOCKED). share_url null on
      both and /k/edexia is 404 (nothing saved to Blob) -> moved to INBOX.
- [x] (Cowork Claude) Built v3.1 feature set; discovered during task 1 that GitHub already
      carries newer Vercel plumbing (api/index.py, vercel.json, Apollo/concurrency/FS
      fixes). Task 1 rewritten above to hybrid-sync instead of force-push. Claude Code's
      catch — correct call.
