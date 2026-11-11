**Rerun acceptance outside the sandbox before approving P4c.** All eight fixes are implemented.

1. Changed `action.yml`, `.github/scripts/pr_comment.py`, `src/arci/{html_report,storage}.py`, and README Action guidance/stale HTML wording.
2. Added regression tests under `tests/unit/{html_report,examples,storage}`; updated HTML goldens and `docs/results/sample-suite-report.html`. All six artifacts show `ARCI 2.0.0`.
3. Focused regression command:
   ```sh
   .venv/bin/pytest tests/unit/html_report tests/unit/storage tests/unit/examples/test_final_action_fixes.py tests/unit/examples/test_pr_comment.py -q -o addopts=''
   ```
   Last line: `120 passed in 4.19s`.
4. Required focused acceptance: **363 passed, 1 failed** (`PermissionError`). Full `LANGSMITH_TRACING=false .venv/bin/pytest -q`: **3,004 passed, 66 failed, 2 skipped**. Failures involve socket/process restrictions; one test interrupted by my interrupt attempt passed separately. [Full log](/tmp/p4c-full-pytest.log).
5. Formatting/lint passed; basedpyright: `0 errors, 0 warnings, 0 notes`. All **65 frozen hashes match**. Order-desk HTML unchanged. Remaining risks: unrestricted acceptance and **360 px visual QA**, which browser access restrictions prevented.