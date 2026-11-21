# Result, run 4: BLOCK at round 4

The [registration](PREREGISTRATION-run-4.md) was committed at `142bb23` on 2026-11-21
at 11:34:47 UTC and pushed at 11:34:50 UTC. The wrapper started at 11:34:59 UTC.
The first main-study trial began after 11:35:03 UTC. The run ended at 11:40:09 UTC.
There was one registered start. Commit `5b77620` contains the [sealed store](runs-run-4/),
the [run log](run-4.log), the audit and both count files.

An independent agent recounted the raw records and checked the four registered conditions
without reading a write-up. Its log filter also displayed the tool's summary. The agent
computed its figures from the records. The orchestrator reran both registered count
scripts and `arci gate`. The count files are byte-identical, the recount agrees on the
figures it checked, and the gate reported `stored decision: MATCH`.

## Read this first

The explicit message is the baseline. The neutral message is the candidate. Both arms
used `qwen3.5:4b-mlx-ctx32k` and the same prompt, ending “Retry an empty lookup once.”
Both messages began “lookup_order returned an empty result.” Only the next sentence
differed.

- The explicit wording continued “Call lookup_order again with the same order_id.”
- The neutral wording continued “This lookup_order result is for the supplied order_id.”

**On these 8 cells, the neutral wording passes less often than the explicit wording by
more than 10 percentage points of mean pass rate**, under the registered assumptions.
The cells are the eight stock-note tasks under the empty-lookup condition, weighted
equally. This threshold decision applies to this model, this prompt and these two
wordings. The test stopped when it crossed the threshold and gives no estimate of size.

## What the tool printed

```
VERDICT: BLOCK (exit 1)
reason: regression established
stopping round: 4
pairs: 32 (64 trials)
baseline 30/32 passed, candidate 14/32 passed
counts: minus=16, zero=16, plus=0, errored=0
PASS wealth: 7.78663e-03; threshold: 40/1; crossed: False
BLOCK wealth: 6.41754e+01; threshold: 40/1; crossed: True
errored pairs: 0; tolerance: 4
candidate hard violations: 0
```

The first three rounds were INCONCLUSIVE. Round 4 produced a statistical BLOCK.
Neither arm had an errored trial, and no candidate hard violation forced the verdict.

## In plain numbers

A pass means the final order state, including the stock note, passed the registered check.

| Wording | Trials | Passed | Failed | Errored |
|---|---:|---:|---:|---:|
| Explicit (baseline) | 32 | 30 | 2 | 0 |
| Neutral (candidate) | 32 | 14 | 18 | 0 |

Of the 32 pairs, only explicit passed in 16, only neutral passed in 0, both passed in
14 and neither passed in 2.

| Task | Explicit passed / trials | Neutral passed / trials |
|---|---:|---:|
| desk-03 | 3/4 | 2/4 |
| desk-06 | 4/4 | 2/4 |
| desk-09 | 4/4 | 1/4 |
| desk-12 | 4/4 | 2/4 |
| desk-15 | 4/4 | 3/4 |
| desk-18 | 4/4 | 1/4 |
| desk-21 | 4/4 | 2/4 |
| desk-24 | 3/4 | 1/4 |

## What the agent did after the message

The injected empty result was delivered on a successful tool call in 31 of 32 trials
in each arm. The middleware replaced the empty result with the assigned text. It made
no retry of its own. These counts describe the agent's actions and decide nothing.

| After the empty result | Explicit | Neutral |
|---|---:|---:|
| Called `lookup_order` again | 31 of 31 | 14 of 31 |
| Passed among those calling again | 30 of 31 | 14 of 14 |
| Did not call it again | 0 of 31 | 17 of 31 |

All 17 trials without another lookup after the empty result failed. Across all assigned
trials, the first call was something other than `lookup_order` in 20 explicit and 14
neutral trials. An uninjected tool error occurred in 20 explicit trials (18 passed)
and 24 neutral trials (6 passed).

## Registered conditions

Both registered scripts produced identical count files.
[Count A](run-4-counts-a.json) · [Count B](run-4-counts-b.json) The log, the audit digest,
the comparison of events with sealed trials and the gate's recomputation supply the other
evidence for the four checks.

