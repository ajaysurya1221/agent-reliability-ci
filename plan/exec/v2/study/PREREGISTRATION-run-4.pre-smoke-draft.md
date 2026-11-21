# Pre-registration, run 4: two wordings for an empty lookup

Draft. D-28 in `../DECISIONS.md` calls for the registration to be committed and pushed
before any trial. Registration push date: [[DATE_PUSHED]]. The separate smoke run is
disclosed below. The three earlier registrations and results are in this study folder.

## Read this first: the explicit message is the baseline

The test compares the neutral message (candidate) with run 3's explicit message
(baseline). Both arms run fresh. Read the tool's verdict over the 8 cells as follows.

- **BLOCK** ("regression established") means the neutral arm passes less often than the
  explicit arm by more than 10 percentage points of mean pass rate on these 8 cells.
- **PASS** ("non-inferiority established") means the neutral arm is within 10 points of
  the explicit arm on the downside. Any shortfall is less than 10 points. This includes
  the neutral arm doing as well as or better than the explicit arm.
- **INCONCLUSIVE** means the test decided neither direction within the registered budget.
- **ERROR** means the error tolerance was exceeded, a record is invalid or another gate
  check failed. It gives no statistical conclusion.

Only a statistical BLOCK supports the wording claim or carries the bound below. A hard
violation by the candidate can also force a BLOCK. Publish the tool's reason line.

## Why a fourth run

After run 3, a reader on dev.to asked whether a control message would show if naming the
next step was what helped. Run 3's own "What will not be claimed" section raised the
same question. It compared one explicit message with the text `null`. Run 4 gives both
arms a message at the same point. The reader's question is in `../launch/devto-reply-3.md`.

We chose the 8 tasks and the fault after seeing run 2. We chose to keep the explicit
text after seeing run 3, where the arm with it passed 15 of 16 trials and run 2's
set-up passed 2 of 16. The question itself was chosen after those results were known.
This is a fourth campaign on related data. We keep the four results separate and claim
no error guarantee across the four. The descriptor lists runs 1, 2 and 3 in `prior_runs`.

## Question

On the 8 stock-note tasks, with the first `lookup_order` call set to return the injected
empty result, does the agent on `qwen3.5:4b-mlx-ctx32k` pass less often, by more than
10 points of mean pass rate over these 8 cells, when that result reaches the model as
the neutral message than when it reaches the model as the explicit message?

## The one difference between the arms

Both arms use `ollama:qwen3.5:4b-mlx-ctx32k`, temperature 0.7 and reasoning off. Both
use run 2's system prompt. It ends "Retry an empty lookup once." The tools and the check
are the same. The check grades the final order state, including the exact stock note.
Each trial has up to 12 tool calls, 12 model steps and 120 seconds. The grader has
20 seconds.

Both arms retry a timeout or a runtime error once. Both use `ReturnToolErrors` and put
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
- Errored-pair tolerance 4, as in run 3. Astra proposed zero. The orchestrator kept 4
  so that one transient local-server error does not void the only start. A pair with an
  error in either arm counts against each test. Keep it without a retry. More than 4
  errored pairs gives ERROR.
- With `per_round` seeds, ARCI derives one scenario seed for each cell in each round. Both
  arms share it and run next to each other on one worker. Each trial starts in a fresh
  process with reset tool state. Model sampling is unseeded. Both arms use one server.
- The suite id is `order-desk-qwen3.5-4b-empty-lookup-control`. The expected experiment
  id is `[[EXPERIMENT_ID]]`. The store folder must have that experiment id as its name.

The suite rule assumes that pair differences are jointly independent across cells and
rounds and that each cell has the same law each round, including no effect of which arm
runs first. The two outcomes within a pair may depend on each other.

Under those assumptions, each directional error is at most 2.5% when its null holds in
every round for the mean over that round's scenario instances. The false-PASS bound
applies when the neutral arm trails by at least 10 points in every round. The false-BLOCK
bound applies when it trails by at most 10 points, ties or leads in every round.
ARCI does not check these assumptions. There is no guarantee averaged over seeds.

