Rerun `.venv/bin/pytest -q` outside the sandbox to complete acceptance. **P2a is implemented.**

1. **Files changed:** `src/arci/descriptor.py`, `src/arci/cli.py`; added `suite_runner.py`, `suite_storage.py`, `demo/suite.py`, and tests under `tests/unit/{suite_runner,suite_cli}/`. Delivered the [suite semantics section](/Users/ajay/Developer/.arci-worktrees/wt-v2-suite/plan-notes/AGENT_SEMANTICS_suite_section.md). No existing runner helper changed.

2. **Test results:**
   ```text
   .venv/bin/pytest tests/unit/suite_runner tests/unit/suite_cli tests/unit/descriptor tests/unit/cli -q -o addopts=''
   363 passed in 85.28s

   .venv/bin/pytest -q -o addopts=''
   65 failed, 2416 passed, 2 skipped in 384.56s
   ```
   The 65 failures involve existing socket/`ps` permission-dependent tests. [Exact failing names](/tmp/p2a-failures-final.txt) · [Verification details](/tmp/p2a-verification.txt).

3. **Checks passed:** Ruff formatting and lint; BasedPyright (`0 errors, 0 warnings`); **63/63 frozen hashes**. `reproduce.py` is absent, so its conditional check was not run.

4. **Design choices:** preserved the v1 compiler/schema and explicit conditions. Prior-run discovery matches candidate IDs, falling back to the complete arm when IDs are empty. Suite gate compares saved decisions without overwriting them, reports absent decisions, and refuses JUnit export.

5. **Remaining risk:** abrupt termination can lose the buffered active round; incomplete evidence gates ERROR. Resume is unsupported. Independent review findings were fixed; none remain deferred.

**Next:** the orchestrator runs the full suite with socket and process-inspection permissions.