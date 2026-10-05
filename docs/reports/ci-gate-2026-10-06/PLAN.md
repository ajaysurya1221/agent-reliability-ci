# Plan of record: "ARCI: Planning, Gating and Reproducing Agent Regressions" (2026-10-06)

Frozen at 21:10 IST on 2026-10-05 for delivery by 12:00 IST on 2026-10-06. This file is the
specification the work packages are checked against. It is not evidence; evidence lives beside
it in this directory once produced.

## Question this package answers

A practitioner changing an agent's prompt, harness or model asks: "is this change real or
noise, and if real, what broke?" This package documents how `arci` answers it with a
pre-registered, exact non-inferiority gate whose decision rule is bound into every trial's
identity, and how a regression verdict connects to a trace divergence, a minimised fault and an
offline reproducer. It adds a planner (`arci plan`) that enumerates the gate's verdict
probabilities before any trial runs, optional descriptive pass^k reporting, and a
clean-environment reproduction package for the archived campaigns.

## Starting identities

| Item | Value |
|---|---|
| agent-reliability-ci main | f299854326194e7b09afb430d4530c4c7c9f3c98 |
| frontier-scout main | b9abe24146b7fd164fb258b0bb2ea39f344850f1 |
| arci FROZEN.sha256 | 48 entries, all OK on both arci worktrees |
| Worktrees | `.arci-worktrees/sb011-plan` (planner), `.arci-worktrees/sb011-release` (report/release), `.frontier-worktrees/sb011-verifier` (verifier repair) |
| Environment | arci worktree venvs: CPython 3.13.12 (uv-managed; `uv.lock` declares compatibility, not a patch pin); system python3 3.14.6; uv 0.12.5, node 24.18.0, Docker 29.8.2 (host linux/arm64; linux/amd64 by emulation), gh 2.97.0, Claude Code 2.1.281 (not used by this package) |
| Live model spend planned | USD 0 (no new live campaign) |

## Frozen decisions

- The planner implements exactly the gate in `docs/STATISTICS.md`: Clopper-Pearson, fixed
  sample, one condition (K=1), one look, tail allocation alpha/(4K), margin delta, independent
  binomial arms, N <= 400 per arm. For every N it reports all three probabilities
  P(PASS), P(BLOCK), P(INCONCLUSIVE) (summing to 1) and the smallest tested N meeting the
  target or "target not reached". Unsupported designs (N > 400, K != 1, looks, newcombe) are
  rejected with a message, not approximated.
- Optional pass^k reporting is descriptive only: all-success estimator C(successes,k)/C(n,k) per
  arm and declared population under an IID assumption; "unavailable" for n < k, invalid
  experiments and outcome-selected sequential stopping; never pooled across conditions.
- Descriptive reporting (pass^k) never changes a verdict, an exit code or a decision seal.
- No new live campaign; archived stores are never edited or resealed.
- No statistical-contract change; no FROZEN file changes; no new runtime dependencies.
- frontier-scout receipts remain supporting observations; approval provenance is UNVERIFIED
  until an authenticated source exists.

## Work packages, owners, cut rules

| WP | Owner | Window (IST) | Cut rule |
|---|---|---|---|
| WP1 freeze | orchestrator | 21:00–21:30 | none |
| WP2 `arci plan` (mandatory), pass^k (optional) | coder A | 21:10–04:00 | pass^k cut at 04:00 if it endangers the planner |
| WP3 verifier repair | coder B | 21:10–05:30 | at 07:00 unrepaired paths become documented limitations, no positive claim |
| WP4 report + reproduction package | orchestrator assembles, architect drafts text, coder A builds reproduce tooling after WP2 | 21:30–08:30 | figures and comparison breadth cut first |
| WP5 freeze, verify, release | orchestrator, architect final review | 08:30–12:00 | 09:00 implementation freeze; 11:15 unresolved CI means a labelled prerelease |

## Acceptance commands

- arci: `just check`, `just frozen` (48 OK), `uv run arci plan --baseline-rate 0.95 --candidate-rate 0.75 --alpha 0.05 --delta 0.10 --n-grid 20,50,100,200,400 --target-verdict BLOCK --target-probability 0.80 --format json`; reproduction: all 18 archived `decision.json` files (12 Jev including the five under `attempt-1-invalid/`, 6 guardrail) re-derive byte for byte in clean subprocess checks on macOS and in Docker (`--platform linux/amd64`); both committed minimised bundles replay REPRODUCED with `--network none` and are left unchanged; the seeded retry example (`examples/retry_agent/hero_demo.py`) reproduces from the release source; `python docs/reports/ci-gate-2026-10-06/reproduce.py --check` passes in a clean clone and in Docker; CI green on the exact PR head and after merge, recorded with URLs and platforms.
- frontier-scout: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q`, `make lint type`, `make demo`; the regression matrix (real git repositories) reproduces each original defect on the unrepaired code and rejects it after the repair; required controls: scope evaluated against the policy and lock of the trusted base commit (a PR cannot expand its own authorisation), a pinned installed verifier (never PR-supplied code), `allowed_file_globs` enforced over renames (both endpoints), deletions, binary and mode-only changes, unusual filenames (newline-safe parsing), a forged approval receipt committed inside the PR rejected, policy+lock self-expansion governed by the base, a protected file renamed out of scope rejected, failed diff collection never a pass, benign in-scope and empty-diff controls passing; a local `ask`/`allow`/`realized`/self-declared approval source yields UNVERIFIED (non-green in enforcing mode) with the reason "approval provenance not authenticated".

## Claims permitted at delivery

1. arci binds the declared decision rule into trial identity and rejects rule substitution and
   incomplete stores (frozen acceptance cases; evalsig is the nearest gate, not a superiority claim).
2. The planner enumerates the existing Clopper-Pearson gate's verdict probabilities over its
   declared grid (reference: about 0.365 BLOCK for 0.95 vs 0.75 at N=200, alpha 0.05, delta 0.10;
   evalsig also offers power planning).
3. All 18 released Jev and guardrail decision records, including invalid attempts, re-derive byte
   for byte on the named tested platforms (exact file comparison; Chronicle is adjacent replay
   work; no comparative score).
4. The released examples connect a regression verdict to a trace divergence and an offline
   failure reproducer (published commands, fingerprints and replay outcomes; "reduced" is kept
   for live examples).
5. The repaired frontier-scout verifier rejects every published out-of-scope and unsupported-
   approval control and accepts the benign scope controls (complete before/after matrix;
   MergeWarden and AGENTOWNERS as comparators).
Must not claim: first agent firewall, first statistical CI gate, first decision-boundary fault
injection, first executable claim verification, or a novel statistical method; universal
calibration or permission calibration from intent datasets; exact Newcombe coverage; anytime-
valid inference; native Claude Code enforcement from synthetic inputs; authenticated approval
from unsigned receipts; production-safe autonomous coding; detection of small regressions at
practical N without the power numbers; ACS certification, regulatory compliance, independently
validated adoption, or superiority outside the measured comparison. No overall "state of the
art" or "first" claim is made by this package.
