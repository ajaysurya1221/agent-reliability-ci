# Result, run 3: BLOCK at round 2

Pre-registration: `PREREGISTRATION-run-3.md`, committed at `c217ae6` and pushed at
2026-11-16 21:40:02 +05:30. The wrapper started 19 seconds later (21:40:21), the first
trial after 21:40:24, and the run ended at 21:42:27. These times come from the run log and
the file system; the store holds no absolute time. One start. Store:
`runs-run-3/order-desk-qwen3.5-4b-empty-lookup-text@4413b7e2f81abc51d3576fce3d0de4974f5c25c820af06c62a5e0d0f6e969504`.
Log: `run-3.log`. Report as the tool renders it: `report-run-3.md`.

Checked after the run by three agents working separately
(`../reviews/R8-run3-result-verify-workflow.json`): a recount from the store by an agent
that read no write-up (every count below came out the same), an audit of the registered
conditions from the raw files (all hold; errata below), and a sentence-by-sentence
check of this file (its corrections are applied).

## Read this first: the roles are swapped

The arm WITH the message is the baseline; run 2's set-up is the candidate. The tool
printed "VERDICT: BLOCK (exit 1)" with "reason: regression established". In this run that
reads: **on these 8 cells, run 2's set-up passes less often than the set-up with the
message, by more than 10 points of mean pass rate.** The registration's short form was
"the message is worth more than 10 points on these 8 cells". Stated exactly: under its
assumptions, the registered test supports a mean pass-rate advantage of more than 10
percentage points on these eight selected cells, for this model, this prompt and this one
wording. This is a threshold decision, not an estimate of the size.

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

These are its first ten lines. It also printed its condition for per-round seeds, "there
is no guarantee averaged over seeds", "The bound covers statistical BLOCK only", and the
two earlier runs; see `run-3.log`.

It is a statistical BLOCK: no hard violation, no errored pair. Round 2 is the earliest
round at which this rule can give a statistical verdict (PASS or a statistical BLOCK) on 8
cells; only an ERROR or a BLOCK forced by a hard violation can come at round 1. `arci gate`
on the store recomputes the decision and reports "stored decision: MATCH".

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
   the message has `empty_result_delivered_ok` = 16. The audit records replacements made
   by the middleware, not what the model received; its lines cannot be tied to single
   trials, so the matching counts are supporting evidence only.
3. **Terminations.** All 32 trials have the termination `completed`: no crash, no
   time-out, no budget stop.
4. **Identity and recomputation.** The store's manifest carries the expected experiment
   id, and `arci gate` reports that the recomputed decision matches the stored one.

These checks do not establish the independence assumptions behind the 2.5% bound, and they
do not give a 2.5% error rate conditional on passing them.

## Errata to the pre-registration

**1. The wrapper changed after the smoke run.**

The pre-registration says of the smoke run: "The registered files are the files the smoke
run used. Nothing was changed after it." That is not true of the wrapper `run-3.sh`. After
the smoke run and before the registration commit the wrapper gained its start guards (the
one-start marker, the checks that the registration is committed and published, the checks
of the versions and of the model id, the stop on a failed warm-up call) and a check-only
mode. The study folder itself (`agent.py`, the descriptor, the tasks, the tools, the
check) was not changed after the smoke run, as far as file times show; git holds no state
from the time of the smoke run. The registered digest of the wrapper is the digest of the
version that ran.

**2. One number about run 2 is wrong.** The pre-registration says: "32 of its 34 failures
under the empty result were on these tasks". Run 2's store gives 33 of 34 (the candidate
passed 7 of 40 on these cells, so 33 failed; the 34th failure was on another task). 32 is
the number of those failures in which the model got the empty result and did not read the
order again. The plan the maintainer approved carried the same slip. It does not change
the grid, the rule or the verdict. Found by the check of the public write-up
(`../reviews/R10-run3-public-section-check-workflow.json`).

Also not in the registration's text, and done: one guard-only run of the wrapper
(`run-3-check.log`) before the start; and the warm-up call outside the experiment was the
prompt "Reply with the single word ok." sent with the command-line client and its default
thinking mode.

## Registered counts (they decide nothing)

Computed by `counts-run-3/count_a.py` and `count_b.py`; the two outputs are identical
(`run-3-counts-a.json`, `run-3-counts-b.json`), and the blind recount agrees.

| Count | With the message | Run 2's set-up |
|---|---|---|
| Trials | 16 | 16 |
| Passed | 15 | 2 |
| Failed | 1 | 14 |
| Errored | 0 | 0 |
| Termination `completed` | 16 | 16 |
| Ended on a budget or the time limit | 0 | 0 |
| First call was not `lookup_order` | 9 | 11 |
| Never called `lookup_order` | 0 | 1 |
| Empty result delivered | 16 | 15 |
| Empty result delivered, call successful | 16 | 15 |
| Then read the order again | 16 (15 passed) | 2 (2 passed) |
| Then did not read it again | 0 | 13 (0 passed) |
| Trials with a tool error that was not injected | 9 (8 passed) | 14 (1 passed) |

Fault accounting (the tool's report): the injected empty result fired in 16 of 16 trials
of the arm with the message and in 15 of 16 trials of run 2's set-up; in the remaining
trial (round 2, desk-06) the model made no tool call.

Passes per task, with the message then without: desk-03 2 and 0; desk-06 2 and 0; desk-09
2 and 1; desk-12 2 and 0; desk-15 2 and 0; desk-18 1 and 0; desk-21 2 and 0; desk-24 2
and 1 (2 trials per task and arm).

## What this supports

On these 8 cells (the 8 stock-note tasks under the injected empty result), with this 4B
model, this prompt and temperature 0.7, the registered test decided that the arm in which
the `null` of the empty lookup is replaced by the registered message passes more often
than the arm with `null`, by more than 10 points of mean pass rate over the 8 cells.

Under the rule's assumptions (independent cells and rounds, the same law in every round,
no effect of which arm runs first), the chance of a statistical BLOCK is at most 2.5% if,
in every round, the mean gain over that round's scenario instances on these 8 cells is 10
points or less. ARCI does not check those assumptions, and there is no guarantee averaged
over seeds. This is a third campaign on related data, chosen after seeing runs 1 and 2;
the bound applies to this registered experiment alone, and no error guarantee across the
three campaigns is claimed.

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

2 minutes 3 seconds from the start of the run to its end, one worker, local models only.
The 32 trials took 122 seconds of trial time in all; the longest took 6.2 seconds.
