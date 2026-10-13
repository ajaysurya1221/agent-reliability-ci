REVIEW 03r1 — Reviewer Astra | Verdict REVISE

**Findings by severity**

1. **MINOR — Unsealable integers still escape as bare `ValueError`.** At [descriptor.py:863](/Users/ajay/Developer/.arci-worktrees/wt-descriptor/src/arci/descriptor.py:863), `json.dumps` is outside the descriptor-error protection. Reproduced with `task.x` containing `0x1` followed by 3,600 zeros: both library entry points raise Python’s integer-conversion-limit error. CLI returns 3 with empty stdout, but stderr omits the filename and `task.x`. Required change 2 remains incomplete.

2. **MINOR — Simultaneous alias conflicts are not all collected.** [descriptor.py:372](/Users/ajay/Developer/.arci-worktrees/wt-descriptor/src/arci/descriptor.py:372) returns the `id`/`condition_id` conflict before checking `fault`/`faults`. A condition containing both conflicts plus unknown `g` reports `conditions[0].g`; the promised sorted-first error is `conditions[0].fault`. Required change 4 remains incomplete. The raw-input-pass approach is acceptable; its early return is the defect.

3. **MINOR — Shared aliases bypass the documented depth limit.** [descriptor.py:303](/Users/ajay/Developer/.arci-worktrees/wt-descriptor/src/arci/descriptor.py:303) skips previously visited nodes without accounting for their depth at the new location. A task defining `a0: &a0 []`, then `aN: &aN [*a(N-1)]` through `a101`, successfully seals with a container path 103 levels deep despite `MAX_DEPTH = 100`.

**Required changes**

1. Reject unencodable scalars at their source path and wrap serialization failures in `DescriptorError`; add library and CLI regressions for the hexadecimal case.
2. Collect every independent condition shorthand violation before sorting; test simultaneous conflicts with and without another field error.
3. Check alias subtree depth at every use, using cached subtree heights if needed; retain acceptance of shallow shared aliases.

**Follow-ups**

- Independently verified at `58e71c5`: unordered collections rejected; seals and argument ordering identical across three hash seeds; structural paths correct; original malformed-scalar and `oracle`/`zzz` cases fixed. Retry and full 182-command guardrail manifests exactly match their builders. No seal divergence appeared in the additional 2,000-float comparison.
- Supplied diff matches; all 48 frozen hashes and schema bytes pass. Global SafeLoader tables and `contracts.load_contract` remain unchanged. No files changed.
- Snapshot-loaded `.venv/bin/python -B -c …` pytest run: **`118 passed, 10 skipped in 0.96s`**. Ruff format/check passed. Filesystem integration, full-suite and exact-commit basedpyright checks were not independently rerun. Next: add the large-integer regression first.

