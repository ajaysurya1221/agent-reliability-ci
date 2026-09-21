# Changelog

## v0.1.0 (2026-09-21)

First release. One claim: a measured regression becomes an executable, reduced failure case.

### What is in it

- Frozen, sealed experiments (`Manifest`), a deterministic paired schedule, one fresh process per
  trial with a separate grader process, a single parent writer for `events.jsonl` and `trials.jsonl`.
- The tool boundary (`ToolBox`): budgets, seeded fault injection (`tool_timeout`, `tool_error_once`,
  `empty_result`, or your own `"module:function"`), record and replay.
- The gate: exact Clopper-Pearson at tail `alpha / (4K)`, Bonferroni bounds on the difference,
  verdicts PASS / BLOCK / INCONCLUSIVE / ERROR with exit codes 0 / 1 / 2 / 3. It never raises.
- `bench/selfcheck.py`: the gate's own operating characteristics by exact enumeration.
- Boundary-aligned trace divergence, ddmin fault minimisation with an honest 1-minimal claim,
  portable replay bundles with hash-verified embedded code.
- CLI (`arci run | gate | report | bundle | replay | diff | minimize`), Markdown and JUnit reports,
  a composite GitHub Action.
- `examples/retry_agent`: agents A, B (A minus one retry) and C (the repair), with a six-step demo.

### How it was checked

229 tests, basedpyright strict, CI on Python 3.11 and 3.14. The acceptance suite was written before
the implementation and is hash-pinned (`FROZEN.sha256`). An adversarial reviewer attacked the code at
four checkpoints with reproductions; 40 findings were fixed and each has a frozen regression test
(`tests/acceptance/test_hardening*.py`). Every published calibration number was recomputed
independently by the reviewer and matched.

### Known limits and residual risks

- Trust model: the agent is assumed buggy, not hostile. It shares a process with the tool boundary,
  so a deliberately hostile agent can forge its result. See `docs/TRUST_MODEL.md`.
- Only the tool boundary is observed. Direct file, network or subprocess use by the agent is
  invisible. Descendants that start their own session survive cleanup.
- The gate is conservative by design: mid-range success rates need large N to reach PASS, and
  N=20 decides almost nothing. `prior_runs` is author-supplied; no cross-run error budget is enforced.
- Supported statistics range: `alpha` in [1e-6, 0.5] with `alpha >= K x 1e-6`, `n_per_arm <= 10000`.
- Bundles embed only the files you include; the minimiser's output embeds none.
- The final reviewer re-check ran on Python 3.13 in a read-only sandbox, so writing bundle payloads
  to disk was exercised by the test suite and CI (3.11, 3.14) but not by that review.
- POSIX only (process groups, `ps` in tests). Windows is untested.