## Planner projections (a model, not a measurement)

[[PLANNER_PROJECTIONS]]

These projections describe the assumed pass rates and pairing. They do not use run 4
trial outcomes.

## Software

ARCI 2.4.1 from PyPI. Run 3 used 2.4.0. Between those tags, the changes under `src/arci`
were the version in `__init__.py`, `logs/kept.py`, `mcp_boundary.py`,
`mcp_toolset_server.py` and six added lines in the command-agent path of `runner.py`.
None changes how a Python or LangChain trial runs or how the suite decides it.

Both arms use langchain 1.4.10, langchain-core 1.7.7, langgraph 1.2.20, langgraph-prebuilt
1.1.1, langchain-ollama 1.1.0, ollama client 0.6.3, pydantic 2.14.3, Python 3.13.12.
Ollama server 0.32.14. Model `qwen3.5:4b-mlx-ctx32k`, id `c01efed5a364`, 32k context.
Apple M5 Pro, 24 GB, one worker.

## Files

`run-4-digests.sha256` must list the SHA-256 digests of the files in
`order-desk-control-message/` used for the run, the offline and blind tests, the count
definitions and both scripts in `counts-run-4/`, and the wrapper `run-4.sh`. The wrapper
checks the digests before the first registered trial and logs the checks in `run-4.log`.
The published commit and digests bind the Python code. The store does not contain it.

## What was looked at before writing this

- Run 2's task and condition choice, run 3's registration and result, the reader's
  question and Astra's design.
- [[OFFLINE_TEST_COUNTS]]. Include the offline check that a scripted model receives
  the explicit text in the baseline arm and the neutral text in the candidate arm
  after the first empty lookup.
- [[SMOKE_RUN_FACTS]]. Record when the smoke ran relative to the push, its separate
  suite id, rule, counts and audit. Disclose any changes to the files or wrapper before
  the registered start. Smoke trials are excluded from run 4's evidence.

## Prediction

- The consultant (Astra): INCONCLUSIVE.
- The orchestrator (Claude): INCONCLUSIVE.
- The maintainer: none supplied before registration.

## What will be published

Publish the verdict whatever it is, its reason, trials passed out of trials run in each
arm, the stopping round and the per-task table. Give the fault accounting by arm,
including how often the first lookup returned the injected empty result. Publish the
counts from `counts-run-4/SPEC.md`, including how often the agent read the order again
after the injected lookup and how often it did not. Compare the outputs of `count_a.py`
and `count_b.py`. If they differ, publish both and explain the difference. The counts
decide nothing.

Prepare a reply in the same dev.to thread. Give both texts, the verdict and reason,
passes out of trials per arm and the stopping round. Include the per-task table,
fault accounting and counts in the reply or link directly to them. State any failed
check. The maintainer approves the exact reply and posts it.

## Conditions for reading the verdict as a statement about the two wordings

Publish the verdict in every case. Read it as an answer about the two wordings only if
all four checks hold. If one fails, publish the verdict and the failed check together
and report "not an answer about the two wordings".

1. The start checks in `run-4.log` passed. The registration and registered files were
   committed, unchanged and published. Every digest, the installed versions, the model
   id and the registered settings matched.
2. Across the whole audit file there are as many lines as distinct call ids. Count lines
   by arm. Each arm's count must be greater than zero and equal that arm's
   `empty_result_delivered_ok`. The audit records replacements by the middleware.
   Its lines cannot be tied to single trials. Agreement supports delivery but cannot
   establish what reached the model on a particular call.
3. At the stopping round, check `by_termination`. Neither arm has a `crash`. In each
   arm, 20 times the number of trials ending in `timeout` or `budget` is at most that
   arm's total trials. The tool scores all three endings as failures. All trials stay
   in the gate.
4. The store's manifest carries the expected experiment id. On that store, `arci gate`
   recomputes the decision from the stored trials and reports a match with the stored
   decision. An interrupted run or ERROR supplies no statistical conclusion.

These checks cannot establish independence. The 2.5% bound does not apply conditional
on the checks passing.

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
