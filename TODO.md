# v0.6 to-do: ready for Jev day one

Plan: `~/.claude/plans/you-are-in-plan-bubbly-moore.md` (approved 2026-09-22). The v0.5 log is in
`CHANGELOG.md` and git history. Legend: `[ ]` open, `[~]` in progress, `[x]` done, `[-]` cut.

## 1. Freeze (Claude; Astra xhigh design review folded in)
- [~] Astra design review of A1-D10 (running)
- [~] `schema.py`: `base_url` with path prefix; `max_requests_per_minute`; `request_seconds` 10 s
- [ ] `AGENTS.md` v0.6 rules (tolerant validation, headers, throttle, bounded wait, raw upstream,
      preflight, minimality for http upstream)
- [ ] Frozen acceptance tests: gateway-shaped fake upstream, 429-then-200, encoding, TLS message,
      preflight exit codes, throttle timing, raw upstream in records, tokens/cost in report,
      Node agent (skipped without node)
- [ ] `FROZEN.sha256`, worktrees wp-k1 / wp-k2 with `.venv`

## 2. Build (Sol, two parallel work packages)
- [ ] WP-K1 boundary/runner/cli/report/minimize: A1 A2 A3 B4 B5 B6 C9
- [ ] WP-K2 example/docs: C8 Node agent + package.json + CI step, B7 runbook + results template,
      README, CHANGELOG 0.6.0, ROADMAP, D10 calibration option

## 3. Verify and review
- [ ] Full suite, ruff, basedpyright strict, frozen hashes; hero demos; Node test locally
- [ ] Astra adversarial release review; findings become frozen regression tests; Sol fixes

## 4. Release
- [ ] Merge to main, CI green on 3.11 and 3.14, tag `v0.6.0`, memory, close this list

## Cut order if behind
D10, then C8's CI step (keep the local test), then B6's worker cap. Never cut A1, A3, B4, B5.
