# Rules for coding agents in this repo

Read `src/arci/interfaces.py`, `src/arci/schema.py` and `docs/STATISTICS.md` first.

## Hard rules

1. FROZEN files are listed in `FROZEN.sha256`. Never edit, move or delete them. That covers
   `src/arci/{schema,interfaces,hashing,fingerprint,schedule,contracts}.py`, everything under `tests/acceptance/`,
   `pyproject.toml`, `uv.lock`, `justfile`, `AGENTS.md`, `docs/STATISTICS.md`. If a frozen file
   looks wrong, stop and say so in your final message. Do not work around it.
2. Edit only the files your brief says you own. Create new files only inside those paths.
3. Do not run git commands that change state (no add, commit, checkout, stash, reset). The
   orchestrator owns git.
4. No network. No new dependencies. Runtime code uses only the stdlib, `pydantic`, `pyyaml`.
5. Use `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/basedpyright`
   directly. Do not call `uv`.
6. The acceptance tests in `tests/acceptance/` are the source of truth for signatures and
   behaviour. Make them pass without touching them. Add your own tests under `tests/unit/<area>/`.
7. Finish with `ruff format`, `ruff check`, `basedpyright` clean on your files (strict mode;
   avoid `# pyright: ignore` unless unavoidable, and explain each one).
8. Your final message: files changed, test command and its last lines, anything you could not do,
   risks. No long logs. Your report is not acceptance evidence; the orchestrator re-runs checks.

## Semantics that tests rely on

- Trial outcome: `PASS` iff the oracle says success AND there is no hard violation. Agent crash,
  uncaught `ToolFault`, timeout, budget exhaustion, oracle-says-no = `FAIL`. Harness fault, grader
  exception, `ReplayMiss` = `ERROR`. Every scheduled trial produces exactly one sealed envelope.
- Determinism: for the same `TrialSpec`, everything except volatile fields
  (each model's declared `VOLATILE` set in `arci.schema`) must be identical, so `record_sha256` is stable. Call ids are
  `c-0000`, `c-0001`, ... in call order. No wall-clock data, pids, temp paths or tracebacks in
  non-volatile fields. `failure_detail` is one deterministic line.
- Randomness: derive every RNG from the spec seed with string namespaces, e.g.
  `random.Random(f"{seed}:agent")`, `random.Random(f"{seed}:fault:{name}")`.
- The schedule is `arci.schedule.build_schedule(manifest)`; `TrialEnvelope.spec_sha256` is
  `arci.schedule.spec_sha256(spec)`. Never re-derive either.
- Events: `trial_start`, then `model_step` / `tool_start` / `tool_finish` in order, then
  `agent_result` (if the agent returned), then exactly one `trial_end`, which the PARENT
  synthesises if the child died or was killed before sending it. `seq` is 0..n-1 with no gaps.
  `tool_start` payload: `tool`, `call_id`, `occurrence`, `arguments`. `tool_finish` payload:
  `tool`, `call_id`, `ok`, `value`, `error_kind`, `injected_by`. The child writes each event to the
  parent as one JSON line and flushes immediately; the parent is the ONLY writer of files.
- Injected calls count toward `max_tool_calls`. The call that would exceed the budget raises
  `BudgetExceeded` before any `tool_start` is emitted.
- Perturbations: `tool_timeout` and `tool_error_once` short-circuit in `before()` with
  `ok=False` (`error_kind` "timeout" / "error"), which the ToolBox raises to the agent as
  `ToolFault`. `empty_result` rewrites the real result's `value` to `None` in `after()`.
  A fault fires only when `tool` matches (None = any) and `occurrence == at_occurrence`
  (None = 0).
- Failure fingerprints use `arci.fingerprint.fingerprint(kind, detail)`:
  oracle failure: kind `"oracle"`, detail
  `"oracle rejected final state; first_failed_tool=<tool>:<error_kind>"` or `...=none`;
  crash: kind `"crash"`, detail = exception type and message; timeout: kind `"timeout"`;
  budget: kind `"budget"`; hard violation: kind `"invariant:<name>"`.
- The child process must be able to import `"module:function"` targets that live in the repo
  (including `tests.acceptance.fixture_agents`): launch it with `sys.executable` and pass the
  parent's `sys.path` through `PYTHONPATH`. Kill the whole process group on timeout.
- REPLAY mode never executes live tools and never re-applies perturbations: it serves recorded
  results verbatim (including injected ones). Because recorded results do not mutate the
  environment, the trial is graded on `spec.replay_final_state`, and only if the agent consumed the
  recording exactly (every recorded call, in order, nothing left over). A miss OR leftover
  recording => outcome `ERROR`, termination `replay_miss`. The ToolBox must latch a replay miss in a
  flag the agent cannot clear: an agent that catches `Exception` must not turn a miss into an
  ordinary failure.
- A raising toolset factory or an unresolvable agent reference is a harness fault (`ERROR`,
  `harness_error`). A raising or unresolvable oracle is `ERROR`, `grader_error`.
- Bundles are portable: `make_bundle(manifest, trial, spec, *, root=None, include=())` embeds each
  `include` path (relative to `root`) as base64 in `files` and its sha256 in `fixtures`. `replay`
  first checks every embedded file against `fixtures` (mismatch => `INVALID`, nothing executed),
  writes them to a temp dir, and puts that dir FIRST on the child's import path.
- `replay(bundle)`: bad seal (including a nested one) => `INVALID`. `tool_mode` REPLAY serves results from
  `spec.recording` keyed by (tool, sha256 of canonical arguments, occurrence); a miss raises
  `ReplayMiss` => `INVALID`. `tool_mode` RECORD in a bundle means "run live against the seeded
  fixture environment" (used to show a repaired agent no longer fails). `REPRODUCED` iff outcome
  and fingerprint both equal the bundle's expectations.
- The gate counts a success as `outcome is PASS`. See `docs/STATISTICS.md` for the rule.
