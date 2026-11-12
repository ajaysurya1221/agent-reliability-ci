# Result of the second pre-registered run (run 2, 2026-11-13)

Pre-registration: `PREREGISTRATION-run-2.md` (pushed at `6fbdb1c`, 02:30:42 +05:30; the
first trial started at 02:30:48). Store:
`runs-run-2/order-desk-gemma4-12b-vs-qwen3.5-4b-recoverable@eaa438b1…/`.
Reports: `report-run-2.md`, `report-run-2.html`. Log: `run-2.log`.
Wall time 76 min 47 s, one worker, no spend. As for run 1, the store (6.9 MB) and the log
are kept on the maintainer's machine and are not in the repository; the reports are.

Run 2 asks the question a reader raised about run 1 (`RESULT.md`, correction of
2026-11-13): **when a tool's error is shown to the model instead of ending the trial, is
the 4B agent within 10 points of the 12B agent?** The one change from run 1 is a small
middleware, the same in both arms, that returns a tool's `ValueError` to the model as an
error message. Run 1's verdict stands for run 1's set-up. The two runs answer different
questions.

## Verdict: INCONCLUSIVE after 5 rounds. My written expectation (INCONCLUSIVE, low confidence) was right.

| | Baseline `gemma4:12b-mlx` | Candidate `qwen3.5:4b-mlx` |
|---|---|---|
| Trials passed | 480 of 480 | 428 of 480 (89.2%) |
| Median seconds per trial (last recorded event) | 3.9 | 4.6 |

Pairs: 52 where only the baseline passed, 428 ties, 0 where only the candidate passed, 0
errored. BLOCK wealth 0.49 and PASS wealth 0.020, against the threshold 40. Neither test
came near crossing. `arci gate` re-derives the same decision from the store.

INCONCLUSIVE means what it says: this run does not show the 4B agent is within the margin,
and does not show it is outside it. The observed gap, 10.8 points, sits almost on the
10-point margin, which is the case this test needs the most pairs for. The registered
budget was 5 rounds and it is not extended after the fact.

## What changed against run 1 (descriptive, not part of the verdict)

| | Run 1 (wrong call ends the trial) | Run 2 (error shown to the model) |
|---|---|---|
| Candidate trials passed | 70 of 96 (72.9%) | 428 of 480 (89.2%) |
| Verdict | BLOCK at round 1 | INCONCLUSIVE after 5 rounds |
| Injected fault fired, candidate, per faulted condition | 18 to 20 of 24 | 119 to 120 of 120 |

The runs differ in more than the middleware (run 2 has five rounds, so different seeds),
so this table is a description, not a measured effect of the change.

## The breakdown the reader asked for (descriptive)

Per arm, over 480 trials each:

| | Baseline | Candidate |
|---|---|---|
| Never called `lookup_order` | 0 | 2 (both failed) |
| First tool call was not `lookup_order` | 0 | 108 (all `check_stock`) |
| Got a tool error of its own making, then passed | 0 | 77 |
| Got a tool error of its own making, then failed | 0 | 47 |

"A tool error of its own making" is a tool call that failed without an injected fault: 124
candidate trials had at least one (115 with `check_stock`, 9 with `issue_refund`). In 112
of the 115 failed `check_stock` calls the model passed the order id as the SKU.

- **The wrong first call is as common as before.** On the stock-note tasks the 4B model
  called `check_stock` first in 108 of 160 trials. The 12B model never did.
- **Shown the error, it usually recovers.** In 106 of those 108 trials it went on to look
  the order up, and 68 of the 108 passed. In run 1 every one of these would have crashed.
- **So "skipped the lookup" in run 1 was mostly "never got the chance".** Only 2 of 480
  candidate trials ended without ever calling `lookup_order`.

## Where the candidate still failed

All but one of the 52 failures are on the stock-note tasks (51; the other is a plain
refund). By condition:

| Condition | Candidate passed, all tasks | Stock-note tasks only |
|---|---|---|
| clean | 114 of 120 | 34 of 40 |
| `tool_timeout` | 118 of 120 | 38 of 40 |
| `tool_error_once` | 110 of 120 | 30 of 40 |
| `empty_result` | 86 of 120 | 7 of 40 |

- **The failures concentrate where two things go wrong in one trial.** On stock-note tasks
  under `empty_result`, the 4B model made the wrong first call in 26 of 40 trials and
  passed none of those 26. In 21 of them it got "unknown SKU", looked the order up once,
  got the injected empty result, and stopped. Under the clean and `tool_timeout` conditions the
  same wrong first call was followed by a pass in 52 of 58 trials.
- Under `empty_result` the 12B model called `lookup_order` a second time in all 120
  trials. The 4B model did so in 87 of 120.
- Fault accounting: every declared fault fired in 120 of 120 baseline trials and in 119 or
  120 of 120 candidate trials. Unlike run 1, the faulted conditions here are a like-for-like
  comparison.

These cuts were chosen after seeing the data. They describe this run and decide nothing.

## What this run does and does not show

It shows that returning tool errors to the model removes most of the gap that run 1
measured, on this suite. It does not show the 4B agent is an acceptable replacement: the
test did not reach PASS, and one cell family (stock-note tasks with an empty lookup) fails
far more often than the rest. It does not show anything about other tasks, other prompts,
or these models in general. It is one run on one machine with two local models.

Thanks to u/Significant_Tune9219 for the comment that led to this run, and to
u/ChemicalExcellent463 for asking what the 4B model did when it skipped the lookup.
