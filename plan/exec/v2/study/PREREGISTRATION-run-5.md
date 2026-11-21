# Run 5 registration — does generic retry wording lower mean success by more than ten points?

Prepared 2026-11-21 UTC. The actual push time and commit are recorded in the result.

Publish the question, both messages, the cap and the stopping rule before the first
live trial.

## Why run 5

The design brief quotes a question from Agentic Affairs on dev.to:

> an arm with an explicit instruction that doesn't name the next call would separate
'naming the step' from 'being told to retry'. Worth a run 5?

Decision D-29 in `../DECISIONS.md` allows one registered run for a new public question
from outside the project when the existing results leave it open.

Every arm in runs 3 and 4 had the same prompt ending “Retry an empty lookup once.”
In run 3, the raw-`null` arm passed 2/16 assignments and had 15 successful injections.
The explicit arm passed 15/16. In run 4, both messages named the tool and its argument.
Only the explicit one asked for a retry. After a successful empty lookup, 31/31
explicit trials and 14/31 neutral trials made a later lookup. Across all assignments,
30/32 explicit and 14/32 neutral trials passed. Run 4 stopped at round 4 with a
statistical BLOCK for neutral.

Neither run gave a generic retry instruction at the point of failure. Run 5 asks
whether the generic message lowers mean success by more than ten percentage points
against the explicit message. Both arms run fresh. The tasks and fault were chosen
after run 2. The explicit message was retained after run 3. The descriptor lists runs
1 through 4 in `prior_runs`. There is no error guarantee across the five campaigns.

## What the model receives

Baseline, `explicit-retry-text`:

`lookup_order returned an empty result. Call lookup_order again with the same order_id.`

Candidate, `generic-retry-text`:

`The previous tool call returned an empty result. Repeat that call with the same input.`

Each message has 86 characters including spaces and punctuation, with one space between
sentences. Counting space-separated words gives 12 for the baseline and 15 for the
candidate. Both ask for a retry with the same input. The baseline names `lookup_order`
twice and `order_id` once. The candidate refers back with “previous” and “that call”,
changes “Call … again” to “Repeat” and calls the argument “input”. Both sentences change.

Both arms use `ollama:qwen3.5:4b-mlx-ctx32k`, temperature 0.7, reasoning off, run 4's
system prompt, tools and state check. The check reads the final order, including the
exact stock note. Each trial has up to 12 tool calls, 12 model steps and 120 seconds.
The grader has 20 seconds.

Both arms retry a tool timeout or runtime exception once and use `ReturnToolErrors`.
Both put the same `ReplaceEmptyLookup` middleware last. It calls the handler once. On
a successful `lookup_order` reply equal to the text `null` after trimming whitespace,
it substitutes the assigned text, preserving call id, name and status. It passes other
replies through. The tool recording retains the empty value. Only the assigned
replacement text changes. Both scripted histories retain the preceding named call and
its arguments. Live histories can diverge. A later lookup can already be queued when
the reply arrives.

## What the verdict means

The comparison is generic minus explicit across the eight equally weighted cells,
under the assumptions below. Report the tool's reason with its verdict.

- A statistical **BLOCK** supports a generic mean pass rate more than 10 percentage
  points lower. A BLOCK forced by a candidate hard violation gives no wording inference.
- **PASS** supports a generic shortfall smaller than 10 points, a tie or a lead.
  Both arms failing every case could give PASS with no errors or hard violations.
- **INCONCLUSIVE** leaves the threshold question open. **ERROR** gives no statistical
  conclusion.

Neither statistical verdict distinguishes a policy choice from a limit of the model's
capability. Neither shows that retrying caused success. The words, references and word
counts change together. This compares these two complete messages.

## Tasks, arm order and stopping rule

The tasks are desk-03, desk-06, desk-09, desk-12, desk-15, desk-18, desk-21 and desk-24.
They repeat one stock-note request with eight order ids. Each cell has the same fault,
`empty_result` on occurrence 0 of `lookup_order`. Count every assigned trial, even if
the agent never receives an empty result.

1. Each round contains eight pairs, one per cell. With `per_round` seeds, the arms in
   a pair share one scenario seed. Each starts in a fresh process with reset tool state.
   The pair runs consecutively on one worker and one server. The client supplies no
   sampling seed. In each pair the tool chooses which arm runs first from the rule
   digest, the cell and the round. The store's row order does not show execution order.
