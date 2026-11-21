# Result, run 5: PASS at round 13

On 2026-11-21 UTC, the [registration](PREREGISTRATION-run-5.md) was committed at
15:28:24 (`6c0a5a0`) and pushed at 15:28:27. The orchestrator reports no live run 5 trial
before registration. The log records the wrapper start at 15:28:33 UTC and the run start at
15:28:39 UTC. The run ended at 15:45:38. There was one start. Commit `addddde` contains
the [sealed store](runs-run-5/), [run log](run-5.log), audit and both count files.

An independent agent recounted the raw records without reading a write-up, checked the
four registered conditions, recomputed arm order and reran `arci gate`. The orchestrator
checked that both registered counters produced identical files. The recount agrees.

## Read this first

The reader asked what happens if the message tells the agent to retry without naming
the call. Both arms used `qwen3.5:4b-mlx-ctx32k` with the same prompt, ending “Retry
an empty lookup once.” After an empty lookup, the middleware supplied the assigned text.

- Named (baseline)
  `lookup_order returned an empty result. Call lookup_order again with the same order_id.`
- Generic (candidate)
  `The previous tool call returned an empty result. Repeat that call with the same input.`

**Across these eight equally weighted cells, under the registered assumptions, PASS supports
a generic shortfall smaller than ten percentage points, a tie or a lead.** The rule tests a
threshold and gives no estimate of the difference. The 16 pairs favoring generic against 10
favoring named do not establish that generic is better. The rule never tested that.

## What the tool printed

```
VERDICT: PASS (exit 0)
reason: non-inferiority established
stopping round: 13
pairs: 104 (208 trials)
baseline 86/104 passed, candidate 92/104 passed
counts: minus=10, zero=78, plus=16, errored=0
PASS wealth: 8.52657e+01; threshold: 40/1; crossed: True
BLOCK wealth: 5.36931e-03; threshold: 40/1; crossed: False
errored pairs: 0; tolerance: 4
candidate hard violations: 0
```

Rounds 1 through 12 were INCONCLUSIVE. Round 13 was the first to cross the PASS threshold.

## In plain numbers

A pass means the final order state, including the exact stock note, passed the check.
Every assigned trial counts, including those in which the agent never called the lookup.

| Wording | Trials | Passed | Failed | Errored |
|---|---:|---:|---:|---:|
| Named (baseline) | 104 | 86 | 18 | 0 |
| Generic (candidate) | 104 | 92 | 12 | 0 |

Of the 104 pairs, only named passed in 10, only generic passed in 16, both passed in 76
and neither passed in 2.

| Task | Named passed / trials | Generic passed / trials |
|---|---:|---:|
| desk-03 | 10/13 | 11/13 |
| desk-06 | 12/13 | 11/13 |
| desk-09 | 9/13 | 11/13 |
| desk-12 | 8/13 | 9/13 |
| desk-15 | 13/13 | 13/13 |
| desk-18 | 11/13 | 13/13 |
| desk-21 | 11/13 | 11/13 |
| desk-24 | 12/13 | 13/13 |

## What the agent did after the message

| Recorded behavior | Named | Generic |
|---|---:|---:|
| Successful lookup delivered the injected empty result | 100 of 104 | 103 of 104 |
| Called `lookup_order` again after that result | 97 of 100 | 103 of 103 |
| Passed among those calling again | 86 of 97 | 92 of 103 |

All 3 named trials that received the empty result and never called again failed.
Another 4 named trials and 1 generic trial never called the lookup at all. All failed.
These counts describe later calls and decide nothing. A later call could already have
been queued when the empty result arrived.

## Which arm ran first

The tool chose the order for each pair. The independent agent used the tool’s own
`arm_order` function with the rule digest, cell and round. Named ran first in 56 pairs
and generic in 48. Omitting the trials with no lookup gives the same sequence of arm
labels as the audit. The store’s row order does not record which arm ran first.

## Registered conditions

Both registered count scripts gave byte-identical files with the full fault and retry
counts. [Count A](run-5-counts-a.json) · [Count B](run-5-counts-b.json)

1. **HOLDS. Published registration and start checks.** The log shows HEAD and the
   published commit both at `6c0a5a0`, the registered files unchanged and all 16
   digests matching. Software versions, middleware, texts and settings matched.
   Ollama server 0.32.14 reported model ID `c01efed5a364`. The server digest and local
   model manifest SHA-256 both matched the registered value. The active context after
   the run was 32768.
2. **HOLDS. Replacement audit.** The [audit](run-5-audit.jsonl) has 203 lines with
   203 distinct call IDs. Its 100 named and 103 generic replacements equal each arm’s
   successful empty-result deliveries. The file and the log give the same SHA-256,
   `5f0578ccc5c7d7a5e041102d7f6ebd9fe3a609b97e0d9b6b3f2b22d7324d4e24`.
   The audit records middleware replacements. It cannot identify a trial or prove live
   model receipt. In the scripted check, all 80 first-request pairs matched byte for
   byte. All 320 later pairs matched after replacing only the first lookup reply.
   [Scripted request check](../reviews/R11-run5-realpath-proof/RESULT.md)
3. **HOLDS. Terminations.** All 104 trials in each arm ended `completed`. Each arm had
   zero crashes, timeouts and budget stops. In each, 20 times the number ending in
   timeout or budget was 0, within the limit of 104.
4. **HOLDS. Store and decision.** The manifest and store folder match the registered
   experiment ID. All 3,638 events matched the ordered events in the sealed trials
   across exactly 208 trial IDs. The gate recomputed the decision and reported
   `stored decision: MATCH`.

The rule assumes independent pair differences across cells and rounds, a stable law in
each cell and no arm-order effect. If generic trails named by at least 10 points on
average over each round’s scenario instances in every round, the chance of a false PASS
is at most 2.5% under those assumptions. ARCI does not test them. The bound does not
apply conditional on the four checks passing or averaged over seeds.

## Run 4 and run 5 side by side

| Wording | Run 4 passed / trials | Run 5 passed / trials |
|---|---:|---:|
| Named retry | 30/32 | 86/104 |
| Neutral message | 14/32 | — |
| Generic retry | — | 92/104 |

These are separate runs with different seeds. Comparing their stopped counts cannot
establish a wording effect. Only the two fresh run 5 arms entered this decision.

## What weakens this, stated now

- The named message passed 30 of 32 in run 4 and 86 of 104 here. Pass rates on these
  cells move between runs.
- Both messages ask for the same input. The generic message refers back to the preceding
  call. Both sentences change, including the verb, the references and the word count. The
  test compares the two complete messages.
- The tasks and fault were chosen after run 2. The named wording was retained after run 3.
  Both scripted histories still showed the preceding tool name and arguments.
- One model, one prompt, one machine, one day. The eight tasks use one stock-note
  sentence with eight order IDs. This was the fifth campaign on related data, with no
  error guarantee across the five.
- The consultant and the orchestrator both predicted INCONCLUSIVE. Both were wrong
  again, as in run 4.
- The wrapper changed after the last review. Only check mode and this one start
  exercised its guards.

## What is not claimed

PASS does not show that the generic wording is better or explain why either wording
works. The run cannot settle whether the gap in runs 1 and 2 came from policy or
capability. The 12B model was in neither arm, and capability was never measured.
The retry counts cannot show that retrying caused the passes. The result gives no
per-task verdict and does not extend to other models, tasks or conditions.

**Registration errata** — none found.
