# CLI and installed-wheel lane report

Implemented on 2026-11-03 within Lane B ownership. No Git mutations, network,
dependency installation, frozen-file edits, or changes to another lane's files.

## Changes

- `src/arci/cli.py`: one comparator import, parser registration, and dispatch;
  command accepts both native stores and selected trial IDs plus `--format`.
  Existing `diff` implementation is untouched.
- `tests/unit/cli/test_trace_check.py`: native sealed-store CLI integration,
  legitimate no-tool traces, MATCH/DRIFT/INVALID and JSON contract, missing and
  malformed input, flag errors, source/summary write checks, text/statistical
  separation, legacy diff parity, and all 12 CI exit-code compositions.
- `.github/scripts/wheel_smoke.sh`: clears inherited `PYTHONPATH`, enables safe
  import paths, retains the packaged demo stores under its existing temporary
  root, and invokes the helper with the installed Python `-P`.
- `.github/scripts/trace_check_smoke.py`: checks installed-package origin and
  execution outside the checkout, selects scenario-compatible real demo traces,
  verifies MATCH/0, DRIFT/1, INVALID/3, validates the versioned JSON allowlists and
  source identities against stored seals/decisions, checks no raw demo payloads,
  and verifies all demo-file hashes and absent `GITHUB_STEP_SUMMARY` output.

The installed MATCH comparison deliberately compares baseline A from the A-vs-A
PASS store to baseline A from the A-vs-B BLOCK store. It requires diagnostic
MATCH while preserving each source's independent gate verdict. DRIFT compares
that same A baseline with the paired failing B trace at the same seed. INVALID
selects an absent candidate trial. No checkout tests or user modules are imported
by the helper.

## Red evidence

Before CLI wiring, `.venv/bin/pytest tests/unit/cli/test_trace_check.py` produced
`2 failed in 0.21s`: help exited 3 because `trace-check` was an unknown command;
the missing-store JSON test received the parser error on stderr instead of a
structured INVALID result. This was the expected new-command failure.

## Green validation

Command:

```text
.venv/bin/pytest tests/unit/cli/test_trace_check.py tests/unit/cli/test_cli.py
```

Last lines:

```text
......................................                                   [100%]
38 passed in 1.18s
```

The 12 recipe cases execute the actual marked Bash block in
`docs/recipes/trace-check.md` under `bash -eu`, covering gate exits 0/1/2/3
crossed with trace exits 0/1/3. Arguments containing spaces verify quoting. A
nonzero gate always remains nonzero, including BLOCK and INCONCLUSIVE with MATCH;
trace failure governs only after a green statistical gate. These are composition
tests with a CLI stub, separate from the real native-store CLI integration tests.

Final owned-file checks:

```text
.venv/bin/ruff format src/arci/cli.py tests/unit/cli/test_trace_check.py .github/scripts/trace_check_smoke.py
3 files left unchanged
.venv/bin/ruff check src/arci/cli.py tests/unit/cli/test_trace_check.py .github/scripts/trace_check_smoke.py
All checks passed!
.venv/bin/ruff format --check src/arci/cli.py tests/unit/cli/test_trace_check.py .github/scripts/trace_check_smoke.py
3 files already formatted
.venv/bin/basedpyright src/arci/cli.py tests/unit/cli/test_trace_check.py .github/scripts/trace_check_smoke.py
0 errors, 0 warnings, 0 notes
bash -n .github/scripts/wheel_smoke.sh
exit 0
```

## Limits and remaining integration evidence

This lane did not build/install dependencies or execute the full demo, wheel
smoke, full pytest suite, or hosted matrix. The integrator owns those acceptance
runs; this report is implementation evidence, not acceptance or release approval.
The helper's real installed-wheel assertions still require the integrator's run.
No change to the frozen statistical decision rule or legacy diff was made.