2. Use the equally weighted mean of cell pass-rate differences with alpha 1/20, margin
   1/10, stakes 1/4 and 1/2, and a boundary of 40 for each direction. Inspect the rule
   only at complete round ends. Stop at the first PASS, BLOCK or ERROR. If none has
   decided by round 30, stop INCONCLUSIVE. The cap is 240 pairs or 480 trials.
3. Keep every pair with an error in either arm, without a retry. For the PASS test it
   scores −1 and for the BLOCK test +1. The tolerance is four such pairs. A fifth
   yields ERROR at that round's end ahead of any other verdict.

The rule assumes independent pair differences across cells and rounds, a stable law
in each cell and no effect of arm order. The two outcomes within a pair may depend on
each other. ARCI does not check these assumptions.

For the mean over each round's scenario instances, the false-PASS bound is 2.5% if
generic trails by at least 10 points in every round. The false statistical BLOCK bound
is 2.5% if generic trails by at most 10 points, ties or leads in every round. At a
shortfall of exactly 10 points in every round both bounds apply. Neither is a bound
averaged over seeds or conditional on the delivery checks below.

## What the planner projects

The explicit arm is assumed to pass 90% in each cell, as in run 4's plan. For these
calculations, arms within a pair are independent, cells and rounds are independent,
rates stay fixed, and there are zero errors or hard violations. Each row uses the
stated generic rate in every cell. Probabilities and expected pairs are rounded.

| Generic rate | PASS | BLOCK | INCONCLUSIVE | Expected pairs |
|---:|---:|---:|---:|---:|
| 90% | 0.807 | 0.000 | 0.193 | 149 |
| 85% | 0.176 | 0.000 | 0.823 | 223 |
| 80% | 0.011 | 0.009 | 0.980 | 238 |
| 75% | 0.001 | 0.145 | 0.855 | 227 |
| 70% | 0.000 | 0.573 | 0.427 | 182 |
| 65% | 0.000 | 0.918 | 0.082 | 124 |
| 50% | 0.000 | 1.000 | 0.000 | 50 |

These are projections. Near the margin the design usually leaves the question open.
To reproduce them, set both model ids and temperature as above. From the suite folder
run `arci plan arci.yaml --baseline-rate .90 --candidate-rate C --agreement A` for each
row, substituting the generic rate as a fraction for C and 0.90 × C + 0.10 × (1 − C)
for A. This calculation calls no model.

## Software, identity and files

Use run 4's environment with Python 3.13.12, ARCI 2.4.1, langchain 1.4.10,
langchain-core 1.7.7, langgraph 1.2.20, langgraph-prebuilt 1.1.1, langchain-ollama
1.1.0, ollama Python client 0.6.3 and pydantic 2.14.3. The wrapper checks these
versions at preflight. Require Ollama server 0.32.14 and model short id `c01efed5a364`.
Require the server's full digest and the local model manifest's SHA-256 both to match
`c01efed5a36459ab6ffffa0b158636a014d8b30b4d5493167cba9916ed558430`.
Check that the model has an active context of 32768 after the run.

The expected store name and experiment id join the following suite id and digest with
one `@` and no spaces. Both come from the descriptor compiled for the planner.

`order-desk-qwen3.5-4b-empty-lookup-generic-retry`

`47eb8652f4366cfb633e04cbc55a03439accfefecc470c3ffab64a53f3dcdaed`

`run-5-digests.sha256` lists the suite files in `order-desk-generic-retry/`, its two
offline tests, the blind test, the definitions and both scripts in `counts-run-5/`,
and `run-5.sh`. The wrapper checks the registration, digest list and listed files
against HEAD and verifies that the published branch contains HEAD. It checks every
digest and logs both commits. The digests bind the listed study files.

## What was looked at before writing

The builder reports reading the reader's question, D-29, the consultant's run 5 design,
run 4's registration and result, its code, tests, wrapper, digests, count definitions,
smoke descriptor and R10 scripted capture. Run 4's dated correction reports 16 pairs
with each arm first.
The original statement that explicit always ran first was wrong. The store and audit
from run 4 also served as a known case for the two counters.

The orchestrator reports no live run 5 trial before this registration. Run 5 has no
smoke descriptor or smoke mode. Run 4 exercised this code path live. The builder
reports only offline checks for run 5:

- Seven copied files matched run 4 byte for byte. The middleware, scripted adapter and
  blind tests checked the two texts, unchanged settings, pass-through, metadata, audit
  and the original recorded empty value. A scripted retry is part of the test.
