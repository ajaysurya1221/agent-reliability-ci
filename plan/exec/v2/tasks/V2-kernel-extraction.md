# V2: extract the round-walking kernel (ARCI v2.2.0, task T2)

You are the implementer. Work only in `/Users/ajay/Developer/.arci-worktrees/wt-v2.2`
(branch `v2.2/integration`). Read `AGENTS.md` there first and obey its hard rules: never edit a
file listed in `FROZEN.sha256`; no git commands that change state; no network; no new
dependencies; use `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/ruff`,
`.venv/bin/basedpyright` directly.

## Files you own

- `src/arci/suite_gate.py`
- `src/arci/suite_stats.py`
- new tests under `tests/unit/suite/` (new files only; do not edit existing tests)

Touch nothing else. Two untracked documents under `docs/` are being edited by someone else;
leave them alone.

## Why

v2.2.0 adds a second caller of the suite decision rule (a verdict from imported pass/fail
outcomes, design record `docs/design/0015-imported-outcomes.md`, section "Kernel extraction").
Both callers must use one kernel so they cannot drift. This task is a pure refactor: no suite
behaviour may change.

## What to build

1. In `src/arci/suite_gate.py`, public:

   ```python
   @dataclass(frozen=True)
   class RoundIncrement:
       minus: int
       zero: int
       plus: int
       errored: int
       candidate_hard_violations: int

   @dataclass(frozen=True)
   class RoundLook:
       round: int                      # 1-based
       pairs: int                      # round * rule.n_cells
       counts: SuiteCounts             # cumulative
       candidate_hard_violations: int  # cumulative
       pass_wealth: str
       block_wealth: str
       pass_crossed: bool
       block_crossed: bool
       verdict: Verdict
       reasons: tuple[str, ...]

   def walk_rounds(
       rule: SuiteRule, per_round_counts: Iterable[RoundIncrement]
   ) -> tuple[RoundLook, ...]: ...
   ```

   `walk_rounds` holds exactly what the loop in `evaluate_rounds` does today after a round's
   increments are known: cumulative count accumulation, one `RunningWealth` per direction advanced
   by the increments, both crossing flags (kept even when a higher-priority step overrides them),
   the verdict ladder of `_round_verdict` with `rule.max_errored_pairs` as the tolerance, and the
   stop after the first round whose verdict is not INCONCLUSIVE. It consumes at most
   `rule.max_rounds` entries. An empty iterable returns `()`. It validates nothing about trials.

2. `evaluate_rounds` keeps its signature and its exact output. It still groups trials by
   `pair_round`, stops at the first incomplete round, computes each complete round's increments
   (including the candidate hard-violation count, which also counts violations on errored
   trials, as `_Counts.add` does today), calls `walk_rounds`, and builds each
   `SuiteRoundDecision` from the `RoundLook` plus that round's `trials_sha256`. Because
   `walk_rounds` stops at the first decisive round, `evaluate_rounds` must not compute digests
   or raise for rounds after it in any way it does not today: check the current order of
   operations (the digest of a round is computed only for rounds actually walked) and keep it.

3. Everything else in `suite_gate.py` stays with its existing callers and keeps its behaviour:
   store validation, `_cells` (called by `decide_suite` over all supplied trials), ERROR
   construction (`stopped_at_round = 0` for every ERROR), the ERROR for trials stored after a
   decisive round, the ERROR for an early inconclusive stop, an incomplete trailing round
   producing no look, no complete round producing `()`.

4. In `src/arci/suite_stats.py`, public `check_rule_plan(rule: SuiteRule) -> tuple[str, ...]`
   with the body of `check_suite_plan`: the same `SuitePlanError` type, the same two messages in
   the same order (never-differs check first, then the tolerance check), the same warning
   tuple. `check_suite_plan(manifest)` becomes `return check_rule_plan(rule_of(manifest))`.
   `registered_pairs` is `n_cells * max_rounds`; confirm that against `SuiteManifest` before
   relying on it, and stop and report if it is not exact.

5. New unit tests in `tests/unit/suite/test_walk_rounds.py`:
   - `walk_rounds` on increments derived from the packaged demo suite's trials equals the
     history `evaluate_rounds` returns, field for field (apart from `trials_sha256`);
   - each rung of the ladder in priority order: errored above tolerance (ERROR), hard violation
     (BLOCK) even when PASS wealth has crossed, PASS, BLOCK, INCONCLUSIVE, and that crossing
     flags are reported under an overriding rung;
   - it stops at the first decisive round and ignores later entries; it never consumes more
     than `max_rounds` entries; empty input gives `()`;
   - `check_rule_plan` raises the same error text as `check_suite_plan` for a rule below the
     79-pair floor and for an unreachable tolerance, and returns the same warning for
     `max_rounds < 3`.

## Acceptance criteria

- `git status --short` shows only `src/arci/suite_gate.py`, `src/arci/suite_stats.py` and new
  files under `tests/unit/suite/` (plus the two untracked documents and fixtures that were
  already there).
- `.venv/bin/pytest tests/acceptance tests/unit/suite tests/unit/suite_cli tests/unit/suite_report tests/unit/suite_runner tests/unit/selfcheck tests/unit/stats tests/unit/gate -q`
  passes with no existing test file modified.
- Before changing any code, save the output of `.venv/bin/python -m bench.selfcheck_suite --quick`
  to a temporary file outside the repository; after your change the output is byte-identical.
  Report both SHA-256 values.
- `.venv/bin/ruff format --check`, `.venv/bin/ruff check` and `.venv/bin/basedpyright` are clean
  on the three paths you own (strict mode, no `# pyright: ignore`).
- `shasum -a 256 -c FROZEN.sha256` reports every file OK.

## Final message

Files changed; the test command and its last lines; the two selfcheck hashes; anything you could
not do or that looked wrong (especially any behaviour of `evaluate_rounds` you could not keep
exactly); risks. No long logs.
