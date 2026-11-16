# Consult: design of a third pre-registered run of the order-desk study

You are the consultant. The orchestrator (Claude) will decide after reading your answer and
will tell the maintainer both views. Work read-only. Change no file. Run no model, do not
start Ollama, do not run `arci run`. You may run `.venv/bin/python -m arci plan ...` in
`/Users/ajay/Developer/.arci-worktrees/wt-v2-logs` to check a power figure. Never open
anything under `~/.claude` or `~/.codex`, and do not search any memory registry.

## Background

ARCI (checkout `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`, records in
`/Users/ajay/Developer/agent-reliability-ci`) published a small study: a 12B local model
(baseline) and a 4B local model (candidate) run the same tool-using "order desk" agent on
24 tasks under 4 conditions (clean; timeout, one-off error and empty result injected on
the first `lookup_order` call). Run 1: 96/96 against 70/96, BLOCK. Run 2 (tool errors
returned to the model): 480/480 against 428/480, INCONCLUSIVE on a 10-point
non-inferiority margin. Write-up: `docs/results/order-desk-study.md`; working records:
`plan/exec/v2/study/`; statistics: `docs/STATISTICS.md`, `docs/STATISTICS_SUITE.md`.

Run 2, candidate arm, counted three times from the store: empty-result condition 86/120;
stock-note tasks under the empty result 7/40 (per task 1,1,4,0,1,0,0,0 of 5); the other 16
tasks under the empty result 79/80. The injected empty result reaches the model as a
successful tool result whose text is `null`. The candidate read the order again in 87 of
120 such trials (86 passed) and not in 33 (0 passed). The system prompt, the same in both
arms, ends "Retry an empty lookup once." The code retries only timeouts and runtime errors.

Two readers of the blog post ask for a third run. Reader A: a "code-retry variant" (the
code retries an empty lookup, so the model need not decide), to see whether this is a
capability gap. Reader B: put the next step into the text the model gets at the point of
failure and see whether a better message closes most of the gap (a tool-design fix).

The project's situation: one maintainer, only coding agents build and run things, 0 stars,
a stop rule on 14 Dec 2026 (15 stars, 2 outside issues or discussions, 1 result posted by
someone else). The product's first screen is now a different tool (`realornoise`); the
study is the content of blog post 1, which drew the only two reader comments so far.

## What a design round produced

Three agents read the records and the harness; three proposed designs; two judges scored
them. Full output: `/private/tmp/claude-501/-Users-ajay-Developer-agent-reliability-ci/39ca2335-7a5a-47d9-a374-69d92a47e1d0/scratchpad/run3-design/workflow-result.json`
(keys `understood`, `designs`, `judges`).

Facts the designs rest on:

- The test has no superiority verdict. With a fix as the candidate, a helpful fix and a
  useless fix both give PASS. So every design puts the changed set-up in the baseline arm
  and run 2's set-up in the candidate arm, with the 4B model in both arms. BLOCK then
  reads "the set-up without the change is worse by more than the margin", that is, the
  change is worth more than the margin; PASS reads "the change is worth less than the
  margin". The proof does not depend on which arm is new; the shipped quickstart compares
  two set-ups of one model in this orientation. The tool will print "regression
  established" for the outcome that favours the change.
- The arm difference has to be a middleware in the study's own `agent.py`, added in one
  arm. The store records the injected null in both arms and never what the model was
  shown.
- No environment with LangChain exists on the machine now; run 2 used ARCI 2.0.0 with
  langchain 1.4.10, langchain-core 1.7.7, langgraph 1.2.20, langchain-ollama 1.1.0. The
  run path of ARCI did not change between 2.0.0 and 2.4.0.

The three designs:

1. Readers-first: two runs (3A code retry, 3B text), 24 tasks under the empty result only,
   margin 10 points, up to 15 rounds each. Flaw found by both judges: 16 of the 24 cells
   already pass 79/80, so a 10-point margin on the mean is a 30-point margin on the 8
   stock-note cells; a rise from 17.5% to 45% there would end PASS.
2. Decision-first: one run (text), the 8 stock-note tasks under the empty result, margin
   20 points, up to 40 rounds. Flaw: the margin was tuned to run 2's counts after the grid
   was; a gain between 10 and 32 points most likely ends INCONCLUSIVE.
3. Smallest-honest: one run (text), the same 8 cells, margin 10 points as in runs 1 and 2,
   up to 40 rounds (16 trials a round, at most 640 trials, under 80 minutes). `arci plan`
   projections with the unchanged arm at 7/40: text arm at 50% gives BLOCK 0.9997 after
   about 80 pairs; 40% gives BLOCK 0.80; 30% INCONCLUSIVE 0.95; no effect gives PASS 0.73
   and INCONCLUSIVE 0.27.

Both judges chose design 3, with one graft: add Reader A's code-retry comparison as a
second run on the same 8 cells and rule, registered in the same commit (projected to stop
after about 25 to 45 pairs, a few minutes). Further grafts: model-free tests of both
middlewares before registration, including one end-to-end check with a scripted chat model
that the text really replaces `null`; a "the change was live" count for each run; both
count scripts committed with the pre-registration and first checked against run 2's
published counts; a digest of `agent.py` sealed into the manifest; `prior_runs` listing
runs 1 and 2; the role swap explained in the first lines of every write-up.

The proposed text for the empty lookup, fixed before any model sees it:
"lookup_order returned an empty result. Call lookup_order again with the same order_id."

## The orchestrator's leaning

Run design 3 plus the code-retry run on the same 8 cells: two small runs, one commit of
pre-registration, the 4B model in both arms, margin 10 points, roles swapped and said so.
Claim nothing about the 12B model, about "capability", about cause, or about the full
suite. Publish INCONCLUSIVE as INCONCLUSIVE. Estimated cost: half a day of agent work and
under 90 minutes of laptop time.

Doubts I want attacked:

1. Is the swapped-role reading sound under `docs/STATISTICS_SUITE.md`, including the
   per-round-seed condition? Is there a cleaner way to ask "does the change help" with the
   released tool?
2. Is choosing the 8 worst cells and one condition from run 2 defensible for a new run, or
   does it make the result too narrow to be worth publishing? Would the full 24 tasks under
   the empty result, or all 4 conditions, be more honest even though less decisive?
3. Margin 10 points on 8 cells and a cap of 40 rounds against the tool's default of 50:
   which would you register, and why?
4. Is the code-retry run worth running at all? Its outcome is nearly fixed (with the retry
   in code the model sees a working lookup), and it cannot say "capability gap". Does
   running it mislead Reader A, or is a confirmed mechanism still worth five minutes?
5. The text: is one sentence right? Should it avoid the word "Error:"? Is there a control
   I am missing (for example a text of the same length that names no next step) without
   which a BLOCK cannot be read as "naming the next step helped"?
6. Should a 12B arm appear anywhere? Without it nothing can be said about "the gap".
7. The bigger question: given the project's situation above, is a third run the best use
   of the next half day, compared with replying to both readers and doing nothing more?
   Say what you would do in the maintainer's place.

## What I need back

Under 700 words, verdict first:

1. Your recommendation: go with the leaning, go with changes (list them), or do not run.
2. The strongest argument against my leaning.
3. A direct answer to each of the seven doubts, one or two sentences each.
4. Anything that would make a published result misleading that the list above misses.
