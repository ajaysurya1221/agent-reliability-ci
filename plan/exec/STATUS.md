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
| 03 | REVISE r1 pending | Fable ACCEPT (withdrawn pending r1), reviewer-subagent ACCEPT (minors), Astra REVISE (1 MAJOR: unordered YAML collections → nondeterministic seals; 3 MINOR) | isolated just check at e962259: exit 0 | e962259 on sprint/descriptor | coder 17 min; r1 to be dispatched after T04+T05 on the same lane |
| 04+05 | REVISE r1 pending | Fable ACCEPT, reviewer-subagent REVISE (2 required), Astra REVISE (2 MAJOR, 3 MINOR; ADR 0006/0008 amended) | 76523e5 on sprint/descriptor | coder 26 min; isolated just check at 76523e5: exit 0 (1035 passed); r1 after T03r1 |
| 03 (final) | ACCEPTED | Fable ACCEPT, reviewer-subagent ACCEPT (r1), Astra ACCEPT (r2) | 314cbbd on sprint/descriptor | three rounds total (T03, r1, r2); 1164 tests green on the lane |
| 04r1 | ROUND 2 IN PROGRESS | reviewer-subagent ACCEPT (r1), Astra REVISE (r1: O_EXCL fallback) → T04r2 dispatched 06:34Z | b45cdda on sprint/descriptor | last round; fail-closed publication, fsync, descriptor add-ons |
| 04r2 | DONE, MERGED | reviewer-subagent ACCEPT (r2), Astra ACCEPT (r2); Fable ACCEPT | 4451a90 on sprint/descriptor → main | isolated just check exit 0 (1198 passed, 2 skipped); coder 13 min; 3 reviewer follow-ups + fsync-durability note → FINAL_REPORT |
| 08+09 | DONE, MERGED | Fable ACCEPT, reviewer-subagent ACCEPT (r1), Astra ACCEPT (r1) | 9dd9f5e on sprint/recipes (pushed) | T08r1 coder 7 min; 18 recipe tests green; confirmatory run recorded (390/400 vs 296/400 BLOCK, 96.65 s) | coder 17 min; 9 recipe tests green; recorded run and the Inspector result pasted by the orchestrator; Inspector step blocked by SDK 1.29.0 (D-03) |
| 11 | DONE, MERGED | reviewer-subagent ACCEPT, Astra ACCEPT (round 1) | b34dac1 on sprint/readme (pushed) | all links absolute; first screen 191 words; merge right after the descriptor lane |
| CI note | — | — | d797af9, c79538a | main CI red on two plan-only commits (ruff on plan/exec/scripts/readme_release_pins.py); fixed in cbd8d20 |
| V (07:05Z) | GREEN | Fable | main f0915f9 (lanes C, README, recipes merged) | isolated: just check 1216 passed, 2 skipped (8:39); figures current; schema current; first screen 191 words; wheel built; `uvx --from <wheel> arci demo --workers 4` from an empty dir: All six steps held, exit 0; lane CI 4451a90 success → main pushed |
| 12 | DONE, MERGED | r1: reviewer REVISE, Astra REVISE → T12r1; r2: reviewer-subagent ACCEPT, Astra ACCEPT (both: httpcore2 typo → next re-freeze) | 5142d66 on sprint/release → main | isolated just check 1216 passed at 3ca5794 (delta md + ADR/FROZEN); merge bar on the merge commit below (V) |
| V (07:41Z) | GREEN | Fable | main 68f7c8c (release merge; head 48e60ac pushed 07:30Z) | isolated: just frozen 53 OK; uv lock --check OK; just check 1216 passed, 2 skipped (7:55); figures current; schema current; reproduce 0 failed of 6; arci 0.8.0; wheel sha 10ddc682…2899 (same bytes as the main-checkout build), sdist 99476b7b…9a01 (41 files: src/arci + README, LICENSE, NOTICE, CHANGELOG, pyproject, .gitignore, PKG-INFO); `uvx --from <wheel> arci demo --workers 4` from an empty dir: All six steps held, exit 0 (2:04 wall) |
| 13 | DONE, RELEASED | reviewer-subagent ACCEPT (r2), Astra ACCEPT (r2) | tag v0.8.0 = 48e60ac; PyPI 0.8.0 attested 08:25Z; release page 08:27Z (user); sprint/t13-docs e9f55ce → main de09b1d | release run 38365660814 green after the publish re-run; receipts: Track A wheel 80/72/73 s, PyPI 76 s cold / 99 s warm, Track B 3 s; cold read 5/5 |
| 14 | REVIEWS IN PROGRESS | reviewer-subagent + Astra | sprint/t14-docs (README availability: published; PyPI-route receipt) | docs only |
