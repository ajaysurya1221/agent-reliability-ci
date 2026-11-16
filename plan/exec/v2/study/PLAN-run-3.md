# Plan for run 3 of the order-desk study (for the maintainer's approval)

Written on 16 Nov 2026. Nothing here has been built or run. This is a plan, not the
pre-registration; the pre-registration is written and committed in step 5, before any
trial.

## Why

Two readers of blog post 1 asked for a third run on the same day. One asked for a code
retry of the empty lookup. The other asked whether a message at the point of failure
closes the gap. Run 2 cannot answer either: it had one wording and one set-up.

## The decision, and who advised what

A design round (three agents on the records and the harness, three designs, two judges)
chose one small run with a text at the empty lookup, and proposed a second small run with a
code retry. Codex Astra 6 at high effort was then consulted
(`plan/exec/v2/reviews/R4-run3-design-astra.md`). It agreed with the text run and advised
against the code-retry run: with the retry in code the model sees a working lookup, so the
outcome is nearly fixed, and a live run adds reporting work and a result that readers would
take as an answer about capability. The orchestrator follows Astra on this point. The code
retry is shown by a scripted test with no model, and Reader A is told why it is not run.

## The run

- **Question.** On the 8 stock-note tasks, with the first `lookup_order` call returning the
  injected empty result: does the 4B agent pass more often, by more than 10 points of mean
  pass rate over these 8 cells, when the empty result reaches it as a fixed message than
  when it reaches it as the text `null` (run 2's set-up)?
- **Arms.** The 4B model (`ollama:qwen3.5:4b-mlx-ctx32k`) in both arms. Same prompt (it
  still ends "Retry an empty lookup once."), tools, checker, temperature and budgets. One
  difference: a middleware in one arm replaces the `null` of an empty `lookup_order` result
  with the message. The message keeps the status of a successful call and has no "Error:".
- **The message, fixed now:** "lookup_order returned an empty result. Call lookup_order
  again with the same order_id."
- **Roles are swapped, and every write-up says so in its first lines.** The test has no
  verdict for "better". So the arm with the message is the baseline and run 2's set-up is
  the candidate. BLOCK then means: the message is worth more than 10 points on these 8
  cells. PASS means: it is worth less than 10 points (it may be worth nothing, or harm).
  INCONCLUSIVE means: not decided within the budget. The tool prints "regression
  established" for BLOCK; the write-up translates it.
- **Rule.** The rule of runs 1 and 2 (alpha 1/20, margin 1/10, stakes 1/4 and 1/2,
  per-round seeds derived by the tool), on 8 cells a round, at most 40 rounds: at most 640
  trials, under 80 minutes on this laptop, one worker. It stops at the first PASS or BLOCK.
- **What the planner projects** (a model, not a measurement; it takes 7 of 40 from run 2
  for the arm without the message): message arm at 50% gives BLOCK in almost every case; at
  40%, BLOCK 4 times in 5; between about 20% and 38% the likely end is INCONCLUSIVE; with
  no effect, PASS 3 times in 4 and INCONCLUSIVE 1 time in 4.

## What will not be claimed, whatever the verdict

- Nothing about the 12B model or "the gap": it is in neither arm.
- Nothing about capability, about cause, or that "naming the next step" is what helped.
  A BLOCK supports "this replacement message helped on these cells", no more.
- Nothing about the other 16 tasks, the other conditions or the full suite. The 8 cells
  and the one condition were chosen from run 2's results, and the write-up says so.
- No comparison of run 3's counts with run 2's as an effect: different seeds, different
  release.
- No second wording tried after seeing the result. One message, one run. Any later wording
  is a new registered run that lists this one.

## Steps

| # | Step | Done when |
|---|---|---|
| 1 | Restore the environment: the released ARCI with run 2's LangChain versions | `arci report` on the run 2 store prints the published verdict from it |
| 2 | New study folder, copied from run 2's; the middleware in one arm; the 8 tasks; one condition; `prior_runs` lists runs 1 and 2 (Codex Astra builds) | Diff against run 2's folder shows only these |
| 3 | Tests with no model: the message replaces `null` only for an empty `lookup_order`; nothing else changes; one end-to-end check with a scripted chat model. A scripted test of a code retry of the empty lookup, for Reader A's reply | Written blind from this plan by a second agent; all pass |
| 4 | Two count scripts, written separately, checked first against run 2's published counts | Both reproduce 87, 33, 86 and 108 from the run 2 store |
| 5 | Smoke run of 16 trials under another suite id, declared not evidence. Then the pre-registration: question, rule, message, digests of every file, software and model ids, the promised counts, your prediction | Committed and pushed before the first trial |
| 6 | The run | The tool exits with PASS, BLOCK or INCONCLUSIVE; errored pairs within the registered limit |
| 7 | Counts by both scripts; result file; an independent check of every number and sentence; Astra consulted on the write-up before it is shown to you | The two scripts agree; the check has no open finding |
| 8 | Pull request to `main`: the sealed store, the write-up section, the tests that re-derive the verdict | CI green |
| 9 | Replies to both readers with the result, for you to post | Files ready |

**Bound.** If step 1 cannot reproduce run 2's verdict from its store with the restored
environment, or steps 1 to 5 take more than one working day of agent time, the run is not
started: both readers get the replies already prepared, changed to say the test was
designed and why it was not run.

## What it costs you

- One word before step 5: your prediction (BLOCK, PASS or INCONCLUSIVE). If you give none,
  the pre-registration says no prediction was made.
- The laptop awake and on power for up to 80 minutes during step 6.
- Posting two replies at the end.

## Not verified

- That the middleware receives the empty result as the text `null` with this LangChain
  version: read from source, not yet executed. Step 3 tests it.
- That run 2's LangChain versions can still be installed together today.
- How long a trial takes in the arm with the message.
