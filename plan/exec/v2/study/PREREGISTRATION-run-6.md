# Run 6 draft registration — recovery after a wrong stock call and an empty lookup

Prepared 22 Nov 2026. Fill the predictions and publish the final registration, code
and digests before the first live trial. Record the push commit and UTC time in the result.

## The reader's question

Agentic Affairs asked on dev.to on 22 Nov, in reply to the run 5 result:

> The generic arm beating named 92 to 86 is the result I'd underline — it kills the
> intuition that more specific wording is always better, and with retry rates at 97/100 and
> 103/103 the retry policy is clearly learned now, not missing. That leaves the compound
> case as the real open question: wrong first call plus an empty lookup was 0 of 26 in run
> 1, and run 5 doesn't isolate it. Would run 6 test the compound with the generic message,
> or is the 12B comparison the next step to settle policy versus capability?

## What the existing results answer

Run 1 had 26 total 4B failures. In 21, its first and only call checked stock with the
order id as the SKU and crashed. The 0/26 belongs to the run 2 4B stock-note tasks.
Both arms then returned tool ValueErrors to the model.
Of 40 assignments to the empty-first-lookup condition, 39 received the injected null.
Of 26 wrong starts, 25 received it and none passed. Across conditions, 106/108 wrong
starts reached lookup and 68/108 passed. Rounds and seeds differed between runs,
limiting attribution to error handling.

Run 5 gave both arms a retry instruction. Generic passed 92/104 and named 86/104.
PASS supported a generic shortfall smaller than ten points, a tie or a lead. The
later-lookup counts, 97/100 named and 103/103 generic, include calls that could have
been queued before the message arrived. They measure behavior under those prompts.
The study did not test superiority or learning.

The consultant's post-hoc run 5 recount found 65/74 generic and 54/62 named passes
after an initial unknown-SKU error followed by a delivered empty lookup. Recovery
already occurred. These model-selected subsets were outside the registered decision.
Run 3 compared raw null with a named retry, across all assignments. Run 4 compared
two named messages. Neither isolates this sequence with generic guidance against null.

The 12B passed 96/96 in run 1 and 480/480 in run 2. The 24 tasks spanned clean,
timeout, one-shot tool error and empty-lookup conditions. The 12B repeated all 120
empty lookups in run 2. Its response to a replacement message has never been tested.
Those records leave this 4B comparison open. D-29 permits one registered run for
this public question. The descriptor lists runs 1–5. There is no error guarantee
across the six campaigns. Only the two fresh arms enter this decision.

## What every assignment tests

Use the eight stock-note tasks desk-03/06/09/12/15/18/21/24. Each uses the same
request with a different order id. Both arms use ollama:qwen3.5:4b-mlx-ctx32k at
temperature 0.7, reasoning off. Keep the run 5 system prompt, including its final
“Retry an empty lookup once.” Keep the tools, one timeout/runtime-error retry,
ReturnToolErrors and the independent final-state check. Each trial starts fresh.

1. Script check_stock(sku=order_id). The real tool raises ValueError("unknown SKU").
   Its returned tool message reads exactly `Error: unknown SKU`.
2. Script lookup_order(order_id=order_id). Register a single fault, empty_result on
   lookup_order, occurrence 0. ARCI records its successful result as JSON null.
3. Hand control to Qwen. Its first request includes the task, both assistant calls
   with arguments and both tool replies. The stock error is identical in both arms.
   Baseline (generic-retry-text) replaces the empty lookup reply with this exact text:

`The previous tool call returned an empty result. Repeat that call with the same input.`

Candidate (raw-null) has no replacement middleware. Its tool reply contains the four
characters `null`. The tool call remains visible in both histories. Qwen chooses
subsequent requests. Middleware may retry timeout/runtime errors. Report later lookup
attempts with any arguments. Grade completed trials on final state and retain every
termination. The oracle requires the exact stock note and unchanged refund. Delivery
and retry counts never filter the statistical comparison.

ScriptedOpening.wrap_model_call in order-desk-compound/agent.py returns one assistant
tool call on each of the first two graph turns. LangChain executes each through the
released ARCI adapter. The third turn forwards the accumulated history to the model.
The opening consumes two of the 12 tool calls and zero of the 12 model steps. The
trial has 120 seconds including the opening. The grader has 20 seconds.

