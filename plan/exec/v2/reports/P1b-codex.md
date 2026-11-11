**P1b implemented. Full-suite acceptance needs an unrestricted rerun.**

Files created:

- [suite_gate.py](/Users/ajay/Developer/.arci-worktrees/wt-v2-suite/src/arci/suite_gate.py)
- [selfcheck_suite.py](/Users/ajay/Developer/.arci-worktrees/wt-v2-suite/bench/selfcheck_suite.py)
- [STATISTICS_SUITE.md](/Users/ajay/Developer/.arci-worktrees/wt-v2-suite/docs/STATISTICS_SUITE.md)
- [gate tests](/Users/ajay/Developer/.arci-worktrees/wt-v2-suite/tests/unit/suite/test_gate.py) and [bench tests](/Users/ajay/Developer/.arci-worktrees/wt-v2-suite/tests/unit/selfcheck/test_selfcheck_suite.py); extended [helpers.py](/Users/ajay/Developer/.arci-worktrees/wt-v2-suite/tests/unit/suite/helpers.py).

No existing tracked files changed. P1a’s schema, schedule and statistics modules remain unchanged.

| Required command | Result / final output |
|---|---|
| `.venv/bin/pytest tests/unit/suite tests/unit/selfcheck -q` | **260 passed**, `[100%]`, exit 0 |
| `.venv/bin/python -m bench.selfcheck_suite` | `All suite checks PASS`; **155.329 seconds** |
| `.venv/bin/pytest -q` | **1549 passed, 65 failed, 2 skipped**, exit 1 |
| `.venv/bin/ruff format --check .` | `468 files already formatted` |
| `.venv/bin/ruff check .` | `All checks passed!` |
| `.venv/bin/basedpyright` | `0 errors, 0 warnings, 0 notes` |
| `shasum -a 256 -c FROZEN.sha256` | All **54 OK**; final line `uv.lock: OK` |

Largest observed errors in the bench’s finite grid—all below 2.5%:

| Cells | False PASS | False BLOCK |
|---:|---:|---:|
| 1 | 2.120015% | 2.108238% |
| 2 | 1.902109% | 1.909437% |
| 5 | 1.623802% | 1.607206% |
| 10 | 1.389777% | 1.382461% |
| 20 | 1.122453% | 1.146505% |

All eight large-grid projections completed. The 20-cell, 20-round gate took **47 ms**.

Full-suite failures are in existing tests. Confirmed sandbox failures include `test_http_upstream_gets_the_real_key_and_the_pinned_model` (socket permission) and `test_timeout_mid_call_keeps_the_trace_and_kills_the_whole_process_tree` (`ps` permission). [Full failure log](/tmp/p1b-full.log).

No contract gaps or proof defects identified. Remaining risk: full-suite acceptance is unverified.

**Next: orchestrator runs `.venv/bin/pytest -q` outside the sandbox.**