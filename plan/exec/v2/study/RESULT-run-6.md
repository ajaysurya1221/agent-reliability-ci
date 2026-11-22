# Result, run 6: BLOCK at round 3

On 2026-11-22 UTC, the [registration](PREREGISTRATION-run-6.md) was committed at
06:00:59 (`0ca504d`) and pushed at 06:01:01. The first wrapper started at 06:02:57.
Its warm-up waited for the end of standard input. It made no trial. The orchestrator
kept that start and registered one final start before either arm ran.
[First-start log](run-6.log) · [Amendment](PREREGISTRATION-run-6-second-start.md)

The amendment was committed at 06:59:16 (`80cb4b8`) and pushed at 06:59:19. The second
wrapper started at 06:59:22. The experiment ran from 06:59:29 to 07:01:42 UTC. Commit
`6528c82` contains the [sealed store](runs-run-6/) and [second-start log](run-6b.log).

An independent verifier recounted the raw records, checked all four registered conditions,
reconstructed the arm order and reran `arci gate`. Both registered counters produced
byte-identical output. Their counts agree with the recount.
[Count A](run-6-counts-a.json) · [Count B](run-6-counts-b.json)

## Read this first

Every trial began with the same scripted mistake. The script called `check_stock` with
the order ID as the SKU, got `Error: unknown SKU`, then called `lookup_order` with the
order ID. That lookup returned an injected JSON null. Only then did the model take over.
Both arms used `qwen3.5:4b-mlx-ctx32k` and the same prompt, ending “Retry an empty
lookup once.” The only change was the lookup reply in the model's history.

- Generic text (baseline) replaced the empty result with the following message.
  `The previous tool call returned an empty result. Repeat that call with the same input.`
- Raw null (candidate) showed the four characters `null`.

**Under the registered assumptions, BLOCK supports a raw-null shortfall greater than
ten percentage points in mean pass rate across the eight equally weighted tasks.**
The rule tests that margin. It gives no estimate of the size of the shortfall. This
comparison tests recovery after the scripted sequence. Run 6 did not measure how often
Qwen would choose either opening call on its own.

## What the tool printed

```
VERDICT: BLOCK (exit 1)
reason: regression established
stopping round: 3
pairs: 24 (48 trials)
baseline 18/24 passed, candidate 0/24 passed
counts: minus=18, zero=6, plus=0, errored=0
PASS wealth: 3.32516e-03; threshold: 40/1; crossed: False
BLOCK wealth: 1.93819e+02; threshold: 40/1; crossed: True
errored pairs: 0; tolerance: 4
candidate hard violations: 0
```

Rounds 1 and 2 were INCONCLUSIVE. BLOCK wealth rose from 5.02 to 20.68 to 193.82.
It first crossed 40 in round 3, before the registered cap of 30 rounds.

## In plain numbers

A pass required the exact stock note and an unchanged refund in the final order state.
Every assignment counted.

| Lookup reply | Trials | Passed | Failed | Errored |
|---|---:|---:|---:|---:|
| Generic text (baseline) | 24 | 18 | 6 | 0 |
| Raw null (candidate) | 24 | 0 | 24 | 0 |

Of the 24 pairs, only generic passed in 18 and both arms failed in 6. No pair had two
passes, a raw-null-only pass or an error.

| Task | Generic passed / trials | Raw null passed / trials |
|---|---:|---:|
| desk-03 | 3/3 | 0/3 |
| desk-06 | 2/3 | 0/3 |
| desk-09 | 2/3 | 0/3 |
| desk-12 | 3/3 | 0/3 |
| desk-15 | 2/3 | 0/3 |
| desk-18 | 1/3 | 0/3 |
| desk-21 | 2/3 | 0/3 |
| desk-24 | 3/3 | 0/3 |

## What the agent did after the opening

| Recorded behavior | Generic text | Raw null |
|---|---:|---:|
| Exact scripted opening followed immediately by the first model step | 24/24 | 24/24 |
| Scripted lookup delivered the injected null | 24/24 | 24/24 |
| Called `lookup_order` again after delivery | 24/24 | 0/24 |
| Passed among those calling again | 18 of 24 | 0 of 0 |
| Made no later lookup | 0/24 | 24/24 |
| Passed among those making no later lookup | 0 of 0 | 0 of 24 |

