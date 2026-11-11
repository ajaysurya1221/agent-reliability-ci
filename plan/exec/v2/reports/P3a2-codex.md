Review the [P3a2 report](tests/unit/adapters/evidence/p3a2-report.md): all **11 items implemented**, with changed files and per-item regression tests.

- **308 scoped tests pass**; all 11 mutation checks detect regressions.
- Ruff, both type checks, and **54 frozen hashes** pass.
- Graded-trial median: **2.372 → 0.880 seconds**, 12 trials each.
- Full suite: **1,633 passed, 65 failed, 2 skipped**. [Failure details](tests/unit/adapters/evidence/p3a2-full-suite-failures.json) identify outside-scope socket/`ps` dependencies.
- Replay remains limited: it does not verify the final answer or restore exception attributes.

Next: run `LANGSMITH_TRACING=false .venv/bin/pytest -q` outside the sandbox.