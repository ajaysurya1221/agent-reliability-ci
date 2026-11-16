# Result, run 3: BLOCK at round 2

**Status of this file: draft.** The verdict, the counts and the four conditions below were
checked by the orchestrator. An independent recount, an audit of the conditions and a
sentence-by-sentence check were started and had not reported when this was committed
(output expected in the session's task file `wwdtk1unu`). Astra has not yet been consulted
on this write-up. Nothing here has been published outside this branch.

Pre-registration: `PREREGISTRATION-run-3.md`, committed at `c217ae6` and pushed at
2026-11-16 21:40:02 +05:30. The wrapper started 19 seconds later (21:40:21), the first
trial after 21:40:24, and the run ended at 21:42:27. One start. Store:
`runs-run-3/order-desk-qwen3.5-4b-empty-lookup-text@4413b7e2f81abc51d3576fce3d0de4974f5c25c820af06c62a5e0d0f6e969504`.
Log: `run-3.log`. Report as the tool renders it: `report-run-3.md`.

## Read this first: the roles are swapped

The arm WITH the message is the baseline; run 2's set-up is the candidate. The tool
printed "BLOCK, regression established". In this run that reads: **on these 8 cells, the
message is worth more than 10 points of mean pass rate.**

## What the tool printed

```
VERDICT: BLOCK (exit 1)
reason: regression established
stopping round: 2
pairs: 16 (32 trials)
baseline 15/16 passed, candidate 2/16 passed
counts: minus=13, zero=3, plus=0, errored=0
PASS wealth: 1.29680e-02; threshold: 40/1; crossed: False
BLOCK wealth: 4.27909e+01; threshold: 40/1; crossed: True
errored pairs: 0; tolerance: 4
candidate hard violations: 0
```

It is a statistical BLOCK: no hard violation, no errored pair. Round 2 is the earliest
round at which this rule can give any verdict on 8 cells. `arci gate` on the store
recomputes the decision and reports "stored decision: MATCH".

## In plain numbers

| | Trials | Passed |
|---|---|---|
| With the message (baseline arm) | 16 | 15 |
| Run 2's set-up, `null` (candidate arm) | 16 | 2 |

Of the 16 pairs: in 13 only the arm with the message passed; in 2 both passed; in 1 both
failed; in none did only run 2's set-up pass.

The run stopped early, at its second look. 15 of 16 and 2 of 16 are counts from a run that
stopped as soon as the rule was met. They are not estimates of the two pass rates, and no
confidence interval is given for them.

## The four conditions for reading the verdict as a statement about the message

All four hold.

1. **The wrapper's checks at the start passed.** `run-3.log`: the registration committed,
   unchanged and published (`c217ae6`); 17 of 17 digests; the registered versions; the
   model id `c01efed5a364`.
2. **Delivery.** The audit file has 16 lines with 16 distinct call ids, and the arm with
   the message has `empty_result_delivered_ok` = 16.
3. **Terminations.** All 32 trials have the termination `completed`: no crash, no
   time-out, no budget stop.
4. **Identity and recomputation.** The store's manifest carries the expected experiment
   id, and `arci gate` reports that the recomputed decision matches the stored one.

These checks do not establish the independence assumptions behind the 2.5% bound.

## Registered counts (they decide nothing)

Computed by `counts-run-3/count_a.py` and `count_b.py`; the two outputs are identical
(`run-3-counts-a.json`, `run-3-counts-b.json`).

| Count | With the message | Run 2's set-up |
|---|---|---|
| Trials | 16 | 16 |
| Passed | 15 | 2 |
| Errored | 0 | 0 |
| Termination `completed` | 16 | 16 |
| First call was not `lookup_order` | 9 | 11 |
| Never called `lookup_order` | 0 | 1 |
| Empty result delivered, call successful | 16 | 15 |
| Then read the order again | 16 (15 passed) | 2 (2 passed) |
| Then did not read it again | 0 | 13 (0 passed) |
| Trials with a tool error that was not injected | 9 (8 passed) | 14 (1 passed) |

Passes per task, with the message then without: desk-03 2 and 0; desk-06 2 and 0; desk-09
2 and 1; desk-12 2 and 0; desk-15 2 and 0; desk-18 1 and 0; desk-21 2 and 0; desk-24 2
and 1 (2 trials per task and arm).

## What this supports

On these 8 cells (the 8 stock-note tasks under the injected empty result), with this 4B
model and this prompt, replacing the `null` of the empty lookup with the registered message
raised the mean pass rate by more than 10 points. Under the rule's assumptions, the chance
of this verdict when the true gain is 10 points or less is at most 2.5%; ARCI does not
check those assumptions, and with per-round seeds the bound needs the null to hold in
every round's scenario instances.

## What it does not support

- Nothing about the 12B model or "the gap": it was in neither arm.
- Nothing about capability or cause, and not that naming the next step is what helped.
  The run compared one message with `null`. A message of the same length that names no next
  step was not tested.
- Nothing about the other 16 tasks, the other three conditions or the full suite. The 8
  cells and the condition were chosen from run 2's results.
- No statement about how large the gain is beyond "more than 10 points on these cells".
- No comparison with run 2's counts as an effect: other seeds, another release.
- The smoke run (6 of 8 and 3 of 8) is not evidence and is not pooled with this.

## What was not run

The code-retry variant. A scripted test with no model
(`order-desk-empty-message/tests/test_code_retry_demo.py`) shows how a code retry behaves:
the empty lookup is followed by one more recorded `lookup_order` call with no model step
between, and the model then receives the order.

## Time

2 minutes 3 seconds from the first trial to the end, one worker, no spend. About 4 seconds
a trial.
