# TASK P1c: fixes after the independent review of the suite kernel

Lane A. Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-suite` (branch `v2/suite`,
your P1a and P1b work is committed there as one commit). Work only there. No git command
that changes state; the orchestrator commits.

Read: `AGENTS.md`; `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md`
section 8 (new, binding); the review record
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/P1-review-workflow.json`
(24 findings with a skeptic's verdict each; none found a statistical error).

You own every file you created in P1a and P1b. Nothing else.

## Do

1. **Contract section 8, items 1 to 7**, in `suite_schema.py`, `suite_schedule.py`,
   `suite_stats.py`, `suite_gate.py`, with unit tests for each item (digit bound at 7 and
   8 digits; `experiment_id` shape; per-round digest; a `bytes` seal; a decision with a
   plain-string verdict in replay; the 5,000-round timing; a test that turns warnings into
   errors around `decide_suite` on wrong-typed records).
2. **Bench (`bench/selfcheck_suite.py`)**, each with a reason the old check could not fail:
   - the gate-versus-enumeration check uses laws that are not mirror images of each other
     and a rule under which BLOCK is reachable before the last round on many paths, so a
     gate that flips the sign of the difference, or ignores an early BLOCK, fails;
   - add gate paths with errored pairs (at and above the tolerance) and with hard
     violations, compared against an independent expectation written in the bench;
   - the default rule is taken from a default `SuiteManifest` through `rule_of`, not from
     literals;
   - the margin grid adds the equal-mean three-point family with a free `P(0)`, so the
     maxima in ADR 0011 (2.16% at 1 cell, 1.97% at 2, 1.67% at 5, 1.42% at 10, 1.15% at 20)
     are reproduced or the difference is reported exactly;
   - a report-only row for the common-mode case of ADR 0011 item 6 (20 cells, a whole
     round sharing one outcome).
   Keep the default run under ten minutes.
3. **`docs/STATISTICS_SUITE.md`**: state that the arm order flips by round and that an
   order effect is therefore a breaker of the same-law-every-round assumption; give the
   common-mode magnitude (0.9% to 67% at 20 cells) with its source; define the estimand
   once, for the pair's true outcomes, and say separately how errored pairs are scored;
   write the default stake set as a set, not as an interval; cite only files that are
   tracked in this branch for exact numbers (copy what is needed under
   `tests/unit/suite/` or into the bench).
4. Leave alone, by decision: suite-wide contract and budgets; seeds derived from the whole
   rule digest; `evaluate_rounds` trusting its stated assumptions; scoring on `outcome`.

## Acceptance (from the worktree root)

```sh
.venv/bin/pytest tests/unit/suite tests/unit/selfcheck -q
.venv/bin/python -m bench.selfcheck_suite
.venv/bin/pytest -q
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright
shasum -a 256 -c FROZEN.sha256
```

Sandbox: tests outside your files that fail only on sockets or `ps` are the orchestrator's
to re-run; name them. Stop and report if section 8 is ambiguous or wrong.

Report (under 50 lines): per item what changed and the test that proves it; command tails;
the measured 100,000-round time; the bench's new maxima per grid size; risks.
