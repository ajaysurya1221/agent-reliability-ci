# FINAL_REPORT — ARCI v0.8.0 sprint (orchestrated run of 2026-10-13)

<<DRAFT at 07:15Z; sections 1 (S10, S12), 4, 5, 8 and the final counts are completed at wrap-up.
Budget clock: Task 00 commit 2026-10-13T03:42:56Z; stop-starting at 12:57:56Z; end 13:42:56Z.>>

Orchestrator: Claude Fable 5.1 (this session). Coders and reviewers: Claude Opus 5.5 at effort high
(workflow subagents; model verified in every transcript). Consultant: Codex `gpt-6-astra` at xhigh,
read-only. Records: `plan/exec/` (PLAN, tasks, DECISIONS, STATUS, reports, reviews, consults,
decisions, measurements), `docs/design/0005`–`0009`.

## 1. Shipped vs the memo's sprint

| Memo task | State | Evidence |
|---|---|---|
| S1 package pipeline | merged (T06) | `.github/workflows/release.yml` (guard, build, smoke matrix, publish with attestations), `docs/RELEASING.md`; lane CI green |
| S2 packaged `arci demo` | merged (T02, T02b) | `src/arci/demo/`; `uvx --from <wheel> arci demo` from an empty dir: exit 0, "All six steps held" (last run on merged main f0915f9); 1:12 wall incl. environment creation (plan/exec/measurements.md) |
| S3 descriptor + schema | merged (T03, T03r1, T03r2; three rounds) | `src/arci/descriptor.py`, `docs/DESCRIPTOR.md`, `docs/schema/arci.schema.json`, `arci schema`, `arci run x.yaml`; ADR 0007 |
| S4 `arci init` | merged (T04, T04r1, T04r2; three rounds) | `src/arci/init.py`; child-process reference validation; atomic publication (D-10); ADR 0008, ADR 0006 |
| S5 smoke UX | merged (T05 with T04) | stderr-only notice with Astra's exact wording; `n_per_arm` 8 scaffold with header; `arci plan` pointer |
| S6 README first screen | merged (T11) | 191 words before the first `## `; ADR 0009; all links absolute; cold read 5/5 (AI-agent labelled) |
| S7 Python recipe | merged (T08, T08r1) | `examples/recipes/python_agent/`, `docs/recipes/python-agent.md`, recorded outputs, 18 recipe tests |
| S8 MCP recipe + Inspector | merged with the Inspector step recorded as blocked (T09; D-03) | `examples/recipes/mcp_agent/`, `docs/recipes/mcp-inspector.md` (Inspector 2.10.1 / SDK 1.29.0 rejects protocol 2026-07-28; verbatim) |
| S9 TTFV harness | merged (T10, two revision rounds) | `docs/measurement/ttfv-protocol.md`, `receipt.template.json`, `receipts/README.md` |
| S10 release-integrity merge | <<state>> | T12 (round 2 in review at 07:15Z), ADR 0005, titled re-freeze commit |
| S11 install/Action matrix | merged (T07) | CI jobs wheel-smoke (Ubuntu/macOS × 3.11/3.14), windows-smoke (install/--help only), action-fixture (must BLOCK); `sprint/**` trigger |
| S12 release | <<state>> | tag v0.8.0, GitHub release, PyPI |

