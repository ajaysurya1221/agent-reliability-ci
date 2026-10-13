# STATUS

Budget clock start (Task 00 commit): 2026-10-13T03:42:56Z. Hard stop for starting tasks: +9h15m. Budget end: +10h.

| Task | State | Reviewers | Commit | Notes |
|---|---|---|---|---|
| 00 | DONE | none | (this commit) | plan persisted |
| 01 | DONE | none | f4e9d64, bee149a | coder/reviewer defs, CONTRACT, consult 01 OK (1:45, 63k tokens), probe: claude-opus-5-5 effort high via Workflow agent(), worktrees wt-{demo,descriptor,package,recipes,measure}; main: uv sync, just frozen, figure check, gh auth, push dry-run, just check (883 passed, 6:06) all pass; GitHub env `pypi` created |
| 02 | MERGED | Fable ACCEPT, reviewer-subagent ACCEPT | 2ae4bfd (merged to main 04:10Z) | coder 15.5 min; lane just check 894 passed 2 skipped in 6:14; wheel smoke from empty dir 1:12 exit 0 |
| 02b | MERGED | Fable ACCEPT, reviewer-subagent ACCEPT | be21582 (merged 04:22Z) | coder 3.5 min; lane just check green |
| 06+07 | MERGED | Fable ACCEPT, reviewer-subagent ACCEPT, Astra ACCEPT | 43b220b (+ NIT fix), merged 04:49Z | coder 9 min; CI on the lane all green (wheel smoke ×4, Windows install-only, Action fixture BLOCK); `pypi` environment restricted to tags v* |
| 10 | MERGED | Fable ACCEPT, reviewer-subagent ACCEPT (round 2) | 961bae7 (merged 04:37Z) | coder 5 min + two revision rounds (1.5 + 1.2 min); docs only |
| 03 | REVISE r1 pending | Fable ACCEPT (withdrawn pending r1), Astra REVISE (1 MAJOR: unordered YAML collections → nondeterministic seals; 3 MINOR), reviewer-subagent running | e962259 on sprint/descriptor | coder 17 min; r1 to be dispatched after T04+T05 on the same lane |
| 04+05 | IN PROGRESS | — | — | init + smoke-notice coder dispatched 04:53Z on the same lane (wf: task-04-05-init-smoke) |
| 11 | DRAFTED | — (reviews after T03/T04 merge) | sprint/readme (committed) | Fable-authored per ADR 0009; first screen 191 words; figure check passes; merge after `arci init` lands |
| 12 | DRAFTED | — (reviews at the end) | sprint/release c5d091d (pushed) | ADR 0005, pyproject metadata + 0.8.0, uv.lock, FROZEN re-freeze (53 lines), CITATION, __init__, CHANGELOG v0.8.0 draft with one placeholder, ROADMAP; wheel 116 KB, sdist 119 KB; lane just check running |
