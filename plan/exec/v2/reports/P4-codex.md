Review the [sample HTML report](/Users/ajay/Developer/.arci-worktrees/wt-v2-integration/docs/results/sample-suite-report.html). P4 is implemented.

Changed files:

- `src/arci/html_report.py`, `src/arci/cli.py`
- `action.yml`, `.github/scripts/{prepare_report,pr_comment}.py`
- `tests/unit/html_report/` including goldens and sample generator
- `tests/unit/examples/{test_pr_comment.py,pr_comments.json}`
- `docs/results/sample-suite-report.html`

Validation:

```text
.venv/bin/pytest tests/unit/html_report tests/unit/suite_report tests/unit/report tests/unit/cli -q
214 passed; [100%], exit 0

.venv/bin/pytest tests/unit/html_report tests/unit/examples/test_pr_comment.py -q -o addopts=''
24 passed in 4.39s

LANGSMITH_TRACING=false .venv/bin/pytest -q
2910 passed, 65 failed, 2 skipped; exit 1
```

Ruff formatting/lint and strict type checks passed. All **64 frozen hashes** match.

Full-suite failures include sandbox `PermissionError`s in existing boundary tests. Browser visual QA was blocked; live GitHub posting was not tested. Sticky comments require `pull-requests: write` and serialized PR runs to avoid concurrent creation.

Next: rerun the full-suite command outside the sandbox.