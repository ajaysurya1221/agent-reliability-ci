Review the 13-file diff: all eight fixes are implemented. Full acceptance still needs an unrestricted rerun.

1. **Fault accounting:** resolves custom factory names, separates duplicate declarations, retains unattributed injections. Tested in `suite_report/test_review_fixes.py`.
2. **Plan errors, cost, readability:** six error goldens match v1.0.0 byte-for-byte; default grids project successfully; Markdown uses six-place decimals and readable stakes. Tested in `planning/test_review_fixes.py`.
3. **Triage limitations and imports:** restored the empty-fixtures caveat; retained private imports because `trace_check.py` is outside ownership. Tested in `suite_cli/test_reports_diagnostics.py`.
4. **Report status and wording:** exposes saved-decision status, exits 3 on mismatch, and aligns JSON/Markdown guarantees and limitations. Tested by report regressions and four updated goldens.

Changed source: `src/arci/{cli,planning,report,suite_report,triage}.py`. Tests changed only under the three authorized test areas. Frozen files remain unchanged.

Commands and tails:

- `.venv/bin/pytest tests/unit/suite_cli tests/unit/suite_report tests/unit/report tests/unit/reports tests/unit/triage tests/unit/diff tests/unit/planning tests/unit/cli -q` → `[100%]`, exit 0; **548 tests**.
- Final CLI follow-up passed; final report follow-up ended **`38 passed in 5.39s`**. All **28 regression cases fail against pre-fix code**.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright` → `528 files already formatted`; `All checks passed!`; `0 errors, 0 warnings, 0 notes`.
- `shasum -a 256 -c FROZEN.sha256` → `uv.lock: OK`; **64/64 passed**.
- `LANGSMITH_TRACING=false .venv/bin/pytest -q` → **2,862 passed, 65 failed, 2 skipped**; exit 1. [Full log](/private/tmp/arci-p2b2-full.log). Failures include sandbox-denied socket operations and `ps`.

Limits: projection admission uses estimated cost; unavailable or slow custom factories report “cannot attribute.”

Next: rerun `LANGSMITH_TRACING=false .venv/bin/pytest -q` outside the sandbox.

