# Result of the pre-registered study (run 1, 2026-11-11)

Pre-registration: `PREREGISTRATION.md` (pushed at `8ff0c3a` before the run).
Store: `runs/order-desk-gemma4-12b-vs-qwen3.5-4b@533c6d1a…/`. Report: `report-run-1.md`.
Log: `run-1.log`. Wall time 17 min 43 s, one worker, no spend.

## Verdict: BLOCK at round 1. My written expectation (PASS) was wrong.

| | Baseline `gemma4:12b-mlx` | Candidate `qwen3.5:4b-mlx` |
|---|---|---|
| Trials passed | 96 of 96 | 70 of 96 |
| Median seconds per session | 5.8 | 5.2 |

Pairs: 26 where only the baseline passed, 70 ties, 0 where only the candidate passed, 0
errored. BLOCK wealth 156.2 against the threshold 40; PASS wealth 0.0019. `arci gate`
re-derives the same decision from the store.

## Correction (2026-11-13)

A reader, u/Significant_Tune9219, pointed out in the
[r/LangChain thread](https://www.reddit.com/r/LangChain/comments/1xtror1/i_put_create_agent_behind_a_faultinjecting/)
that the run cannot separate "the 4B model reasons worse" from "the 4B model needs tighter
tool contracts". The stored run confirms it:

- 23 of the candidate's 26 failures are `ValueError: unknown SKU` from `check_stock`.
- In 21 of those 23, the model's first and only tool call was `check_stock` with the order
  id as the SKU (for example `sku: "ORD-103"`); it never called `lookup_order`. In the
  other 2 it looked the order up first and then passed a wrong SKU.
- The tool raises an exception. The retry middleware in this set-up handles only timeouts
  and runtime errors, so the model was never shown "unknown SKU" and had no chance to
  correct itself. One wrong call ended the trial.
- The baseline's first call was `lookup_order` in all 96 trials.

So this run measured: **the 4B model makes a wrong first call more often, in a set-up
where a wrong call is fatal.** It did not measure whether the 4B model can do the task
when a tool error is returned to it.

This file originally said of these failures: "This is a capability gap on one task type,
not a robustness gap." That sentence claimed more than was measured and is replaced below.
The verdict, the counts and the report are unchanged: BLOCK at round 1 stands for the
experiment as registered.

A second, separately pre-registered run asks the question the reader raised, with the tool
error returned to the model in both arms: `PREREGISTRATION-run-2.md`, result in
[`RESULT-run-2.md`](RESULT-run-2.md). The two runs answer different questions.

Run 2 ended INCONCLUSIVE after 5 rounds (2026-11-13): the 12B agent passed 480 of 480
trials and the 4B agent 428 of 480. Shown the error, the 4B model went on to look the order
up in 106 of the 108 trials that began with the wrong call, and 68 of those 108 passed.

## Where the candidate failed (descriptive, not part of the verdict)

| Condition | Candidate passed |
|---|---|
| clean | 18 of 24 |
| `tool_timeout` | 19 of 24 |
| `tool_error_once` | 18 of 24 |
| `empty_result` | 15 of 24 |

- 23 of the 26 failures are one behaviour: on "check stock and add a note" tasks the 4B
  model calls the stock tool with a SKU the order does not have, the tool raises
  `ValueError: unknown SKU`, and the run crashes. 2 more refund the wrong amount.
- All 26 failures are on the stock-note and plain-refund tasks; none on refund-with-note.
- **Fault accounting shows the same thing from another side:** the declared fault fired in
  24 of 24 baseline trials per faulted condition but only 18 to 20 of 24 candidate trials.
  The candidate sometimes never looked the order up at all, so the fault had nothing to
  hit. Without that table the faulted conditions would look like a fair comparison.
- The failures are not caused by the injected faults: the clean condition fails as often.
  They are wrong first tool calls on one task type, in a set-up that gave the model no
  chance to recover from them (see the correction above).

## What this run does and does not show

It shows that on this suite, as registered, the 4B model is worse than the 12B model by
more than the 10-point margin, with a stated bound of 2.5% on a false BLOCK under the
assumptions printed in the report (independence across cells and rounds; per-round seeds).
It does not show anything about other tasks, other prompts, or these models in general. One
round decided it, so the result rests on 96 pairs; every cell was run once.

The pilot at temperature 0 had the candidate ahead (79% against 67%). The difference is
the check: the pilot ran before the plain-refund check was corrected, which had been
failing the 12B model unfairly on all 8 refund tasks.