## 2. Deviations from the memo, with the rule that decided each
(rules: a = the prompt, b = the memo, c = the repo's rules, d = Astra consult, e = reversibility)
- Smoke N is 8, not the memo's 5: the smallest N at which a total collapse can still BLOCK under the default rule (ADR 0008; E1 tie-break; d).
- `arci init` writes a bare `arci run arci.yaml` success line, labels arms `baseline`/`candidate`, accepts only built-in faults and requires `--out` to end in `.yaml`/`.yml` (ADR 0008; d, then c).
- The descriptor defaults `task_id` to `experiment_id`, labels bare arms `<module tail>.<function>`, and parses YAML with an isolated resolver (booleans only `true`/`false`; `010` is ten) so a hand-written task cannot change a seal silently (ADR 0007; E2 tie-break; d, c).
- The README's PASS sentence states the positive non-inferiority finding ("any reliability drop … is smaller than the allowed drop") rather than the memo's "not shown to be worse", which also describes INCONCLUSIVE (ADR 0009; d, c: docs/STATISTICS.md).
- The first-screen scaffold command stays the memo's four-reference form without `--fault` (D-09; b).
- The runner appends the current directory to every child's import path, never prepends; an MCP server whose env sets `PYTHONPATH` keeps it (ADR 0006, amended after Astra's review; b first-screen command, c AGENT_SEMANTICS, e).
- `arci init` publishes by hard link, or by rename only with `--force`; the orchestrator's own O_EXCL-copy fallback was removed after Astra rated it MAJOR (D-10; c: ADR 0008 "published atomically").
- The Inspector preflight is documented as blocked by the Inspector's SDK, not patched around (D-03; c: no network in tests, bridge version handling out of scope; e).
- `arci run --out` defaults to `runs` (T03; b: the memo's `arci run arci.yaml` with no further flags).
- The version bump has a design record (ADR 0005) although the v0.7.0 precedent had none (a over c's precedent).
- No `justfile` changes; release steps live in `docs/RELEASING.md` and CI scripts (c: frozen).
- Merges were done with plain `git merge --no-ff` after lane CI on `sprint/**`, never through `gh pr`, because the user's deny list blocks `gh pr create/merge`, `gh release create`, `gh workflow run`; the orchestrator never routed around a deny via `gh api` (harness over a; HUMAN_INBOX lists each denied step with the exact command).
- Coders were dispatched through the Workflow tool's `agent()` with model `opus`/effort `high` because mid-session `.claude/agents/*.md` are not registered (D-01); every transcript shows `claude-opus-5-5`.
- `codex exec` runs with stdin closed and prompts in files after three consults stalled on an open stdin pipe (D-05).

## 3. Review coverage
Product changes merged into main: 8 (T02, T02b, T06+T07, T10, T03, T04+T05, T08+T09, T11); every one carries two or more non-author reviews. Merged with one review: 0. With none: 0 (plan-only commits under `plan/exec/` are records, not product changes; one of them, the README-pins script, broke `ruff` on main for two commits and was fixed in cbd8d20).
Cross-family (Astra, read-only) reviews of merged changes: T06+T07 (release workflow, CI), T03 (three rounds), T04+T05 (two rounds; ADR 0006/0008), T08+T09 (two rounds), T11 (two rounds), plus T12 (two rounds, in progress) and T13 <<pending>>. Astra also made the three blind bias-control proposals (E1–E3) and their tie-breaks, and CONSULT 01.

| Task | Author | Reviewers | Verdicts (rounds) |
|---|---|---|---|
| T02 demo | Opus | Fable, reviewer-subagent | ACCEPT, ACCEPT (1) |
| T02b demo polish | Opus | Fable, reviewer-subagent | ACCEPT, ACCEPT (1) |
| T06+T07 package/CI | Opus | Fable, reviewer-subagent, Astra | ACCEPT ×3 (1, one NIT fix) |
| T10 measurement | Opus | Fable, reviewer-subagent | REVISE → REVISE → ACCEPT (3 rounds; Fable ACCEPT) |
| T03 descriptor | Opus | Fable, reviewer-subagent, Astra | r1 Astra REVISE (MAJOR: unordered YAML collections) → r2 reviewer ACCEPT → r3 Astra ACCEPT |
| T04+T05 init/smoke | Opus | Fable, reviewer-subagent, Astra | r1 reviewer REVISE, Astra REVISE (2 MAJOR) → r2 reviewer ACCEPT, Astra REVISE (O_EXCL fallback) → r3 reviewer ACCEPT, Astra ACCEPT |
| T08+T09 recipes | Opus (+ orchestrator-pasted Inspector output) | Fable, reviewer-subagent, Astra | r1 found the pasted block incomplete → T08r1 → ACCEPT, ACCEPT |
| T11 README | Fable | reviewer-subagent, Astra | r1 Astra REVISE (relative links) → r2 ACCEPT, ACCEPT |
| T12 release merge | Fable | reviewer-subagent, Astra | r1 REVISE, REVISE (ROADMAP claim; carried-forward bullets; lock markers) → r2 <<pending>> |
| T13 release | Fable | reviewer-subagent, Astra | <<pending>> |

## 4. Metrics vs the memo's targets
| Metric | Target | Measured | Where |
|---|---|---|---|
| Packaged demo TTFV | p50 ≤ 2 min | <<>> | plan/exec/measurements.md, docs/measurement/receipts |
| Own-agent TTFV (sample tree) | ≤ 10 min | <<>> | |
| Cold read of the README (Opus subagent, no context; AI-agent labelled) | ≥ 4/5 | 5/5, BLOCK interpretation correct (plan/exec/cold-read-2026-10-13.json) | plan/exec/measurements.md |
| Installed-package smoke on CI | green | <<>> | release workflow |
| Merge bar on the released commit | green | <<>> | |

## 5. Cuts and why
<<>>

## 6. Usage
- Opus 5.5 (workflow subagents, all `claude-opus-5-5`, effort high): 32 workflow runs, 39 agent transcripts (14 coder task dispatches incl. 7 revision rounds; 15 reviewer dispatches; 1 cold read; 1 probe; 1 read-only repo map). Output tokens 948,886; cache reads 232.4 M; cache creation 9.2 M (summed from the transcripts at 07:15Z; T12 round 2 and T13 reviews add to this; final figure at wrap-up <<>>).
- Fable 5.1 (orchestrator): one session, context compacted once at ~06:45Z; wrote the plan, CONTRACT, ADRs 0005–0009, the README rewrite (T11), T12, all merges and verification runs, the recipe docs' Inspector transcript, and every plan record.
- Astra (`gpt-6-astra`, xhigh, read-only): 20 consults so far (CONSULT 01; E1/E2/E3 proposals and tie-breaks; reviews 06-07, 03 ×3, 04-05 ×3, 08-09 ×2, 11 ×2, 12 ×2) <<+ T13>>; typical run 3–8 minutes; three early runs stalled 45 minutes on open stdin (D-05).

## 7. Known issues
- `src/arci/mcp_boundary.py` reads `sys.stdout.buffer` at import (pre-existing; not hit by the demo).
- hatchling is version-pinned, not hash-pinned, in the release build (ADR 0005 "Not in v0.8.0").
- Inspector 2.10.1 (TS SDK 1.29.0) rejects the bridge's protocol revision 2026-07-28; the bridge never negotiates (D-03).
- `arci init`: every non-`FileExistsError` from `os.link` is reported as "hard links unsupported" (EIO, ENOSPC, EXDEV too); still fails closed. macOS `fsync` is not `F_FULLFSYNC`, so durability there is best effort. Dead signed-prefix branches in `descriptor._int_value`. (REVIEW 04r2 follow-ups.)
- The sdist's contents are not checked by an allowlist in `release.yml` (hatchling adds `PKG-INFO` and `.gitignore`); ADR 0005 says so.
- `uv lock` rewrites equivalent dependency markers on regeneration (e304e81 and v0.8.0); recorded in ADR 0005 and `docs/RELEASING.md`.
- The `pypi` GitHub environment has a tag policy (`v*`) but no required reviewer.
- Measurement protocol follow-ups from the T10 reviews: a `trials_started` field and a Track A version check.
- README: several lines below the fold exceed the wrap width; the first-screen "on PyPI" availability sentence is true only after the tag publishes.
- <<T13 additions>>

## 8. Next three steps
1. <<>>
2. <<>>
3. <<>>