1. **HOLDS. Published registration and start checks.** The log records the published
   commit `142bb23`, unchanged registered files and all 16 file digests matching.
   Installed versions, middleware, texts and settings matched the registration. The
   Ollama server reported 0.32.14 and model ID `c01efed5a364`. The server digest and
   local model manifest SHA-256 both matched the registered value. After the run the
   active context was 32768.
2. **HOLDS. Replacement audit.** The [audit](run-4-audit.jsonl) has 62 lines and 62
   distinct call IDs. Each arm's 31 replacements match its 31 successful injections
   (`empty_result_delivered_ok`). The audit file and log trailer give the same SHA-256,
   `c53b18d1468eae9bb02fb88d5c0d2863f9095fbb1ce82027ae9b3502eed275bb`.
   The audit records middleware replacements. Its lines cannot identify individual trials
   or prove what reached a live model call. In a separate scripted run, paired client
   requests differed only in the replacement text wherever that reply appeared.
   [Scripted request check](../reviews/R10-run4-realpath-proof/RESULT.md)
3. **HOLDS. Terminations.** All 32 trials in each arm ended `completed`. Each arm had
   zero crashes, timeouts and budget stops, so 20 times its timeout and budget count
   was 0, within the registered limit of 32.
4. **HOLDS. Store and decision.** The manifest and store folder carry the registered
   experiment ID. All 1,001 events matched their sealed trial records in order across
   exactly 64 trial IDs. On this store, `arci gate` recomputed the decision and reported
   `stored decision: MATCH`.

The rule assumes independent pair differences across cells and rounds, a stable law in
each cell and no arm-order effect. If neutral's mean pass rate is at least explicit's
minus 10 points in every round, the chance of a statistical BLOCK under those assumptions
is at most 2.5%. Each mean covers that round's scenario instances. ARCI does not test
the assumptions.
The bound does not apply conditional on these checks passing or averaged over seeds.

## What weakens this, stated now

- The orchestrator saw 16 live smoke trials before the registration was pushed. Explicit
  passed 7 of 8 and neutral passed 4 of 8. This broke decision D-28's “before any trial”
  wording. The registration discloses it. The smoke trials had their own store and none
  entered this decision.
- Both arms ran on one shared local server, one after the other within a pair.
  **Corrected later on 21 Nov 2026:** this point first said that the explicit arm ran
  first in all 32 pairs. That was wrong. The store lists the explicit arm first in every
  pair, but the tool chooses which arm runs first from the rule digest, the cell and the
  round (`arm_order` in `suite_schedule.py`, release 2.4.1). Recomputed for this run: the
  explicit arm ran first in 16 pairs and the neutral arm in 16. The order of the lines in
  the audit file agrees. The consultant found the error; the orchestrator recomputed it.
  The verdict and every count are unchanged. Order effects are still not tested.
- One trial per arm never called `lookup_order`. Both were in round 2, explicit desk-24
  and neutral desk-12. Both failed and stayed in the analysis. With only 4 rounds,
  each task has 4 trials per arm. The table cannot establish a result for any one task.
- The neutral text is 7 characters longer and uses different words, including “supplied”
  where the explicit text says “same”. This comparison covers these two wordings on one
  model, with one prompt, on one machine, on one day.
- This was the fourth campaign on related data. The orchestrator selected the tasks and
  the fault after seeing run 2 and kept the explicit wording after run 3. The eight tasks
  use the same stock-note request with different order ids. There is no error guarantee
  across the four campaigns.
- Both INCONCLUSIVE predictions predated the smoke run. The orchestrator reports that
  seeing the smoke counts moved its expectation toward BLOCK before the registration was
  complete. Both recorded predictions were wrong. The maintainer supplied none.

## What is not claimed

The run cannot tell us why the explicit wording passed more often or whether naming the
next step helps in general. It gives no result for other models, tasks or conditions,
and no estimate of the size of the difference. Only the two fresh arms enter the test.
Comparing run 4's stopped counts with run 3's would not measure a wording effect.

**Registration errata** — none found.
