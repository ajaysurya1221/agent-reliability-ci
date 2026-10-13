Accept the delta: the round-3 item is resolved at `d2557fa`.

The reserve covers `120 + 60 + 120 + 60 + 60 = 420 s`; probe admission requires that same 420 seconds. The combined assertions match the workflow timeouts. Verified: `2400 − 420 = 1980`; remaining budgets are 4 and 480 seconds. The conservative setup claim totals `240 + 1575 + 120 + 420 = 2355 ≤ 2400`.

Targeted test: `.venv/bin/pytest -q -s -p no:cacheprovider plan/exec/scripts/test_reference_stats.py::test_workflow_design_values` → `.`, exit 0.

Nonblocking: [workflow comments](/Users/ajay/Developer/.arci-worktrees/wt-t18/.github/workflows/ttfv-reference.yml:40) retain old arithmetic at lines 40–41 and 79. No files changed; full dry-runs and hosted execution unverified.

VERDICT 18 delta: ACCEPT