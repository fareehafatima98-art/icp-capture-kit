# AGENT_TASKS — shared channel between Cowork Claude and Claude Code

Protocol: Claude Code reads this FIRST every session. Do INBOX top to bottom. Move finished
items to DONE with a one-line result (files touched + test output/URL). Blockers go to
BLOCKED with the exact error. Commit this file with your changes.

## INBOX

- [ ] (Needs Fareeha, then Claude Code) After main is pushed AND BLOB_READ_WRITE_TOKEN is added
      to prod env AND Vercel redeploys main: POST /api/capture with force on a test domain and
      confirm (a) share_url is non-null (or read share_error for the real reason) and (b) 25/25
      emails land with the retry+stagger fix. Log the share_url here. Claude Code will run this
      re-test as soon as the deploy is live.

## BLOCKED

- [ ] Push. Local main and branch claude/push-files-t6r4u2 are ready at the SAME commit
      (3083e00): base sync + docs + resilience fix, main fast-forwarded over origin/main
      (no divergence, no force needed). Claude Code's env has NO GitHub creds (no gh, no token,
      no helper). ACTION FOR FAREEHA: run `! git push origin main` (this is the one that matters
      — see below) and `! git push origin claude/push-files-t6r4u2` in the Claude Code prompt
      (Mac keychain should have creds). If it fails, switch to SSH:
      `git remote set-url origin git@github.com:fareehafatima98-art/icp-capture-kit.git` then retry.
      NOTE: pushing main auto-deploys to PRODUCTION (kit.fareehafatima.com) — no manual promotion
      needed. Confirmed from deploy history: every production-target deploy has githubCommitRef=main;
      the claude branch only ever made PR previews. The blob-fix commit 06d1c2b was a preview that
      was NEVER merged to main, which is exactly why prod lacked it. The main merge fixes that.
      AUTH STATUS (confirmed 2026-07-24): pushing via the Claude Code `!` prompt fails
      ("could not read Username ... Device not configured") for BOTH https and ssh — this Mac has
      no cached GitHub creds, no ~/.ssh key, and no gh CLI, and `!` has no interactive prompt.
      Resolution (do ONE, in the real Terminal.app so no token leaks into the session): (a)
      `git push origin main` in Terminal and paste a fine-grained PAT (Contents: R/W) as the
      password; or (b) `brew install gh && gh auth login && gh auth setup-git` then push (this
      also unblocks `!` pushes here afterward); or (c) generate an ssh key, add it to GitHub, and
      `git remote set-url origin git@github.com:fareehafatima98-art/icp-capture-kit.git`. Remote
      is currently https.
- [ ] Add BLOB_READ_WRITE_TOKEN to prod env (Fareeha, in progress). Root cause of null share_url:
      the Blob store is connected via Vercel OIDC, which injects only BLOB_STORE_ID +
      BLOB_WEBHOOK_PUBLIC_KEY, not BLOB_READ_WRITE_TOKEN. storage.py needs the read-write token.
      Fareeha is adding it manually (store Settings -> copy token -> project env var) + redeploy.
      DO NOT revoke the token.

## DONE

- [x] (Claude Code) Decision 2 — 25-email resilience fix committed (3d4f1ff). scrape_llm.llm now
      does one jittered-backoff retry on transient 429/529/5xx; build_kit staggers the concurrent
      prospect-sequence starts (STAGGER_SECONDS=0.8/index) so the burst spreads across the rate
      limit while still overlapping (stays inside Vercel's 60s cap), and stores the per-prospect
      error on the kit instead of dropping it. Files: scrape_llm.py, capture.py. Verified with a
      mocked run: order preserved, errors stored on failures only, counts correct. Needs live
      re-test after deploy to confirm 25/25 (see INBOX).
- [x] (Claude Code) Decision 1 — merged deploy-branch tip into main locally. Clean fast-forward
      (main was exactly 3 commits behind: 06d1c2b surface-blob-errors, 25ec813 docs, 3d4f1ff
      resilience). No force. main and the branch now point at 3d4f1ff, ready to push.
- [x] (Claude Code) TASK 1 hybrid sync done. git-init'd the folder, added remote
      fareehafatima98-art/icp-capture-kit, synced FROM the deploy branch (no force-push).
      Confirmed the original premise was backwards: local was OLDER, missing api/index.py +
      vercel.json and behind on the Apollo endpoint (old /v1 path 403s), concurrent sequences,
      and the read-only-FS guard. All v3.1 features present in the synced code; nothing to port.
      Added CLAUDE.md + AGENT_TASKS.md to the repo; gitignored .claude/ and .vercel.
- [x] (Claude Code) Verified live capture end to end (all but the share link). POST /api/capture
      on kit.fareehafatima.com returned full real kits: stripe.com ~45s, edexia.com (force) with
      5 real enriched AU teacher prospects + verified emails. Confirms ANTHROPIC_API_KEY,
      APOLLO_API_KEY, APOLLO_ENRICH=1 working at runtime, maxDuration=60 in vercel.json.
      share_url null on both (root cause = missing BLOB token, see BLOCKED).
- [x] (Cowork Claude) Built v3.1 feature set; found that GitHub already carried the newer Vercel
      plumbing. Task 1 rewritten to hybrid-sync instead of force-push. Claude Code's catch — correct.
