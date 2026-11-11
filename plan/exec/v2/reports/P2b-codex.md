Rerun full acceptance outside the sandbox; **P2b is implemented**.

Changed [cli.py](/Users/ajay/Developer/.arci-worktrees/wt-v2-reports/src/arci/cli.py), [report.py](/Users/ajay/Developer/.arci-worktrees/wt-v2-reports/src/arci/report.py), [suite_report.py](/Users/ajay/Developer/.arci-worktrees/wt-v2-reports/src/arci/suite_report.py), [triage.py](/Users/ajay/Developer/.arci-worktrees/wt-v2-reports/src/arci/triage.py), and [planning.py](/Users/ajay/Developer/.arci-worktrees/wt-v2-reports/src/arci/planning.py). Updated suite/planning tests and v1 report goldens. Existing v1 Markdown bytes remain unchanged apart from fault accounting.

```sh
.venv/bin/pytest tests/unit/{suite_cli,suite_report,report,reports,triage,diff,planning,cli} -q -o addopts=''
```

Last line: **`521 passed in 87.11s (0:01:27)`**

- Ruff format/check: clean.
- Basedpyright: `0 errors, 0 warnings, 0 notes`.
- All 64 frozen hashes pass; last line: `uv.lock: OK`.
- Full run: 2,828 passed, 65 failed, 2 skipped. Failures involve decision/MCP/process tests, with socket and `ps` permission errors and downstream assertions. Full acceptance is unverified.

Limits: large projections return floors only. Three documented type ignores reuse `_valid_events`, `_projection`, and `_first_difference` from the unowned trace-check module.

Next: run `LANGSMITH_TRACING=false .venv/bin/pytest -q` outside the sandbox.