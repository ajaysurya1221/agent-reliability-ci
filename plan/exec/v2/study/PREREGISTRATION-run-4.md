# Pre-registration, run 4: two wordings for an empty lookup

Sixteen live smoke trials ran before this registration was complete or pushed. That was
contrary to D-28 in `../DECISIONS.md`, which says to push it "before any trial".
The orchestrator saw 7 of 8 explicit trials pass and 4 of 8 neutral trials pass.
Publish this registration before the first main-study trial. Record the actual push time
and commit in the result. The three earlier registrations and results are in this folder.

## Read this first: the explicit message is the baseline

The test compares the neutral message (candidate) with run 3's explicit message
(baseline). Both arms run fresh. Read the tool's verdict over the 8 cells as follows.

- For neutral minus explicit, statistical **BLOCK** ("regression established") supports
  a mean pass-rate difference below −0.10. A **BLOCK** forced by a candidate hard
  violation supplies no inference about wording. Publish the tool's reason line.
- **PASS** ("non-inferiority established") supports a difference above −0.10. Any
  shortfall is less than 10 percentage points. A tie or a neutral lead also qualifies.
- **INCONCLUSIVE** means the test decided neither direction within the registered budget.
- **ERROR** means the error tolerance was exceeded, a record is invalid or another gate
  check failed. It gives no statistical conclusion.

## Why a fourth run

After run 3, a reader on dev.to asked whether a control message would show if naming the
next step was what helped. Run 3's own "What will not be claimed" section raised the
same question. It compared one explicit message with the text `null`. Run 4 gives both
arms a message at the same point. The reader's question is in `../launch/devto-reply-3.md`.

The orchestrator chose the 8 tasks and the fault after run 2 and kept the explicit text
after run 3. In run 3 the arm with that text passed 15 of 16 trials and the arm with
run 2's set-up passed 2 of 16. Those results informed the question. The four campaigns
have separate results and no shared error guarantee. The descriptor lists runs 1, 2 and 3
in `prior_runs`.

## Question

Across all assigned trials, does using neutral wording on eligible lookups reduce mean
success by more than ten percentage points versus explicit wording on these 8 stock-note
tasks with `qwen3.5:4b-mlx-ctx32k`?

## The one difference between the arms

Both arms use `ollama:qwen3.5:4b-mlx-ctx32k`, temperature 0.7 and reasoning off. Both
use run 2's system prompt. It ends "Retry an empty lookup once." The tools and the check
are the same. The check grades the final order state, including the exact stock note.
Each trial has up to 12 tool calls, 12 model steps and 120 seconds. The grader has
20 seconds.

Both arms retry eligible tool exceptions once. Both use `ReturnToolErrors` and put
the same middleware class, `ReplaceEmptyLookup`, last. It calls the handler once. For a
successful `lookup_order` tool message whose content is `null` after trimming whitespace,
it replaces the content and keeps the call id, name and status. It makes no retry.
All other tool results pass through. Only the replacement text differs for the model.

The baseline arm gets run 3's explicit text.

> `lookup_order returned an empty result.
> Call lookup_order again with the same order_id.`

The candidate arm gets the neutral text.

> `lookup_order returned an empty result.
> This lookup_order result is for the supplied order_id.`

There is one space between sentences. Counting spaces and punctuation, the explicit text
has 86 characters and 12 words. The neutral text has 93 characters and 13 words. A word
is one space-separated item. The first sentence is identical. The explicit text says
"Call", "again" and "the same order_id". The neutral text repeats "result" and says what
the result is for ("the supplied order_id"). Both the words and the length change.

## Grid and rule

- The tasks are `desk-03`, `desk-06`, `desk-09`, `desk-12`, `desk-15`, `desk-18`, `desk-21`
  and `desk-24`. One stock-note request with eight order ids. The fault is `empty_result`
  on `lookup_order`, occurrence 0. Every round has one pair per cell, 8 pairs, 16 trials.
  All trials count, including those in which the agent never gets the empty result.
- The test uses the equally weighted mean of the 8 cell differences in pass rate,
  neutral minus explicit. Alpha 1/20, margin 1/10, stakes {1/4, 1/2}. At most 30 rounds
  (240 pairs, 480 trials). Look only at complete round ends. Stop at the first PASS,
  BLOCK or ERROR. If none occurs by round 30, stop INCONCLUSIVE.
- Errored-pair tolerance 4, as in run 3. The consultant proposed zero and accepted four.
  The orchestrator kept four so one transient server error would not void the only start.
  A pair with an ERROR in either arm stays in the run without a retry. It scores −1 for
  the PASS test and +1 for the BLOCK test. A fifth errored pair gives ERROR at the end
  of that complete round, ahead of any other verdict.
- With `per_round` seeds, ARCI derives one scenario seed for each cell in each round. Both
  arms share it and run next to each other on one worker. Each trial starts in a fresh
  process with reset tool state. Model sampling is unseeded. Both arms use one server.
- The suite id is `order-desk-qwen3.5-4b-empty-lookup-control`. The expected experiment
  id below is also the required store folder name.