- R11 captured 400 requests per arm using the actual adapter and client with a fake
  transport. All 80 first-request pairs matched byte for byte. All 320 later pairs
  matched after replacing only the first lookup reply. Neither arm sent a tool reply
  containing the literal text `null`. Zero requests left the process. The capture and
  checks are in `../reviews/R11-run5-realpath-proof/`.
- Both count scripts produced byte-identical output on run 4's store with its audit.
  The wrapper passed shell syntax checking. All seven planner rows used run 5's
  descriptor and registered model settings.

Server readiness, the loaded model and context, and delivery to a live model on run 5
remain unchecked. The scripted responses give no evidence of live retries or passes.

## Predictions

The consultant (Astra) recorded INCONCLUSIVE in the design. This registration records
INCONCLUSIVE for the orchestrator (Claude) and no prediction from the maintainer.

Both recorded predictions for run 4 were INCONCLUSIVE and were wrong.

## When the verdict answers the wording question

Publish any verdict and its reason. Only a statistical PASS or statistical BLOCK answers
the threshold question under the stated assumptions. Check each of the four conditions
below. All four must hold, and both counters must agree on every figure used in a
check. If evidence is missing or conflicts, name the failed check and report
“not an answer about the two wordings”.

1. The start checks in `run-5.log` passed. The registration and listed files were
   committed, unchanged and pushed. Every digest, software version and setting
   matched. Confirm the logged server version, model short id, both full digests and
   the model's active context of 32768 after the run.
2. The logged SHA-256 matches `run-5-audit.jsonl`. The number of audit lines equals
   the number of distinct call ids overall. Each arm has at least one replacement,
   and its line count equals its own `empty_result_delivered_ok`. These lines record
   middleware replacements. They cannot identify a trial or prove live model receipt.
3. At the stopping round neither arm has a crash. In each arm, 20 times the number
   ending in timeout or budget is at most its total trial count, using
   `by_termination`. Crashes, timeouts and budget stops count as failures and stay in
   the gate.
4. The store manifest has the expected experiment id. On that store `arci gate`
   recomputes the decision and reports a match. For every trial, `events.jsonl` matches
   the ordered events in its sealed trial record, with no extra or missing events or
   trial ids. An interruption or ERROR supplies no statistical conclusion.

## One start

After publication, set `RUN5_ENV` to the registered environment and run
`sh run-5.sh real` from the study folder. One start means one time past the guards.
The wrapper requires fresh output, log and audit paths. It checks the published files,
hashes, server, model and settings of both arms. A failed guard leaves no new marker or
`run-5.log`, so a corrected start is possible. After all guards pass, the wrapper
claims the permanent `run-5-real.started` marker atomically, moves the preflight log
to `run-5.log` and warms up the model once outside the experiment. It runs ARCI with
one worker under `caffeinate` and writes `runs-run-5/`. Check mode starts no trial and
refuses an existing real marker or real log. It writes `run-5-check.log`.

Keep the first outcome, including an interruption, ERROR or INCONCLUSIVE. Stop if a
delivery check fails. No replacement start, extra rounds or wording change. A later
study would need its own registration listing this run.

## What will be published

If interrupted before a verdict, publish the interruption and the available records.
For a completed run, publish the sealed store, log, audit and its digest, both counters'
output and the gate recomputation. Give the verdict and reason, stopping round, passes
out of trials per arm, audited replacements, the per-task table and fault accounting
by arm. Publish all counts
in `counts-run-5/SPEC.md`. After any marked empty lookup, successful or failed, count
trials with and without a later lookup attempt and passes in each group. A later attempt
counts even if it fails. Explain any discrepancy between counters. ARCI alone decides.

Prepare a reply in the reader's thread with both texts and the available results.
For a completed run, give the verdict, reason, arm counts, stopping round and any
failed check. Include or link the per-task table and full counts. For an interruption
before a verdict, report the interruption and link the available records.
The maintainer approves the exact reply and posts it.

## Limits on claims

Only a statistical PASS or statistical BLOCK answers the threshold question for these
eight cells on this model, prompt and set-up, under the stated assumptions and with all
four checks met. It gives no effect-size estimate, per-task verdict or result for other
models, wordings or conditions. Report stopped counts without fixed-sample intervals.
A PASS does not establish absolute reliability. An INCONCLUSIVE result does not show a
near miss or no effect. Do not infer a mechanism from the retry counts or a wording
effect from differences between campaigns. Only the two fresh arms enter the decision.
