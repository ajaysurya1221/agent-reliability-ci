# Lane B: triage CLI and installed-package smoke

Scope: approved Task 2 brief, source base `16e8a1a`. Only the five owned paths
were edited. No Git mutation, network access, dependency changes or subagents.

## Changes

- `src/arci/cli.py`: register `triage RUN_DIR [--trial CANDIDATE_ID]
  [--format text|json]`. Dispatch calls only shared `triage_run` and
  `render_triage`, then returns `result.exit_code`. Help states unchanged gate
  exits, diagnostic INVALID/3, root-cause limits and possible disclosure.
- `tests/unit/cli/test_triage.py`: real sealed stores with deliberately
  unimportable recorded agent/oracle references; no engine mocks. Cover help,
  argument errors, text/JSON, all gate exits, explicit PASS selection, DRIFT with
  PASS/0 and INCONCLUSIVE/2, baseline/missing/nonunique selectors, malformed
  selected events/store JSON, withheld payloads, source hashes and no summary
  writes. Fixture gate verdicts are independently checked before CLI calls.
- `.github/scripts/triage_smoke.py`: stdlib plus installed ARCI only, outside
  checkout, `-P`, cleared PYTHONPATH and verified installed import provenance.
  Reuses demo stores for PASS/0, BLOCK/1, INCONCLUSIVE/2 and selector checks;
  derives sealed harness-ERROR/3 and PASS/0-with-DRIFT stores from existing records
  without executing recorded code. Checks exact shared envelope/nested fields,
  complete original gate, real manifest/trial/decision hashes, group counts,
  original pair outcomes and presence from comparator hashes. All source stores
  and GITHUB_STEP_SUMMARY stay unchanged. Run-level ERROR is INVALID/3 with its
  original ERROR/3 gate retained; a bad selector retains original BLOCK/1 while
  returning diagnostic INVALID/3.
- `.github/scripts/wheel_smoke.sh`: invoke the new installed helper immediately
  after the existing unchanged trace-check smoke, sharing the demo stores.

## TDD receipt

Before CLI implementation, `.venv/bin/pytest -q tests/unit/cli/test_triage.py`
reported 11 expected failures because `triage` was an unknown command; four
argument-error cases passed. No production plumbing preceded this red run.
After integration, a fixture omission of required trial_start identity payloads
was corrected; no core implementation or API change was required.

## Verification

- `.venv/bin/pytest -o addopts='' -q tests/unit/cli/test_triage.py`:
  `19 passed in 0.34s`.
- Final full CLI suite: `.venv/bin/pytest -o addopts='' -q tests/unit/cli`:
  `100 passed in 22.57s`.
- `.venv/bin/ruff format --check src/arci/cli.py tests/unit/cli/test_triage.py
  .github/scripts/triage_smoke.py`: `3 files already formatted`.
- `.venv/bin/ruff check` on the same files: `All checks passed!`.
- `.venv/bin/basedpyright` on the same files:
  `0 errors, 0 warnings, 0 notes`.
- `bash -n .github/scripts/wheel_smoke.sh`: exit 0.

Fresh-wheel smoke execution and the complete repository suite are owned by the
orchestrator after integration; this worker has not represented those as run.
The installed helper must run against the freshly built candidate wheel before
release. No frozen files or existing comparator smoke were edited by Lane B.
