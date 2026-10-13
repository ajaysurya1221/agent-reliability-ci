# FINAL_REPORT — ARCI v0.8.0 sprint (orchestrated run of 2026-10-13)

Budget clock: Task 00 commit 2026-10-13T03:42:56Z; stop-starting at 12:57:56Z; end 13:42:56Z. Work ended
at 09:14Z (about 5 h 15 min of the 10 h), with every lane merged and nothing in flight.

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
| S9 TTFV harness | merged (T10, two revision rounds); two maintainer-machine receipts merged (T13) | `docs/measurement/ttfv-protocol.md`, `receipt.template.json`, `receipts/` (two `ai-agent` receipts; no cold readers yet) |
| S10 release-integrity merge | merged (T12, two rounds) | 68f7c8c on main; ADR 0005; titled re-freeze commit 5142d66; merge bar on the merge commit green (1216 tests, frozen 53/53, reproduce 0 failed) |
| S11 install/Action matrix | merged (T07) | CI jobs wheel-smoke (Ubuntu/macOS × 3.11/3.14), windows-smoke (install/--help only), action-fixture (must BLOCK); `sprint/**` trigger |
| S12 release | released: PyPI 0.8.0 with attestations (08:25Z), GitHub release page with the CI files (08:27Z, created by the user) | annotated tag v0.8.0 = 48e60ac (main CI green); release run 38365660814: guard+build and wheel smoke ×4 green; first publish attempt failed `invalid-publisher` (no trusted publisher registered) → the user registered it → `gh run rerun --failed` succeeded; CI artefacts byte-identical to a local build and to the PyPI files; `gh release create` was denied for the orchestrator, so the user ran the inbox command; receipts, recipe titles and README availability merged (T13, T14) |

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
Product changes merged into main: 12 (T02, T02b, T06+T07, T10, T03, T04+T05, T08+T09, T11, T12, T13, T14, T15); every one carries two or more non-author reviews. Merged with one review: 0. With none: 0 (plan-only commits under `plan/exec/` are records, not product changes; one of them, the README-pins script, broke `ruff` on main for two commits and was fixed in cbd8d20).
Cross-family (Astra, read-only) reviews of merged changes: T06+T07 (release workflow, CI), T03 (three rounds), T04+T05 (two rounds; ADR 0006/0008), T08+T09 (two rounds), T11 (two rounds), T12 (two rounds; FROZEN/pyproject), T13 (two rounds; release), T14 (two rounds; post-publication docs), T15 (three rounds; AI-cohort receipts). Nine of the twelve merged changes had an Astra review; the three without (T02, T02b, T10) touched no mandatory area. Astra also made the three blind bias-control proposals (E1–E3) and their tie-breaks, and CONSULT 01.

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
| T12 release merge | Fable | reviewer-subagent, Astra | r1 REVISE, REVISE (ROADMAP claim; carried-forward bullets; lock markers) → r2 ACCEPT, ACCEPT |
| T13 release, receipts | Fable | reviewer-subagent, Astra | r1 REVISE (README clause, un-stamped times, inbox command), REVISE (stale sentence) → r2 ACCEPT, ACCEPT; both scored the two interpretation answers correct |
| T14 post-publication docs | Fable | reviewer-subagent, Astra | r1 REVISE (one long README line, two receipt nits), ACCEPT → r2 ACCEPT, ACCEPT |
| T15 AI-cohort receipts (user request after the run) | Fable | reviewer-subagent, Astra | r1 REVISE (user paths in notes; verdict enum prose; README link), REVISE (mixed re-run exits; failed-init scaffold stamps; coaching timestamp) → r2 ACCEPT, REVISE (generated names) → r3 ACCEPT, ACCEPT |

## 4. Metrics vs the memo's targets
| Metric | Target | Measured | Where |
|---|---|---|---|
| Packaged demo TTFV | p50 ≤ 2 min, p95 ≤ 3 min | From PyPI with the README's exact command: 76 s cold uv cache (3 s install + 73 s run), 99 s warm (machine busy). From the local wheel: 80 s cold, 72 s and 73 s warm. Empty dir, maintainer machine (15-core M5 Pro); AI-agent labelled, not cold readers | plan/exec/measurements.md; docs/measurement/receipts/2026-10-13-claude-fable-orchestrator-{demo,pypi-demo}.json |
| Own-agent TTFV (sample tree) | p50 ≤ 10 min (cold users) | 3 s from scaffold start to a validated INCONCLUSIVE (install 0 s from a local wheel, init 1 s, run 2 s); tool path only, no reading or reference writing; AI-agent labelled | docs/measurement/receipts/2026-10-13-claude-fable-orchestrator-own-agent.json |
| Cold read of the README (Opus subagent, no context; AI-agent labelled) | ≥ 4/5 | 5/5, BLOCK interpretation correct (plan/exec/cold-read-2026-10-13.json) | plan/exec/measurements.md |
| AI-cohort TTFV pass (five context-free readers: 2 Opus, 2 Sonnet, 1 Haiku; after the run, at the user's request; never cold readers) | memo: ≥ 80 % all five correct; own agent ≤ 10 min | 5/5 readers all five correct, both interpretations correct; demo 73–75 s; own-agent scaffold→validated verdict under 15 s each after one failed `arci init` (missing `--task`) per reader | docs/measurement/receipts/2026-10-13-ai-reader-*.json; plan/exec/measurements.md |
| Installed-package smoke on CI | green | green: wheel smoke on Ubuntu and macOS × Python 3.11/3.14 from an empty directory (release run 38365660814); Windows install/--help job green on main CI | release workflow; .github/workflows/ci.yml |
| Merge bar on the released commit | green | green: isolated `just check` 1216 passed/2 skipped, `just frozen` 53 OK, `uv lock --check`, figures, schema, `reproduce.py --check` 0 failed, at 68f7c8c (tag v0.8.0 = 48e60ac, same tree + plan records); main CI run 38363108519 success on the tagged commit and run 38372707567 success on the final head ef6031c | plan/exec/STATUS.md (V rows) |

## 5. Cuts and why
None of S1–S12 was cut. Reduced: S8's Inspector preflight ships as a recorded, blocked step rather than a working one (D-03); S9 shipped the protocol and maintainer-machine receipts but no cold readers (recruiting is the user's step, HUMAN_INBOX 5); S12's PyPI upload and GitHub release page wait on the user (HUMAN_INBOX 1 and 3). The budget was not the reason for any of these.

