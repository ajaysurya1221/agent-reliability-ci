**V5 implemented; acceptance is blocked by one stale, unowned test.** [test_cli.py:328](/Users/ajay/Developer/.arci-worktrees/wt-v2.2/tests/unit/outcomes/test_cli.py:328) still expects the removed placeholder response.

Files changed, all within ownership:

- `bench/export_outcomes.py`
- `src/arci/cli.py` — example branch only
- `src/arci/demo/outcomes/` — package and run-1 data
- `examples/outcomes/order-desk/` — README and both exports
- `tests/unit/outcomes/{test_example,test_export}.py`

Both exports reproduce stored verdicts, counts, and wealths exactly. The offline wheel contains the example; extracted-wheel and ZIP-import checks pass from an empty directory.

Verification:

```text
.venv/bin/pytest tests/unit/outcomes tests/unit/docs -q -o addopts='' --tb=line
1 failed, 271 passed in 2.17s
```

All 14 new tests pass. Ruff formatting/checks, strict basedpyright, secret scan, and frozen hashes pass.

`arci verdict --example` begins:

```text
Descriptive verdict: the rule file declares it was written after outcomes existed. The error bound is not claimed.
VERDICT: BLOCK (exit 1)
```

Example sizes in bytes:

| Run | baseline.csv | candidate.csv | rule.yaml |
|---|---:|---:|---:|
| 1 | 2,614 | 2,614 | 2,542 |
| 2 | 12,982 | 12,982 | 2,566 |

README: 1,838 bytes. Packaged run 1 is byte-identical.

No commits made, as required. **Next: the orchestrator must update the stale placeholder test before acceptance can pass.**

