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
| Environment | Python 3.14.6 (arci venvs use the uv-managed interpreter pinned by uv.lock), uv 0.12.5, node 24.18.0, Docker 29.8.2 (host linux/arm64; linux/amd64 by emulation), gh 2.97.0, Claude Code 2.1.281 (not used by this package) |
| Live model spend planned | USD 0 (no new live campaign) |

## Frozen decisions

- The planner implements exactly the gate in `docs/STATISTICS.md`: Clopper-Pearson, fixed
  sample, one condition (K=1), one look, tail allocation alpha/(4K), margin delta. Unsupported
  designs are rejected with a message, not approximated.
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

- arci: `just check`, `just frozen`, `uv run arci plan --baseline-rate 0.95 --candidate-rate 0.75 --alpha 0.05 --delta 0.10 --n-grid 20,50,100,200,400 --target-verdict BLOCK --target-probability 0.80 --format json`, `python docs/reports/ci-gate-2026-10-06/reproduce.py --check` (clean clone, and in Docker with `--platform linux/amd64 --network none`), CI green on the PR head and after merge.
- frontier-scout: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q`, `make lint type`, `make demo`; regression matrix tests reproduce each original defect and reject it after the repair.

## Claims permitted at delivery

Only the five claims listed in the orchestrator's approved plan, each with its measurement and
nearest comparison; the must-not-claim list applies verbatim. No overall "state of the art" or
"first" claim is made by this package.