## 6. Usage
- Claude workflow subagents: 40 workflow runs, 56 agent transcripts (14 Opus 5.5 coder task dispatches incl. 7 revision rounds; 22 Opus 5.5 reviewer dispatches; 1 Opus cold read; 1 probe; 1 read-only repo map; the AI cohort: 5 readers on Opus/Sonnet/Haiku and 5 Sonnet scorers). Models seen: {'claude-opus-5-5': 2451, 'claude-sonnet-5-5': 73, 'claude-haiku-5-5': 25}. Output tokens 1,126,100; cache reads 269.0 M; cache creation 11.9 M (summed from the transcripts at the end of the run).
- Fable 5.1 (orchestrator): one session, context compacted once at ~06:45Z; wrote the plan, CONTRACT, ADRs 0005–0009, the README rewrite (T11), T12, all merges and verification runs, the recipe docs' Inspector transcript, and every plan record.
- Astra (`gpt-6-astra`, xhigh, read-only): 27 consults (CONSULT 01; E1/E2/E3 proposals and tie-breaks; reviews 06-07, 03 ×3, 04-05 ×3, 08-09 ×2, 11 ×2, 12 ×2, 13 ×2, 14 ×2, 15 ×3); typical run 3–8 minutes; three early runs stalled 45 minutes on open stdin (D-05).

## 7. Known issues
- `src/arci/mcp_boundary.py` reads `sys.stdout.buffer` at import (pre-existing; not hit by the demo).
- hatchling is version-pinned, not hash-pinned, in the release build (ADR 0005 "Not in v0.8.0").
- Inspector 2.10.1 (TS SDK 1.29.0) rejects the bridge's protocol revision 2026-07-28; the bridge never negotiates (D-03).
- `arci init`: every non-`FileExistsError` from `os.link` is reported as "hard links unsupported" (EIO, ENOSPC, EXDEV too); still fails closed. macOS `fsync` is not `F_FULLFSYNC`, so durability there is best effort. Dead signed-prefix branches in `descriptor._int_value`. (REVIEW 04r2 follow-ups.)
- The sdist's contents are not checked by an allowlist in `release.yml` (hatchling adds `PKG-INFO` and `.gitignore`); ADR 0005 says so.
- `uv lock` rewrites equivalent dependency markers on regeneration (e304e81 and v0.8.0); recorded in ADR 0005 and `docs/RELEASING.md`.
- The `pypi` GitHub environment has a tag policy (`v*`) but no required reviewer.
- Measurement protocol follow-ups: a `trials_started` field and a Track A version check (T10 reviews); the protocol should say how a repeat attempt by the same reader counts in §8 (REVIEW 14).
- README: several lines below the fold exceed the wrap width; the first-screen "on PyPI" availability sentence is true only after the tag publishes.
- Found by the AI cohort (5/5 readers): the README's four-reference `arci init` command fails on the sample tree without `--task` (`KeyError: 'order_id'`); the error names the flag and every reader recovered on the second try; T15 adds one README sentence. Also reported: `arci run` prints no store path (follow-up: a stderr line), the clean smoke scaffold without `--fault` says little about a retry change (by design, ADR 0008/D-09; the recipe adds `--fault`), README length before "Gate your own agent".
- Resolved during the run: PyPI publication (first attempt failed for a missing trusted publisher; succeeded on re-run after the user registered it) and the GitHub release page (created by the user because `gh release create` was denied for the orchestrator). The README availability line was updated twice to stay true at each commit (T13 pending, T14 published).

## 8. Next three steps
1. Announce (your accounts; drafts B–F in HUMAN_INBOX): the package is on PyPI with attestations and the release page is up; the one claim per post is backed by a recorded run.
2. Run the TTFV protocol with five human cold readers on the released package (HUMAN_INBOX 5, the pilot template). The AI cohort (5/5 on every question, demo 73–75 s) and the maintainer-machine numbers are not cold-reader evidence; the cohort did find the `--task` snag that humans would hit too.
3. Open the follow-up branch for the review leftovers: ADR 0005 `httpcore2` typo at the next re-freeze, an sdist allowlist step in release.yml, the `arci init` link-error attribution and macOS F_FULLFSYNC note, dead branches in `descriptor._int_value`, `trials_started`/Track A version check in the protocol, and MCP Inspector protocol negotiation (ADR + Astra) if the Inspector recipe is to work end to end.
