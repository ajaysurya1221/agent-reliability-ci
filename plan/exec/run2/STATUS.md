# Run 2 STATUS

Budget clock start (Task 00 commit): 2026-10-13T18:12:20Z. Stop starting tasks at +7h15m. Budget end: +8h.

| Task | State | Reviewers | Commit | Notes |
|---|---|---|---|---|
| 00 | DONE | none | (this commit) | plan persisted; worktrees wt-t16, wt-t17 |
| 16 | CODING | Fable + reviewer + Astra | sprint/t16-code (wt-t16) | dispatched 18:14Z with T17 (Workflow, Opus high) |
| 17 | CODING | Fable + reviewer | sprint/t17-protocol (wt-t17) | dispatched 18:14Z |
| 18 | QUEUED | Fable + reviewer + Astra | sprint/t18-refmachines | brief written; starts when a coder slot frees |
| 19 | DONE (check; D-11 corrected per Astra) | Astra DISAGREE r1 on the preservation claim → D-11 rewritten: standalone compatibility mode, trial traffic untouched, tests pin trial responses; ADR 0011 next run | plan/exec/DECISIONS.md D-11 | no SDK supports 2026-07-28 (sdk 1.32.1, core 2.2.0 → 2025-11-25) |
| 20 | DESIGN v2 IN REVIEW | Astra REVISE r1 → draft v2 (provenance states, conservative capabilities, ordering, volatile imported_at, seal binds importer config); r2 dispatched | plan/exec/run2/adr-0010-draft.md, fixtures.md | fixtures 2 and 3 accepted conditionally as authentic (offline replay of real instrumentations), must show tool identity/order |
