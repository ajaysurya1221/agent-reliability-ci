# FINAL_REPORT — run 2, "post-release hardening and reference measurement" (2026-10-13/14)

Budget clock: Task 00 commit 2026-10-13T18:12:20Z; stop-starting at 01:27:20Z; end 02:12:20Z (2026-10-14).
Work ended at 22:31Z on 2026-10-13 (4 h 19 min of the 8 h), every lane merged, main green at 02910c3
(CI run 38476482555), nothing in flight.

Orchestrator: Claude Fable 5.1. Coders and reviewers: Claude Opus 5.5 at effort high (workflow
subagents). Consultant: Codex `gpt-6-astra` at xhigh, read-only. Records: `plan/exec/run2/`
(PLAN, PLANNING-RECORD, tasks, reports, reviews, consults, measurements, data) and
`plan/exec/DECISIONS.md` (D-11). The plan was made jointly with Astra (blind proposals, tie-break)
and approved by the user with three decisions: autonomous run; no posting or recruiting this month;
D1 deferred past 2026-11-12.

## 1. Shipped vs the approved plan

| Item | State | Evidence |
|---|---|---|
| T16 leftovers, code | merged (three review rounds) | `arci run` prints `run store: <path>` on stderr; `arci init` errno attribution and macOS fsync note; `mcp_boundary` frames via `sys.__stdout__` at call time; wheel smoke runs `arci schema`; release workflow sdist allowlist; CI Action-fixture summary check with a stderr-leak guard; recipe-test fixes; README own-agent command shows `--task`; CHANGELOG Unreleased entries. Isolated merge bar 1225 passed. Reviews: Fable, reviewer ×3, Astra ×3 (two REVISE on the guard's error handling and a CHANGELOG qualifier). |
| T17 protocol and scripts | merged (two rounds) | Protocol §2.3 Track A version check, §4.6 multi-store `trials_started`, §5 q2 either-route sentence, §7.1 per attempt, §7.2 ISO-or-empty `at` and a six-stage failure taxonomy, §8.2–8.4 first-attempt rule; zsh-safe stopwatch scripts; cohort builder `--persist`, `--legacy-sentence`, overwrite refusal, all-or-nothing writes, 64 tests; persisted cohort result committed under `plan/exec/run2/data/`. Reviews: Fable, reviewer ×2. |
| T18 reference-machine timing | merged (three review rounds + the D-12 tie-break delta; two coder hangs) | `.github/workflows/ttfv-reference.yml` (five cold + two warm samples per OS, per-sample timeout, deadline arithmetic, robust journal), `plan/exec/scripts/reference_stats.py` (validated per-block stats), `docs/measurement/reference-machines/README.md`. Reviews: Astra REVISE ×3 → ACCEPT on the tie-break delta; reviewer REVISE ×2 → ACCEPT (r3). Final run 38470699338: all seven samples on both runners; JSON committed under docs/measurement/reference-machines/. |
| T19 Inspector compatibility check | done | D-11: no released MCP SDK (v1 1.32.1, v2 core 2.2.0 used by Inspector 2.10.1) supports revision 2026-07-28; the honest fix is an explicit standalone compatibility mode of the bridge (argv flag, never an environment variable), ADR 0011 for the next run once an MCP pilot or the MCP post commits; Astra agreed after one correction. |
| T20 D2 import-record provenance model, design only | done | `plan/exec/run2/adr-0010-draft.md` v3 accepted by Astra after two REVISE rounds (purity of the import function with explicit provenance inputs; ordering evidence; recursive immutability; conservative capabilities; separate source-reported vs oracle outcomes). Fixture candidates in `plan/exec/run2/fixtures.md` (two offline-replay producers accepted conditionally; no fixture fetched; D3 not started). |
| T21 wrap-up | done | this file; HUMAN_INBOX section "Run 2"; plan/exec/run2/STATUS.md. |

## 2. Deviations from the plan, with the rule
- T18 needed three rounds: the first commit had no per-sample timeout (the macOS job hit its
  25-minute limit live), the second's deadline arithmetic was still unbounded and its validator
  accepted contradictory samples (Astra); fixed in T18r1/T18r2 (rule c: honest measurement, and
  rule e). Astra's third round still found the reserve under-counted by 60 s; with the three
  rounds exhausted, D-12 applied the fix as a minimal orchestrator delta (reserve 420 s, probe gated
  on the whole reserve, the combined inequality asserted) and merged on the reviewer's round-3
  ACCEPT plus Astra's ACCEPT of that delta only.
- Two Opus coders on the T18 revision hung inside a Bash tool call after writing their edits (no
  child process remained; the hung commands were ordinary PyYAML/shellcheck/shasum checks). The
  orchestrator stopped them, verified the on-disk work in isolated child sessions with wall-clock
  limits, and committed it (plan/exec/run2/reports/18r3.md). Cause not established; recorded as a
  harness known issue.
- T16 needed two extra delta rounds for the CI stderr-leak guard (grep error handling) and a
  CHANGELOG qualifier (Astra); accepted in round 3.
- The T18 workflow's push trigger was narrowed to `sprint/t18-**` (orchestrator) so other lane
  pushes do not spend runner time on PyPI downloads.
- D2's acceptance criterion for "authentic fixtures" was interpreted (Astra, agreed) as genuine
  producer output, including a real instrumentation replaying its recorded cassettes offline, never
  hand-written spans; a producer counts only once its fixture shows useful tool identity and order.

## 3. Review coverage
Product changes merged into main in this run: 3 (T16, T17, T18), each with two or more
non-author reviews; Astra reviewed T16 (workflows and the publication path), T18 (workflow) and the
two design records (D-11, ADR 0010 draft); T17 was reviewed by the reviewer subagent and the
orchestrator. No author-only merge. Plan-only commits under `plan/exec/` are records.

## 4. Measurements
- **Reference machines (memo target: demo p50 ≤ 2 min, p95 ≤ 3 min on clean reference machines).**
  Final workflow (2684e24), run 38470699338, committed under `docs/measurement/reference-machines/`:
  ubuntu-latest cold 231–232 s (p50 232, p95 232), warm 231/231; macos-latest cold 208–244 s (p50
  220, p95 244), warm 231/228: **both runners over the memo's target by about 2×**, warm equal to
  cold within seconds (the resolve/download is ~1 s; the demo's computation is the time). Earlier
  runs agreed (run 38451606669: 213–227 s cold). Preliminary (first run, old schema):
  ubuntu-latest cold 169 s, warm 156/146/141/137 s (p50 146 s misses the 120 s target; p95 169 s
  within 180 s); macos-latest 235 s cold then 336, 417, 453 s, job timed out (far over target, and
  slowing monotonically for an unknown reason). The package resolve is ~1 s on both; the demo's
  compute dominates. These are machine timings, not receipts (protocol §1.4).
- **Every dated adoption metric in the memo** (demo TTFV by Oct 20, own-agent TTFV by Oct 27,
  cold-read comprehension by Nov 12, first external run by Oct 31, external runs/Action references/
  stranger issues later): **unmeasured**, because no external users were recruited (user decision);
  HUMAN_INBOX keeps the launch and outreach drafts ready.

## 5. Cuts and why
D1 (user decision), D3–D6 (no authentic fixtures in hand; memo line 306), D7 (cookbook kill rule),
D8 and all posting (user decision), R1–R8 (conditional on external evidence), Inspector negotiation
(ADR 0011 next run), `httpcore2` typo and hash pinning (next justified re-freeze).

## 6. Usage
- Claude workflow subagents in run 2: 12 workflow runs (6 coder runs incl. revisions and the two stopped hangs; 6 reviewer runs), 15 agent transcripts; models seen {'claude-opus-5-5': 749}; output tokens 386,269; cache reads 71.7 M; cache creation 3.3 M (summed from the transcripts at wrap-up).
- Astra (`gpt-6-astra`, xhigh, read-only): 10 consults in run 2 (D2/D-11 design ×3, review 16 ×3, 18 ×4) plus the three planning consults (blind proposal, tie-break) recorded in plan/exec/run2/PLANNING-RECORD.md.
- Fable 5.1 (orchestrator): one session continued from run 1; wrote the plan with Astra, the D2 design draft, D-11/D-12, all briefs, the T18 tie-break delta, every merge and verification run, and these records.

## 7. Known issues
- macOS GitHub runners: the demo slows down monotonically across samples (235 → 453 s); cause unknown
  (leftover processes, accumulating temp stores, throttling). Until understood, macOS reference
  timings are reported but not interpreted.
- The demo's size (200 trials per arm, six steps) puts hosted runners over the memo's p50 target;
  the target and the demo's size are a planning decision, not a workflow fix.
- `worker.py` still reads `sys.stdout.buffer` at import (same pattern T16 removed from the boundary).
- The sdist allowlist rejects directory entries (hatchling writes none today).
- `receipt.template.json` keeps the old "per reader per track" and "ERROR if none" wording because
  its `_comment`s are copied into every receipt (changing it would alter rebuilt receipts).
- Inspector step still blocked (D-11); ADR 0011 pending.
- The reference-machine workflow's trigger is `sprint/t18-**` + `workflow_dispatch`; `gh workflow run` is denied for the orchestrator, so re-running it needs a push to such a branch or the user's click.

## 8. Next three steps
1. Investigate the macOS runner slowdown with a process/disk snapshot before each sample (one small
   workflow change), then decide whether the demo should run fewer trials on hosted runners or the
   memo's reference-machine target should name the machine class.
2. ADR 0011 (bridge compatibility mode) and, once an MCP pilot or the MCP post commits, its
   implementation; D3 (first importer) once two authentic fixtures are produced per
   `plan/exec/run2/fixtures.md`.
3. The human part: post the drafts and recruit five cold readers (HUMAN_INBOX 4–5); every dated
   metric stays unmeasured until then.
