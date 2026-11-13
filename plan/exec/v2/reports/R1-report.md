Review the [updated sample report](/Users/ajay/Developer/.arci-worktrees/wt-v2.1/docs/results/sample-suite-report.html). **R1 is implemented.**

1. **Files changed:** `report.py` (additions only), `suite_report.py`, `html_report.py`; three new test files; eight suite goldens; sample HTML; LangChain recipe paragraph. v1 byte pins pass, including 19 JSON pins captured before runtime edits.

2. **Focused tests:**  
   `.venv/bin/pytest tests/unit/{suite_report,html_report,report,reports,suite_cli} -q` → **345 passed**, ending `[100%]`.  
   `.venv/bin/pytest tests/unit/tool_outcomes_blind -q` → **51 passed**, ending `[100%]`.

3. **Full suite:** `LANGSMITH_TRACING=false .venv/bin/pytest -q` → **2,749 passed, 65 failed, 5 skipped**. Failures match the documented socket/`ps` restrictions; no additional category identified. Last line: `FAILED …test_diff_minimize_bundle_and_replay`.

4. **Required checks:** Ruff format → `554 files already formatted`; Ruff check → `All checks passed!`; basedpyright → `0 errors, 0 warnings, 0 notes`. Frozen verification: **65/65**, ending `uv.lock: OK`.

5. **Limits/risks:** Full-suite acceptance remains sandbox-limited. Browser preview was unavailable. Version remains 2.0.0; unrelated edits and blind tests were untouched.

Next: inspect the [full-suite failure log](/private/tmp/r1-full.log) before the orchestrator’s unrestricted rerun.