`order-desk-qwen3.5-4b-empty-lookup-control@2268db685b3425006a9d019ecf2c65a96d47dba71a97c7924df07d13f947b0e1`

The suite rule assumes that pair differences are jointly independent across cells and
rounds and that each cell has the same law each round, including no effect of which arm
runs first. The two outcomes within a pair may depend on each other.

Under those assumptions, each directional error is at most 2.5% when its null holds in
every round for the mean over that round's scenario instances. The false-PASS bound
applies when the neutral arm trails by at least 10 points in every round. The false-BLOCK
bound covers only a statistical BLOCK and applies when the neutral arm trails by at most
10 points, ties or leads in every round. At exactly −0.10 in every round both nulls hold.
ARCI does not check these assumptions. There is no guarantee averaged over seeds.

## Planner projections (a model, not a measurement)

`arci plan` assumes independent cells and rounds, independent arms within a pair, stable
pass rates, zero errors and zero hard violations for these projections. The explicit
pass rate is 90% in every cell. Each row gives the assumed neutral rate in every cell.
Probabilities and expected pairs are rounded.

| Neutral arm | PASS | BLOCK | INCONCLUSIVE | Expected pairs |
|---|---|---|---|---|
| 90% | 0.807 | 0.000 | 0.193 | 149 |
| 85% | 0.176 | 0.000 | 0.823 | 223 |
| 80% | 0.011 | 0.009 | 0.980 | 238 |
| 75% | 0.001 | 0.145 | 0.855 | 227 |
| 70% | 0.000 | 0.573 | 0.427 | 182 |
| 65% | 0.000 | 0.918 | 0.082 | 124 |
| 50% | 0.000 | 1.000 | 0.000 | 50 |

90% for the explicit arm is an assumption taken from one count (15 of 16 in run 3). Other
assumptions give other figures.

These projections describe the assumed pass rates and pairing. They do not use run 4
trial outcomes.

## Software

The smoke log shows installed ARCI 2.4.1 (run 3 used 2.4.0), langchain 1.4.10,
langchain-core 1.7.7, langgraph 1.2.20, langgraph-prebuilt 1.1.1, langchain-ollama
1.1.0, ollama Python client 0.6.3, pydantic 2.14.3 and Python 3.13.12. It reports
Ollama server 0.32.14 and model `qwen3.5:4b-mlx-ctx32k`, id `c01efed5a364`, with an
active context of 32768 after the smoke. The registered model manifest SHA-256 is
`c01efed5a36459ab6ffffa0b158636a014d8b30b4d5493167cba9916ed558430`.
The orchestrator reports that ARCI came from PyPI and the machine was an Apple M5 Pro
with 24 GB. The run does not verify the package origin or machine details.

## Files

`run-4-digests.sha256` lists the SHA-256 digests of the files in
`order-desk-control-message/` used for the run, the offline and blind tests, the count
definitions and both scripts in `counts-run-4/`, and the wrapper `run-4.sh`. The wrapper
checks the digests before the first registered trial and logs the checks in `run-4.log`.
The published commit and digests bind the Python code. The store does not contain it.

## What was looked at before writing this

- Run 2's task and condition choice, run 3's registration and result, the reader's
  question and Astra's design.
- The build and blind-test reports record 12 and 17 passes. The orchestrator reports
  obtaining the same counts on 21 November. The offline
  adapter test showed that the scripted model received the explicit text in the baseline
  arm and the neutral text in the candidate arm after the first empty lookup.
- R10 captured scripted client requests only (`../reviews/R10-run4-realpath-proof/`).
  A mock transport recorded 800 request bodies, 400 per arm. Over 8 tasks and 10 rounds,
  80 request pairs matched exactly. In the other 320 pairs only the first lookup reply
  differed. Neither arm sent literal `null` as that reply. No request left the process.
- One coding agent wrote the code from a brief. Two others wrote the blind tests and
  the mock transport check. The seven files copied from run 3 match the originals.

## Smoke run and changes before publication

The orchestrator decided to proceed before the smoke and pushed D-28 at 11:03 UTC on
21 Nov 2026. The 16 live smoke trials checked the set-up from 11:13 to 11:14 UTC that
day, before this registration was complete or pushed. That was contrary to D-28's
"before any trial" wording. The orchestrator saw explicit 7 of 8 and neutral 4 of 8
before completing the registration. The smoke verdict was INCONCLUSIVE, with zero
errored pairs and 8 audit lines per arm.

The smoke had its own descriptor, seed schedule and suite id,
`order-desk-qwen3.5-4b-empty-lookup-control-smoke-not-evidence`. Its rule used alpha
1/2, margin 1/2, one round and tolerance zero. No smoke trial enters a registered count
or decision. The smoke log records the agent path and both texts without source hashes.
The orchestrator includes `run-4-smoke.log`, `runs-run-4-smoke/` and
`run-4-smoke-audit.jsonl` in the registration commit, along with
`PREREGISTRATION-run-4.pre-smoke-draft.md` in this folder. That draft was written before
the smoke run and retains five placeholders in double square brackets. The placeholder
check applies only to the completed registration.

