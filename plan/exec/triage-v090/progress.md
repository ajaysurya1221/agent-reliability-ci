# SDD ledger — plan: plan/exec/triage-v090/PLAN.md

Start: 2026-11-05 18:17 UTC. Base f039e1ddd07011a6018b88171cb51d5be3d63b26.
Hard elapsed-working budget: 16 hours. The operator approved the whole plan and release.

## Preflight

| Task/interface | Producer/consumer | Check and resolution |
|---|---|---|
| Core | triage/context/tests | No frozen schema changes. Selected context uses comparator presence, not new equality. |
| CLI | CLI/smoke/tests | Gate exits differ from report's success exit by approved design. Legacy behavior stays intact. |
| Core -> CLI | triage_run, render_triage, result.exit_code | Shared signatures and JSON envelope fixed in PLAN. Disjoint owned files. |
| Core -> docs | observed text and JSON | Docs use actual final output, never fabricated transcript. |
| CLI -> package | shared smoke script | Both CI and release test the same installed command. |
| Docs/release | version/frozen metadata | Approved narrow packaging re-freeze only. No dependency resolution changes. |
| Review -> delivery | exact candidate | Any source/base changes invalidate prior candidate acceptance. |

Ruling: use ordinary Git worktree at `.arci-worktrees/triage-v090` after the native
creation call did not return a result and was terminated — verified isolation is
available now — cost if wrong: native app bookkeeping may not reflect the checkout.

Ruling: honor the approved two parallel code lanes despite the skill's serial-worker
default — file ownership is disjoint — cost if wrong: integration rework, caught by
independent whole-branch checks.

Ruling: retain execution records/worktree instead of deleting skill scratch at finish
— the approved plan requires historical evidence — cost: retained disk usage.

Ruling: APFS-copy and repoint the existing installed environment for worker tests
— avoid resolving dependencies before work — cost if wrong: environment dependence,
addressed by fresh wheel and hosted matrix checks.

Baseline: local/remote main f039e1d; latest GitHub/PyPI 0.8.0; requested 0.9.0 unused.
PyPI environment exists with tag branch policy and no reviewer rule. Installed uv
0.12.5 available to orchestrator for approved lock re-freeze. Isolated environment
imports this worktree; 120 existing comparison/CLI tests pass.

## Tasks

1. Baseline and briefs: complete. 272 protected-file hashes captured.
2. Core and CLI lanes: in progress.
3. Review and independent agent QA: pending.
4. Final local/hosted verification and merge: pending.
5. Release and downloaded-artifact verification: pending.
