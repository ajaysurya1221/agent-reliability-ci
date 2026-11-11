# Phase 0 gate report (ARCI v2.0)

Written by the orchestrator (Claude Fable 5.2), 2026-11-11. Branch `v2/phase0`, nothing
committed. No file under `src/`, `tests/`, `docs/` or `bench/` was changed. All 54 frozen
hashes pass. Plan: `plan/exec/v2/PLAN.md`.

## Gate decision: PASS, with the design changed in three places

Phase 0 was meant to prove two things before any product code: that the statistics hold, and
that a LangChain agent can run under ARCI's boundary. Both hold. Neither holds in the form
the approved plan described, and the changes are listed below for your approval.

| Spike | Question | Result |
|---|---|---|
| S1, S1b, S1c | Is there a valid multi-task rule, and what does it cost? | Yes: balanced rounds with two betting tests. Error bound proved and attacked without a counterexample. Costs measured exactly |
| S2, S2b | Can a `create_agent` agent run under the boundary with no change under `src/`? | Yes. The prototype's shape does not ship; nine binding requirements go to phase 3 |
| S3 | Does the existing MCP bridge work with a current MCP client? | No. Confirms MCP stays out of v2.0 |
| S4 | What does the study cost? | **Not run.** Needs your API key |
| S5 | Design records | ADR 0011 and ADR 0012 drafted and revised after Codex's first review; second review result recorded at the end of this file |

## Three changes to the approved plan

1. **Statistics: balanced rounds replace sampled cells.** The plan drew each pair's task at
   random. Measured for one fixed schedule, that design's false-PASS rate reached 23% at the
   99th percentile and 53% at worst, though it averages 1.2%. A manifest's schedule is
   fixed, so that is the rate a user of that manifest faces. With balanced rounds every
   round runs every cell once, verdicts come only at round ends, and the 2.5% bound holds
   for the suite as registered. Price: up to 1.8 points of power at 20 cells and 4.9 at 50,
   and 7.5 to 25 more pairs on average.
2. **Adapter: one ARCI middleware plus proxy tools, not "one changed line".** A user writes a
   small adapter file (44 lines in the prototype), a check function and `arci.yaml`. The
   plan's objective sentence and the launch claim change accordingly.
3. **Claims: no "fewer runs" claim.** Against v1's default rule the new test decides more
   often at the same ceiling. Against v1's Newcombe option, with independent arms on one
   task, it saves nothing at equal power. Nothing can PASS before about 80 pairs
   (160 sessions) at the default margin.

## Numbers to carry forward (exact enumeration, defaults, 20 cells)

| Case | Result |
|---|---|
| Identical arms at 0.95 | PASS 99.9%, about 126 pairs |
| 0.95 dropping to 0.75 | BLOCK 92.8%, about 203 pairs |
| Identical arms at 0.80 | PASS 77.8%, about 251 pairs |
| Identical arms at 0.50 | PASS 52.0%, about 306 pairs; the rest INCONCLUSIVE |
| Largest error found on the margin | 2.16% at 1 cell, 1.15% at 20 cells; proved at most 2.5% |
| Adapter overhead per trial | About 1 second idle; budget 1.5 seconds |

## What was done to check the work

- Every spike was re-run by the orchestrator. Results reproduced; the only differences were
  a recorded elapsed time and one lint line caused by Codex's own report file.
- Four independent review rounds, each finding re-checked by a separate skeptic:
  S2 (15 agents, 11 findings), S1 (18, 13), S2b (12, 9), S1c (18, 13). No finding was
  refuted in any round. An independent implementation agreed with Codex's on 2.5 million
  decision paths; an independent search of about 220,000 configurations found no violation
  of the balanced-rounds bound.
- Two of the errors caught were mine: the S2 brief assumed the wrong native LangChain
  behaviour for tool failures, and the S1c brief asked for 12 scenarios but defined 8.
  Codex kept a check failing and flagged the count instead of bending either.

## Decisions needed from you

1. **Approve ADR 0011** (`adr-0011-draft.md`): the suite gate. Two judgment calls inside it:
   - Seed rule default: `fixed` per cell (stronger guarantee; my choice) or `per_round`
     (wider scenario coverage; Codex's preference). Both stay available as a sealed option.
   - Default tolerance for errored pairs: 1% of registered pairs, scored against both tests.
2. **Approve ADR 0012** (`adr-0012-draft.md`): LangChain as an optional extra.
3. **S4, the cost pilot.** Name the provider and put its API key in your shell environment;
   I never see or store the key. The pilot is 20 sessions per candidate model, a few cents
   to a few dollars, with your USD 50 cap set in the provider console first.

## What happens after approval

- Lane A (statistics): phase 1 kernel, then phase 2 runner, store and CLI.
- Lane B (adapter): phase 3 with the nine requirements, then phase 4 report.
- Both lanes run under Codex in separate worktrees; I review and merge.
- S4 can run at any point before phase 5.

## Records

Briefs in `tasks/`; spike code and results in `spikes/`; reviews in `reviews/`; Codex
consults in `consults/`; this file and both ADR drafts at the top of `plan/exec/v2/`.

## Codex review of the design records: ACCEPT on the third round

Codex Astra 6, read-only, high effort. Records in `consults/`.

| Round | ADR 0011 | ADR 0012 | What it found |
|---|---|---|---|
| 1 | REVISE | REVISE | Five blocking findings on 0011 (stopping rules, store checks, pair adjacency, provider-failure rule, planning model); two on 0012 (CI isolation, version bounds) |
| 2 | REVISE | REVISE | All seven resolved or partly resolved. Three new: the `per_round` seed mode claimed an averaged guarantee that a deterministic hash cannot support; the adapter type check would have skipped its own files; the transitive version endpoints were not named |
| 3 | ACCEPT | ACCEPT | All resolved, no new blocking finding |

One non-blocking item carried into phase 3: fix the exact lowest jointly installable set of
LangChain packages from package metadata before writing the version assertions.

The phase 0 condition for S5, "Codex read-only review returns no blocking finding", is met.
