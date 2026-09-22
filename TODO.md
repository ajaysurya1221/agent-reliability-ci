# v0.5 to-do: the decision boundary (Jev / System One)

Live checklist for the autonomous build started 2026-09-22. Goal: arci records, replays, budgets
and perturbs System One (Jev) decisions made by the agent under test, with zero agent changes and
the API key never entering the agent's process. Everything runs offline; a real key slots in later.
Research: `docs/design/jev-research-2026-09-22.md`.

Legend: `[ ]` open, `[~]` in progress, `[x]` done, `[-]` cut.

## 0. Ideation and design (Claude leads, Astra consults)
- [x] Research Jev: blog, docs (api, models, confidence, jaggedness, patterns, cookbooks), SDK
      source (`typesafe-sdk` 0.7.1, `system-one-adapter` 0.2.0), third-party write-ups
- [x] Confirm the integration seam: SDKs read `TYPESAFE_BASE_URL` / `TYPESAFE_API_KEY`
- [x] Astra (xhigh) adversarial review of the goal and design; fold in the verdict (DESIGN: CHANGE, all folded in)
- [x] Write `docs/design/0003-decision-boundary.md` (decision record)

## 1. Freeze (Claude owns; hash-pinned in FROZEN.sha256)
- [x] `schema.py`: `DecisionSpec`, `Manifest.decisions`, `TrialSpec.decisions`; reserved tool
      name `decision`; manifest validation rules
- [x] `schedule.py`: bind `decisions` into every `TrialSpec` (spec hash changes)
- [x] Perturbation kinds `decision_low_confidence`, `decision_unavailable` and their params
- [x] Acceptance tests: HTTP boundary record/replay/miss, key isolation, budgets, 401/422/529
      mapping, perturbation maths, diff signatures, fixture upstream, hero demo 2 exit codes
- [x] `AGENTS.md` v0.5 section for the coder; regenerate `FROZEN.sha256`

## 2. Build (Sol implements offline; Claude verifies outside the sandbox)
- [x] WP-J1: loopback HTTP listener in the boundary process; record/replay/budget for decisions;
      fixture and http upstreams; env injection in the runner (26/26 decision acceptance tests)
- [x] WP-J2 (in J1): decision perturbations; diff signatures for decisions
- [x] WP-J3 (WP-J2 job): `examples/jev_triage_agent` (A gated, B regression, C fix; fixture answers from
      hidden ground truth; MCP tools `issue_refund` / `escalate` / `reply`; independent oracle)
- [x] Hero demo 2 script: A vs B exit 1, A vs A exit 0, A vs C exit 0, replay REPRODUCED,
      minimiser 1-minimal; wired into CI (test_hero_decisions.py 5/5)

## 3. Verify and review
- [ ] Full suite, ruff, basedpyright strict, frozen hashes unchanged
- [x] Astra adversarial review of the full diff with reproductions: CHANGES_REQUIRED, 5 blocking
      (lost worker faults, non-total validation, cross-transport order, pipelining, key leaks) + Expect stall
- [~] Frozen regression tests for every finding (`test_decisions_hardening.py`); Sol fixing (WP-J1b)
- [ ] Specialist escalation only for failures Sol cannot reproduce in its sandbox

## 4. Docs and release
- [ ] `docs/DECISIONS.md` user guide ("Testing agents that use Jev"), TRUST_MODEL addendum,
      REAL_AGENTS pointer, README section + status, CHANGELOG 0.5.0, ROADMAP update
- [ ] Tag `v0.5.0`, push (repo stays private; no PyPI)
- [ ] Update project memory; remove this file or move it into the changelog

## Cut first if behind
- [ ] Descriptive "Decisions" table in `arci report` (confidence bins with exact intervals)
- [-] Ollama-backed System One emulator (use `system-one-adapter`; roadmap note only)
- [-] Python in-process agents (run them as command agents through the toolset bridge)
