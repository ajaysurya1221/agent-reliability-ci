# TASK P2a: suite runner, store, descriptor and `arci run` / `arci gate`

Lane A. Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-suite` (branch `v2/suite`).
Phase 1 is committed and frozen there: `suite_schema.py`, `suite_schedule.py`,
`docs/STATISTICS_SUITE.md`, `docs/design/0011-suite-gate.md` and the suite acceptance tests
are now FROZEN (see `FROZEN.sha256`). `suite_stats.py` and `suite_gate.py` are not frozen
but are pinned by those tests. Work only in the worktree. No git command that changes
state. No network. No new dependency.

Read first: `AGENTS.md`; `docs/design/0011-suite-gate.md` items 9, 10, 12 and its
amendments; `docs/STATISTICS_SUITE.md`; `docs/AGENT_SEMANTICS.md`; `src/arci/runner.py`,
`storage.py`, `descriptor.py`, `cli.py`, `worker.py`, `gate.py`, `demo/`; the contract
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md`.

## You own

New: `src/arci/suite_runner.py`, `src/arci/suite_storage.py`, `tests/unit/suite_runner/`,
`tests/unit/suite_cli/`, a seeded offline fixture under `src/arci/demo/` (new files only)
or `tests/unit/suite_runner/fixtures/`. Edit: `src/arci/descriptor.py`, `src/arci/cli.py`
(and `src/arci/runner.py` only to expose an existing private helper without changing
behaviour; say which). Every v1 behaviour, test and record stays byte-identical.

## Build

1. **Store** (`suite_storage.py`): a suite run directory holds `manifest.json` (the sealed
   `SuiteManifest`), `trials.jsonl`, `events.jsonl` and, when decided, `decision.json`,
   mirroring v1's layout so existing readers of trials and events work. Creating a store
   refuses unless `manifest.validate_seal()`, `experiment_id == suite_experiment_id(manifest)`
   and `check_suite_plan(manifest)` passes: the experiment id names the directory, so it is
   never trusted. `load_suite_run(dir)` returns manifest and trials; a loader helper tells a
   suite store from a v1 store by the manifest's `schema_version` without guessing.
