# Decisions log

Tie-break order: (a) the run prompt; (b) the memo; (c) the repo's rules; (d) an Astra consult seeing both positions; (e) the more reversible option. Every tie-break becomes an ADR in docs/design/.

## Decisions made at plan time (2026-10-13) (rule in brackets: a=prompt, b=memo, c=repo rules, d=Astra, e=reversibility)

1. The memo lives outside the repo; Task 00 copies it verbatim to `plan/research/forward-plan-2026-10-13.md` and `plan/exec/` is repo-relative [a].
2. Worktrees are created with `git worktree add` under `/Users/ajay/Developer/.arci-worktrees/wt-<lane>` on `sprint/<lane>` branches; coder dispatches get the absolute path; integration only on main by me [a fallback, c convention].
3. The demo is packaged as `arci.demo` (world, agents, experiment, run) and `examples/retry_agent/{world,agents}.py` become re-export shims; `experiment.py` and `hero_demo.py` stay byte-identical; distinct `arci-demo-` experiment ids; N fixed at 200; temp store [c: frozen test_hero, figure needles; b: real gate path; e].
4. `arci run` accepts YAML descriptors directly, so the memo's `arci run arci.yaml` holds; sealing stays `Manifest.create`; schema is `Descriptor.model_json_schema()` committed at `docs/schema/arci.schema.json` with a staleness test [b, c].
5. The console script puts the cwd on the children's import path (append, never prepend): ADR 0006, Astra-reviewed; without it the first-screen command cannot work [b: first-screen command; c: AGENT_SEMANTICS parent-never-imports; e: append is the least invasive].
6. `arci init` validates refs in a child process with the runner's path rule, never in the CLI process [c: AGENT_SEMANTICS].
7. The smoke notice goes to stderr of `arci run` only, threshold `n_per_arm < 100`, with the planner's numbers where its domain allows [c: pinned stdout/report bytes; b: "CLI prints that small N usually yields INCONCLUSIVE"].
8. Version bump and packaging metadata happen once, in T12, with ADR 0005 and a re-freeze commit covering `pyproject.toml`, `uv.lock` and the new ADRs; wheel version stays 0.7.0 until then and nothing is published before the bump [c; the v0.7.0 precedent re-froze without an ADR, but your rule asks for one, so a=prompt wins].
9. No `justfile` changes (frozen); release steps live in `docs/RELEASING.md` and CI scripts [c].
10. Release workflow uses `uv build` + `pypa/gh-action-pypi-publish` (SHA-pinned) because `uv publish` uploads but does not generate attestations [a: "with attestations"; docs checked today].
11. Windows gets an install/import/--help job only; any module-level POSIX reference that breaks import is guarded; execution is not advertised [b S11].
12. S8's Inspector step is run once by me with network; tests never call npx; a protocol-version rejection is recorded verbatim, not patched around in this sprint [c: no network in tests; b: honesty; e].
13. Reviewer subagent has Read/Grep/Glob only; I run all checks and hand it the diff and outputs [a: read-only tools].
14. Coder tool set is Read/Edit/Write/Bash/Grep/Glob; no Agent/web tools [a].
15. Denied `gh` commands are never bypassed through `gh api`; merges use plain git after lane CI; anything still blocked becomes HUMAN_INBOX [harness over prompt; a for the inbox].
16. Cut order under budget pressure: S8, then S9, then S7 reduced [b: TTFV path first; e].
17. No new store under `docs/results/`; measurement receipts live in `docs/measurement/receipts/` [c: pinned-store tests].
18. The `Independence` paragraph added on origin main (#14) is kept verbatim below the fold in the README rewrite [c: never loosen].

## Decisions made during execution

(appended as they happen: id, decision, positions, rule, consequence)