A later lookup counts with any arguments. Six generic trials repeated the lookup and
still failed the final-state check. The gate used every pair, regardless of retry.
In round 2 on desk-18, the generic arm retried, wrote `stock: 5` when stock was 46, and
issued a full refund on a task that requested only a stock note.

## Which arm ran first

The verifier used ARCI's `arm_order` with the rule digest, task index and round.
Generic ran first on desk-21 and desk-24 in round 1, on desk-06, desk-09 and desk-15 in
round 2, and on desk-18, desk-21 and desk-24 in round 3. Raw null ran first in the
other 16 pairs. Generic passed 6/8 when first and 12/16 when second. Store row order
does not record execution order.

## Registered conditions

1. **HOLDS. Publication and preflight.** Both registrations were pushed before any
   trial. The second-start log gives `80cb4b8` for both HEAD and the published commit.
   All 20 digests in each list matched the committed files. Pinned versions, middleware,
   arm settings and reply texts matched. Ollama 0.32.14 listed model ID `c01efed5a364`.
   The full server digest and local model manifest digest matched registration. The
   active context after the run was 32768.
2. **HOLDS. Live exposure.** All 48 openings matched, including the stock error, the
   injected null and the immediate handoff. The audit has 24 baseline replacements with
   24 distinct call IDs, matching the baseline delivery count, and zero candidate entries.
   The first-exchange file has one matching receipt per arm, task and seed, with no extras.
   The observer checked all six messages, including the prompt, task, call arguments and
   assigned reply, and a completed assistant response on that request. Both files'
   SHA-256 digests matched the log.
   [Replacement audit](run-6-audit.jsonl) · [Receipts](run-6-first-exchanges.jsonl)
3. **HOLDS. Terminations.** All 24 trials in each arm ended `completed`. Each arm had
   zero crashes, timeouts and budget stops. Both met the registered limit, 20 × 0 ≤ 24.
4. **HOLDS. Store and decision.** The sealed manifest and store directory matched the
   registered experiment ID. All 590 events matched their sealed trials in order, with
   no missing or extra events or trial IDs. The verifier's gate recomputation returned
   `stored decision: MATCH` with exit code 1.

The rule assumes independent pair differences across tasks and rounds, a stable law
within each task and no arm-order effect. Under those assumptions, if raw null trails
by at most ten points on average over each round's scenarios in every round, the chance
of a false statistical BLOCK is at most 2.5%. The bound does not average over seeds or
condition on the four checks passing.

## What weakens this, stated now

- The script chose both opening calls. The model chose only what came next. Receipts
  retain match flags for the first exchange, without the full live request bodies.
- One model, one prompt, eight tasks sharing one stock-note sentence with different
  order IDs. This was the sixth campaign on related data. The error bound covers this
  registered comparison alone.
- The client supplied no sampling seed. Both arms used one server and raw null ran first
  in 16/24 pairs. The run cannot establish independence, stability or absence of order
  effects.
- One agent wrote the blind tests and then implemented the code. The local model server
  had stopped. An initial guard refused to start, and the server was started again before
  the guard check passed. The laptop logged AC power before and after the registered run.
- The consultant and the orchestrator each predicted BLOCK before any trial. Both
  predictions matched. The maintainer supplied no prediction.
- The run 5 recount had already found recovery after model-chosen wrong starts followed
  by a delivered empty lookup. That subset was identified after the run. Both forecasters
  had also been wrong on runs 4 and 5.

## What is not claimed

The result leaves policy versus capability open. It cannot tell us whether the model
would recover the same way from a wrong call of its own. The retry counts do not show
learning or why a retry succeeded. There is no per-task verdict, estimate of absolute
reliability or claim of general superiority. The 12B model was in neither arm, and the
result does not extend to other tasks, prompts or models.

**Registration errata.** The original no-restart rule was amended after the first
start stopped at warm-up without a trial. The amendment changed the wrapper and its
recordkeeping. The opening, arms, predictions and decision rule stayed as registered.