2. **Runner** (`suite_runner.py`): `run_suite(manifest, out_dir, *, workers, ...)`.
   - One stage is one round. Submit a whole round, wait for all of it, append it, then call
     `suite_gate.evaluate_rounds`; stop at the first round whose verdict is not
     INCONCLUSIVE or at `max_rounds`. There is no other look. Then write the sealed
     `decide_suite` decision.
   - **The unit of scheduling is the pair.** One worker slot runs both arms of a pair back
     to back, in the order given by `suite_schedule.arm_order`; pairs run in parallel
     across slots. Reuse v1's `run_trial` for each trial unchanged.
   - Before any trial: `check_suite_plan`, printing its warnings. Trials are appended in a
     deterministic order (schedule order) once the round is complete, so the store's bytes
     do not depend on thread timing apart from volatile fields.
   - An errored pair is stored as it is; the gate scores it. The runner never re-runs a
     trial inside an experiment. If `evaluate_rounds` returns ERROR, stop.
   - A run interrupted mid-round leaves a partial round; `arci gate` on it is ERROR by
     contract. Do not add resume.
   - `prior_runs`: when the out directory already holds earlier suite runs for the same
     `suite_id` and candidate, the descriptor path records their experiment ids into
     `prior_runs` before sealing (as v1 does for its own runs; follow v1's rule).
3. **Descriptor** (`descriptor.py`): `arci.yaml` may declare a suite. Keep v1 descriptors
   byte-for-byte as they are. A suite descriptor has `tasks:` (a list of `{id, ...task
   fields}` or a path to a JSON/YAML/JSONL file), the same agent, toolset, check and faults
   keys v1 uses, and an optional `rule:` block with `alpha`, `delta`, `stakes`,
   `max_rounds`, `scenario_seeds`, `max_errored_pairs`, `acknowledge_single_round`.
   Rationals are written `1/20`; a decimal such as `0.05` is accepted only when it converts
   exactly to a rational within the schema's digit bound, else a clear error. Defaults come
   from `suite_stats.default_max_rounds` and `default_max_errored_pairs`. Fault conditions
   map to cells as v1 maps faults to conditions (one clean condition plus one per fault,
   unless v1 does it differently: follow v1). Every error names the key and the fix.
4. **CLI** (`cli.py`): `arci run` on a suite descriptor runs the suite and exits with the
   decision's exit code; `arci gate <run-dir>` re-derives the decision for a suite store
   with `decide_suite`, compares it with the stored one, and prints verdict, stopping
   round, pairs, counts, both wealths against the threshold, errored pairs against the
   tolerance, and the guarantee sentence for the sealed seed mode (the `per_round`
   condition verbatim from `docs/STATISTICS_SUITE.md`). `report`, `triage`, `diff`,
   `minimize`, `bundle`, `replay`, `trace-check` and `plan` on a suite store or descriptor
   exit 3 with one line saying suite support for that command is not built yet (the next
   task adds report, triage, diff and plan). They keep working on v1 stores.
5. **Fixture**: a 20-cell seeded suite with no model call (for example 5 tasks by 4
   conditions over the existing demo environment, or a new tiny one) with three agents: a
   control equal to the baseline, a planted regression, and one for INCONCLUSIVE. Agents
   draw their randomness from the trial seed, so the fixture declares
   `scenario_seeds: per_round`.

## Tests

- Runner: PASS for the control, BLOCK for the planted regression, INCONCLUSIVE for a
  deliberately small `max_rounds` (exit codes 0, 1, 2); the run stops at the first decisive
  round and stores exactly rounds 1 to r; `decide_suite` on the stored run equals the
  stored decision; both arms of a pair ran in the same worker slot in `arm_order` (assert
  from event timestamps or an injected recorder, not by sleeping); two runs with the same
  manifest give identical non-volatile content; a harness error in one pair below the
  tolerance is scored, above it is ERROR; an interrupted round gives ERROR at the gate.
- Store: refuses a manifest with a wrong or malformed `experiment_id`, a broken seal or an
  invalid plan; never creates a directory outside `out_dir`.
- Descriptor: every key, every error message, defaults, rationals and decimals, tasks from
  a file; v1 descriptor tests untouched and green.
- CLI: end-to-end `arci run` and `arci gate` on the fixture through `subprocess`; the
  deferred commands exit 3 with the message; v1 CLI tests untouched and green.
- Keep the whole new test set under about three minutes; use few workers and short trials.

## Acceptance (from the worktree root)

```sh
.venv/bin/pytest tests/unit/suite_runner tests/unit/suite_cli tests/unit/descriptor tests/unit/cli -q
.venv/bin/pytest -q
.venv/bin/python reproduce.py --check --strict     # if present at the root; v1 must stay 6 of 6
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright
shasum -a 256 -c FROZEN.sha256                      # 63 entries
```

Sandbox: tests that fail only on sockets or `ps` are the orchestrator's to re-run; name
them. If trials cannot spawn at all in your sandbox, say so at once and give the commands
the orchestrator should run.

Also deliver, as a plain file `plan-notes/AGENT_SEMANTICS_suite_section.md` in the worktree
root (not under `docs/`): the text of the new section for the frozen
`docs/AGENT_SEMANTICS.md` describing suite experiments as you built them (schedule, pair
scheduling, round stage, errored-pair scoring, round-end priority, that the v1 scheduler
rule applies to `arci/0.5` only). The orchestrator adds it at the next re-freeze.

Stop and report if a frozen file or the contract blocks you. Report under 60 lines: files;
command tails; design choices you made where this brief was silent; what the orchestrator
must re-run; risks.
