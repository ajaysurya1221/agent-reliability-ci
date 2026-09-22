# v0.6 to-do: ready for Jev day one

Plan: `~/.claude/plans/you-are-in-plan-bubbly-moore.md` (approved 2026-09-22). The v0.5 log is in
`CHANGELOG.md` and git history. Legend: `[ ]` open, `[~]` in progress, `[x]` done, `[-]` cut.

## 1. Freeze (Claude; Astra xhigh design review folded in)
- [x] Astra design review: PLAN_V06: CHANGE; folded in (request_seconds stays 5 s under the SDK
      timeout, the bounded wait is recorded as attempts/first_status, ERROR on removal blocks 1-minimal)
- [x] `schema.py`: `base_url` with path prefix; `max_requests_per_minute`; `request_seconds` stays 5 s
- [x] `AGENTS.md` v0.6 rules (tolerant validation, headers, throttle, bounded wait, raw upstream,
      preflight, minimality for http upstream)
- [x] Frozen acceptance tests (`test_decisions_v06.py`, `test_decisions_node.py`): gateway-shaped fake upstream, 429-then-200, encoding, TLS message,
      preflight exit codes, throttle timing, raw upstream in records, tokens/cost in report,
      Node agent (skipped without node)
- [x] `FROZEN.sha256`, worktrees wp-k1 / wp-k2 with `.venv`; design record `docs/design/0004-day-one.md`

## 2. Build (Sol, two parallel work packages)
- [x] WP-K1 boundary/runner/cli/report/minimize: A1 A2 A3 B4 B5 B6 C9 (v0.6 acceptance 13/13, all
      decision and MCP socket suites green in the worktree; three test-side fixes on the way)
- [x] WP-K2 example/docs: C8 Node agent + package.json + CI step, B7 runbook + results template,
      README, CHANGELOG 0.6.0, ROADMAP, D10 calibration option (Node test 2/2 with the unmodified JS SDK)

## 3. Verify and review
- [x] Full suite (430 tests), ruff, basedpyright strict, frozen hashes; hero demo 2 via CLI; Node test locally
- [x] Astra release review: CHANGES_REQUIRED (failed resend escaped ERROR, per-entry probability bound,
      preflight echoing provider strings, temp-tarball lock, version 0.5.0) + slow-drip deadline + docs
- [x] Frozen regression tests for every finding; version 0.6.0; registry lock; docs corrected; Sol fixed them (WP-K1b); all socket suites green
- [x] Astra re-check: 1-5, 7-12 FIXED, 6 PARTIAL (chunked trickle past a detached socket) fixed directly
      with a frozen regression case; final gate green (430 tests, ruff, strict types)

## 4. Release
- [x] Merged to main; a timing flake in the v0.1 retry example on the loaded 3.11 runner was fixed
      by raising its per-trial budget to 15 s; CI green on 3.11 and 3.14; tagged `v0.6.0` (a221ad2);
      memory updated. Repo stays private; nothing on PyPI. Delete this file when the next cycle starts.

## Cut order if behind
D10, then C8's CI step (keep the local test), then B6's worker cap. Never cut A1, A3, B4, B5.