With exposure verified under reading condition 2, this measures recovery after that start.
How often Qwen chooses the wrong call, how it would phrase or batch its own calls,
and whether it would choose the first lookup after its own error are outside the test.

## Decision and stopping rule

Estimate no effect size. Test the equally weighted mean pass-rate difference, raw null
minus generic, over the eight registered cells. Report ARCI's reason with its verdict.

- A statistical BLOCK supports a raw-null shortfall greater than ten percentage points.
  A candidate hard-violation BLOCK gives no statistical conclusion about the reply.
- PASS supports a shortfall smaller than ten points, a tie or a lead. Even two arms
  that fail every assignment can pass the relative rule.
- INCONCLUSIVE leaves the margin question open. ERROR gives no statistical conclusion.
  Neither PASS nor BLOCK distinguishes policy from capability.

Use one worker. Each round has eight pairs with per_round scenario seeds. Both arms
share the scenario seed in each pair, use reset state in separate processes, and run
consecutively on the same server. The client supplies no sampling seed. ARCI chooses
arm order from the rule digest, cell and round. Store row order does not give execution
order.

Register alpha 1/20, margin 1/10, stakes 1/4 and 1/2, threshold 40 in each direction.
Inspect only complete round ends. Stop at the first PASS, BLOCK or ERROR. Stop
INCONCLUSIVE at 30 rounds if still undecided (240 pairs, 480 trials). Retain errored
pairs without retry. Each scores −1 for PASS and +1 for BLOCK. Four are tolerated.
The fifth yields ERROR at round end before other verdicts.

Assume independent pair differences across cells and rounds, a stable law within
each cell and no arm-order effect. The arms within a pair may depend on each other.
Under these assumptions the false-PASS bound is 2.5% if raw null trails by at least
ten points on average over each round's scenario instances in every round. The false
statistical BLOCK bound is 2.5% if the shortfall is at most ten points in every round.
Both apply at the margin. These bounds are neither seed-averaged nor conditional on
the delivery checks. ARCI does not establish the assumptions.

## Planner projections

Assume generic passes 85% in every cell. Each row gives a hypothetical raw-null
rate. For this table only, also assume independent arms, identical joint laws in all
cells and rounds, and zero errors and hard violations. Values and pairs are rounded.

| Raw null | PASS | BLOCK | INCONCLUSIVE | Expected pairs |
|---:|---:|---:|---:|---:|
| 20% | <0.001 | >0.999 | <0.001 | 26 |
| 40% | <0.001 | >0.999 | <0.001 | 43 |
| 55% | <0.001 | 0.986 | 0.014 | 92 |
| 65% | <0.001 | 0.475 | 0.525 | 192 |
| 75% | 0.012 | 0.011 | 0.978 | 237 |
| 85% | 0.633 | <0.001 | 0.367 | 172 |

From the suite folder, use the registered environment and the following command
for each candidate rate C, as a fraction. A = 0.85 × C + 0.15 × (1 − C).

`python -m arci plan arci.yaml --baseline-rate .85 --candidate-rate C --agreement A`

At the historical run 5 pace, 26 pairs would take about four minutes and the cap
about 39 minutes. The new opening and subsequent model choices can change the pace.

## Identity, software and offline evidence

The expected experiment id joins the suite id and digest below with one `@`:

`order-desk-qwen3.5-4b-compound-generic-retry`

`1399fb1d45ce14c2bdf8c973a77291a4f9dcdfc1b350c95259808b96855ab838`

Use Python 3.13.12, ARCI 2.4.1, langchain 1.4.10, langchain-core 1.7.7,
langgraph 1.2.20, langgraph-prebuilt 1.1.1, langchain-ollama 1.1.0, ollama client
0.6.3 and pydantic 2.14.3. Require Ollama server 0.32.14, short id c01efed5a364
and the following full SHA-256 in both the server listing and local manifest:

`c01efed5a36459ab6ffffa0b158636a014d8b30b4d5493167cba9916ed558430`

Run 6 uses no live smoke. The draft was built using the prior results, design,
D-29, run 5 study files and released environment. The offline checks used stand-ins.

- The worker captured stand-in inputs. Separate blind tests checked false success
  claims and fault withholding.
- One agent wrote the blind interface note first, its tests second, and the
  implementation afterwards. These tests have no independent author.