The design, build, blind-test and registration briefs predate the smoke. The orchestrator
reports that only the registration and wrapper were revised among existing study files.
The digest list and R10 proof were added afterward. The briefs
and draft record both texts, alpha 1/20, margin 1/10, stakes 1/4 and 1/2, the 30-round
cap, tolerance four, the delivery checks and both INCONCLUSIVE predictions. The smoke
counts changed neither the design nor the decision to proceed. They moved the
orchestrator's expectation toward BLOCK.

The wrapper clears `PYTHONOPTIMIZE` and refuses optimized Python. It logs the first
client version line for information and requires the local server to report version
0.32.14. It checks the listed short id and requires both the named model's full server
digest and the SHA-256 of its readable local manifest to match the registered digest.
It logs the post-run context. Check mode also refuses an existing `run-4-real.started`
or `run-4.log`. In check and real modes, Git status on the registered files must
succeed with empty output. Smoke mode has been used and its permanent
`run-4-smoke.started` marker exists.

## Prediction

- The consultant (Astra): INCONCLUSIVE.
- The orchestrator (Claude): INCONCLUSIVE.
- The maintainer supplied no prediction before registration.

Both predictions stand as recorded before the smoke.

## What will be published

Publish the verdict whatever it is, its reason, trials passed out of trials run in each
arm, audited replacements per arm, the stopping round and the per-task table. Give the
fault accounting by arm. Publish the counts from `counts-run-4/SPEC.md`. After any
lookup marked as an empty-result injection, including a failed one, report trials with
and without a later lookup attempt. A later lookup counts even if it fails. Compare
`count_a.py` and `count_b.py`. Publish and explain any difference. ARCI alone decides
the verdict.

Prepare a reply in the same dev.to thread. Give both texts, the verdict and reason,
passes out of trials per arm and the stopping round. Include the per-task table,
fault accounting and counts in the reply or link directly to them. State any failed
check. The maintainer approves the exact reply and posts it.

## Conditions for reading the verdict as a statement about the two wordings

Publish the verdict in every case. Read it as an answer about the two wordings only if
all four checks hold. Both count scripts must agree on every figure used in a condition.
If a check fails or evidence is missing or conflicts, publish the verdict and reason,
identify the failed check and report "not an answer about the two wordings".

1. The start checks in `run-4.log` passed. The registration and registered files were
   committed, unchanged and published. Every file digest, installed version and setting
   matched. Check that the log shows server 0.32.14, the registered short id and full
   model manifest digest, and an active context of 32768 for that model after the run.
2. The SHA-256 printed in the log equals the SHA-256 of the audit file. Across the
   file there are as many lines as distinct call ids. At least one replacement is
   required in each arm, so a single replacement overall cannot suffice. Each arm's
   line count must equal its own `empty_result_delivered_ok`. The audit records middleware
   replacements. Its lines cannot identify a trial or prove what reached a model call.
3. At the stopping round, check `by_termination`. Neither arm has a `crash`. In each
   arm, 20 times the number of trials ending in `timeout` or `budget` is at most that
   arm's total trials. The tool scores all three endings as failures. All trials stay
   in the gate.
4. The store's manifest carries the expected experiment id. On that store, `arci gate`
   recomputes the decision from the stored trials and reports a match with the stored
   decision. For each trial, the events in `events.jsonl` must match those in its sealed
   trial record, in order, with no extra or missing events or trial ids. An interrupted
   run or ERROR supplies no statistical conclusion.

These checks cannot establish independence. The 2.5% bound does not apply conditional
on the checks passing. If both arms failed every trial with no errors or hard violations,
the statistical rule would give PASS. Report passes out of trials per arm. A PASS does
not mean "both work".

## One start

Start once, in a fresh output folder. If set-up takes more than two agent-hours, D-28
calls for dropping the run. Publish an interruption or ERROR as the outcome of this
registration. If a delivery check fails, report it and stop there. Any later run needs
a new registration that lists this one.

If the verdict is INCONCLUSIVE, keep it. No added rounds, second start or new wording.
Do not read the observed difference as an effect, as "nearly" or as "no effect".

## What will not be claimed, whatever the verdict

- No claim about why one wording works, about reasoning, or about naming the next step
  in general. The run compares these two wordings.
- No claim about the 12B model, other tasks, other conditions or the full suite.
- No estimate of the size of an effect. The verdict answers a threshold question.
  Report stopped counts without fixed-sample confidence intervals.
- No reading of a difference between run 4's counts and run 3's counts as an effect.
  Only the two fresh arms enter the decision.

## Command

Run the wrapper from `plan/exec/v2/study/`, with `RUN4_ENV` set to the registered
Python environment.

```sh
sh run-4.sh real
```

The wrapper takes a permanent one-start marker and checks the output and audit paths.
It enters `order-desk-control-message/`, sets both model ids and temperature, turns off
tracing and sets the audit path. It checks the published files, digests, software,
model id, prompts and middleware in both arms. It makes one warm-up call outside the
experiment and stops if that call fails. It runs the following command under
`caffeinate` with `RUN4_ENV`'s Python.

```sh
python -m arci run arci.yaml --workers 1 --out ../runs-run-4
```