- R12 captured 80 first requests per arm. Each contained both genuine exchanges.
  All 320 paired request bodies matched byte for byte after changing only the lookup
  reply. All 160 first-exchange receipts matched the assignments and recorded a
  completed stand-in assistant response. All 640 requests stayed in process.
  See ../reviews/R12-run6-realpath-proof/.
  The compressed capture has SHA-256
  `c54d20bfa00718ff16569c83ebddb7c12704612d2751272ccec6ef0890bb7e45`.
- Both counters agreed on the temporary worker store and the historical run 5 store.
  The wrapper received shell syntax checking only. All six rows used arci plan.
  The digest list binds the study files, tests, counters and wrapper.

Live server readiness, active context, acceptance of the serialized history by the
server and model, sampling, latency, retry choices and final-state success on the
real model remain unchecked. The offline evidence cannot predict those outcomes.

## Predictions

The consultant predicts BLOCK.

The orchestrator (Claude) predicts BLOCK. The maintainer supplied no prediction.

Both were stated before any trial of this run. No live trial of any kind preceded this
registration. For runs 4 and 5 both recorded predictions were wrong.

## Conditions for reading the verdict

Publish every outcome. Interpret a statistical PASS or BLOCK for this reply comparison
only if all four checks hold and both counters agree on every figure used. If a check
fails, identify it and report the verdict without a reply-effect conclusion.

1. The registered files were committed, unchanged and pushed before the first trial.
   The wrapper passed its preflight. Check digests, versions, arm settings, model
   short id, both full digests and the logged active context of 32768 after the run.
2. For each assigned trial, require the opening and successful injected null. The
   next tool/model event after the scripted lookup finish must be a model step.
   Check the baseline audit digest against the log. Its line count and distinct call
   ids must equal baseline deliveries and be positive.
   Candidate audit lines must be zero. Check the first-exchange file against its
   logged digest. Require exactly one receipt per stored arm, task and scenario seed,
   with no extras. The first outbound chat request must contain exactly the registered
   system prompt, user task, wrong stock call, stock error, lookup call and assigned
   reply, including the exact arguments above. Require a completed assistant response
   from Ollama on that same request. Missing or mismatched evidence withholds the
   live-exposure conclusion. Keep every assignment in the gate.
3. Neither arm has a crash. In each arm, 20 times the number ending in timeout or
   budget must be at most its total trials. All such terminations stay in the gate.
4. The sealed manifest and store name match the expected experiment id. Every event
   matches the ordered events in its sealed trial, with no extra or missing events
   or trial ids. Recompute with arci gate and require “stored decision: MATCH”.

## One start and publication

Before publication, retain the consultant's BLOCK and replace the predictions
placeholder with any other attributed predictions, or remove it if there are none.
Under D-29, commit and push PREREGISTRATION-run-6.md, run-6-digests.sha256 and all
listed files before any live trial. Set RUN6_ENV to the registered environment. From
study/, check mode writes run-6-check.log and starts no trial. Real mode is
`sh run-6.sh real`. The wrapper verifies publication, file hashes, versions, model
identity and each arm's configuration. A failed guard leaves no new real marker
or real log. After all guards, it atomically claims run-6-real.started and moves the
preflight log to run-6.log. It warms the one shared model once outside the experiment,
then starts ARCI under caffeinate with one worker and fresh runs-run-6/ output.

Keep the first start, even if interrupted or ERROR. No restart, extra rounds,
replacement wording or follow-up comparison under this registration. Publish the final
registration and both replies first. After the run publish the sealed store, run log,
run-6-audit.jsonl and run-6-first-exchanges.jsonl with their digests, both counters'
output and gate recomputation.
Give verdict and reason, stopping round, per-arm and per-task passes/assignments,
openings, successful empty deliveries, handoffs, later lookup attempts with any
arguments and passes with and without a later attempt. Name any failed condition
or disagreement. For an interruption publish the available records and where execution
stopped. The maintainer approves and posts the thread reply linking the result.

The stopped counts are descriptive. They establish no superiority, absolute reliability,
effect size, per-task verdict, learning or cause of success after a retry. They do not
measure spontaneous mistakes, explain policy versus capability or test the 12B model.
Claims apply only to this model, prompt, shared opening and eight cells on this setup.
