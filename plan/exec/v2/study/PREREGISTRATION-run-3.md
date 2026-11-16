# Pre-registration, run 3: a message at the empty lookup, one model in both arms

Written and pushed on 2026-11-16 before any run 3 trial. Run 1: `PREREGISTRATION.md` and
`RESULT.md`. Run 2: `PREREGISTRATION-run-2.md` and `RESULT-run-2.md`. The plan the
maintainer approved: `PLAN-run-3.md`.

## Read this first: the roles are swapped

The test has no verdict for "better". So in this run the arm WITH the change is the
baseline, and run 2's set-up is the candidate. The tool's words then mean:

- **BLOCK** (the tool prints "regression established"): run 2's set-up passes less often
  than the set-up with the message, by more than 10 points of mean pass rate over the 8
  cells. In plain words: the message is worth more than 10 points on these 8 cells.
- **PASS** ("non-inferiority established"): the message is worth less than 10 points on
  these 8 cells. That includes worth nothing, and harm.
- **INCONCLUSIVE**: not decided within the registered budget.
- **ERROR**: the error tolerance was exceeded, a record is invalid or another check of
  the gate failed; no statistical conclusion.

The reading of BLOCK as an improvement, and the 2.5% bound below, apply to a statistical
BLOCK only, not to a BLOCK forced by a hard violation in the candidate arm. The published
result includes the tool's reason line.

## Why a third run

Two readers of the blog post asked for one. On dev.to, "Agentic Affairs" asked for a
variant in which the code retries an empty lookup. On Hashnode, "Halfcycle" asked whether a
message that names the next step, at the point of failure, closes the gap. Run 2 had one
set-up and cannot answer either.

The code-retry variant is not run. With the retry in code the model is simply handed a
working lookup, so the outcome is nearly fixed, and it could not say anything about
capability. How a code retry behaves is shown by a scripted test with no model
(`order-desk-empty-message/tests/test_code_retry_demo.py`). This choice followed the advice
of a consulted second model (`../reviews/R4-run3-design-astra.md`).

This is a third campaign on related data, chosen after seeing runs 1 and 2. The
directional guarantee applies to this registered experiment under its assumptions; no
error guarantee across the three campaigns is claimed. The three results are not pooled
and none replaces another.

## Question

On the 8 stock-note tasks, with the first `lookup_order` call returning the injected empty
result: does the agent built on `qwen3.5:4b-mlx` pass more often, by more than 10 points
of mean pass rate over these 8 cells, when the empty result reaches the model as one fixed
message than when it reaches it as the text `null`, as in run 2?

## The one difference between the arms

Both arms: the same model (`ollama:qwen3.5:4b-mlx-ctx32k`), temperature 0.7, reasoning off,
the system prompt of run 2 (it ends "Retry an empty lookup once."), the tools, the check,
the retry of timeouts and runtime errors (once), `ReturnToolErrors`, and the budgets (12
tool calls, 12 model steps, 120 s).

Baseline arm only: a middleware, `ExplainEmptyLookup`, placed last. When a `lookup_order`
result is a successful tool message whose content is the text `null`, it replaces the
content with:

> lookup_order returned an empty result. Call lookup_order again with the same order_id.

It makes no further call and no retry. With this model client the model is sent the role
and the content of a tool message and nothing else, so the difference between the arms is
the content of that one message: this text against `null`.

What this compares: the instruction "Retry an empty lookup once." in the system prompt
alone (candidate arm), against the same prompt plus this message at the point of failure
(baseline arm). One wording is tested.

## Grid and rule

- Tasks: `desk-03`, `06`, `09`, `12`, `15`, `18`, `21`, `24` (the 8 stock-note tasks: one
  task sentence with eight order ids). Condition: `empty_result` on `lookup_order`,
  occurrence 0. 8 cells a round, 16 trials a round.
- Rule: alpha 1/20, margin delta 1/10, stakes {1/4, 1/2}, at most 40 rounds (320 pairs,
  640 trials), errored-pair tolerance 4, `per_round` seeds derived by the tool. The run
  stops at the first round end that gives PASS, BLOCK or ERROR.
- Under ARCI's stated assumptions (independent cells and rounds with the same law each
  round, including no effect of which arm runs first; and, with `per_round` seeds, the
  relevant null holding in every round's scenario instances), each directional error is at
  most 2.5%. ARCI does not check these assumptions, and there is no guarantee averaged over
  seeds. Both arms of a pair get the same scenario seed; the model's own sampling is not
  seeded. Both arms use one model on one local server.
- The tool's default cap for 8 cells is 50 rounds. It is lowered to 40 to bound the time.
- Expected experiment id:
  `order-desk-qwen3.5-4b-empty-lookup-text@4413b7e2f81abc51d3576fce3d0de4974f5c25c820af06c62a5e0d0f6e969504`.
  The store folder must carry this name.

Chosen from run 2's results, and said here so that nobody reads it otherwise: the 8 tasks
and the one condition. In run 2 the candidate passed 7 of 40 on these cells, and 32 of its
34 failures under the empty result were on these tasks. The verdict is about these 8 cells
only. "10 points" is the same number as in runs 1 and 2 on a different grid; it is not the
same margin.

## Planner projections (a model, not a measurement)

`arci plan` on this descriptor, with the arms independent within a pair and every cell
passing at 7/40 without the message. Pass rate with the message, then the projected end:
50%: BLOCK 0.9997. 40%: BLOCK 0.80, INCONCLUSIVE 0.20. 38%: BLOCK 0.63. 30%: INCONCLUSIVE
0.95. No effect: PASS 0.73, INCONCLUSIVE 0.27. Other assumptions give other figures; 7/40
is one count from 40 trials.

## Software

ARCI 2.4.0 from PyPI (run 2 used 2.0.0; the files on the run path are unchanged between
the two). langchain 1.4.10, langchain-core 1.7.7, langgraph 1.2.20, langgraph-prebuilt
1.1.1, langchain-ollama 1.1.0, ollama (client) 0.6.3, pydantic 2.14.3, Python 3.13.12.
Ollama server 0.32.14. Model `qwen3.5:4b-mlx-ctx32k`, id c01efed5a364, 32k context. Apple
M5 Pro 24 GB, one worker. With this environment `arci report` on run 2's published store
prints "VERDICT: INCONCLUSIVE (exit 2); stored decision: match".

## Files

`run-3-digests.sha256` lists the SHA-256 of every registered file: the 8 files of
`order-desk-empty-message/`, its 4 test files, the blind test, the two count scripts and
their definitions, and the wrapper `run-3.sh`. The wrapper checks every digest before the
first trial and writes the result into `run-3.log`. Nothing of the Python code is sealed
into the store; the digests and this commit are what bind the code.

Carried over unchanged and not used with a real model: `offline_model.py`. It cannot run
the baseline arm (it does not understand the message), so the folder's offline quickstart
mode is not a check of this run. The offline proof is `tests/test_end_to_end.py`, which has
its own scripted model.

## What was looked at before writing this

- Run 2's store, counted three times.
- Offline tests of the middleware (9), blind tests written from the interface by a second
  agent (17), and an end-to-end test through ARCI's adapter with a scripted model (16
  offline trials: the baseline arm received the message, the candidate arm `null`).
- A reviewer's check through the real client path with a fake HTTP transport and no model:
  800 request bodies; the only difference between the arms was the content of the tool
  message after the first lookup (`../reviews/R5-run3-build-review-workflow.json`,
  scripts in `../reviews/R5-realpath-proof/`).
- A smoke run with the real model: 16 trials under the suite id
  `order-desk-qwen3.5-4b-empty-lookup-text-smoke-not-evidence`, with another rule (alpha
  1/2, delta 1/2, one round), because the tool refuses fewer than 10 rounds on 8 cells with
  the registered rule. **Not evidence.** Arm with the message: 6 of 8 passed. Run 2's
  set-up: 3 of 8. All 16 trials completed; no errored pair; 8 audit lines for 8 deliveries;
  first trial 4.4 s, longest 6.2 s; 65 s in all. The registered files are the files the
  smoke run used. Nothing was changed after it.

## Prediction

No maintainer prediction was supplied before registration. The maintainer was asked for
one word (BLOCK, PASS or INCONCLUSIVE) and had not answered when this was committed.

## What will be published

The verdict, whatever it is. Per arm: trials passed out of trials run, the stopping round,
and the per-task table. Fault accounting. The counts defined in `counts-run-3/SPEC.md`,
computed by `count_a.py` and `count_b.py`, which two agents wrote separately; both gave the
same output on run 2's store and on the smoke store. If they disagree on run 3's store,
both outputs are published and the difference explained. The counts decide nothing.

## Conditions for reading the verdict as a statement about the message (fixed now)

The verdict is published in every case. It is read as a statement about the message only
if all of these hold. If one fails, the verdict and the failure are published together and
the result is reported as "not an answer about the message".

1. The wrapper's checks at the start passed (`run-3.log`): the registration committed,
   unchanged and published; every digest; the installed versions; the model id.
2. Delivery: the audit file has as many lines as distinct call ids, that number is greater
   than zero, and it equals the baseline arm's `empty_result_delivered_ok`. The audit
   records replacements made by the middleware, not what the model received; it is a
   count, its lines cannot be tied to single trials, and agreement is supporting evidence
   only.
3. At the stopping round, using `by_termination`: no trial in either arm has the
   termination `crash`, and in each arm 20 x (trials with termination `timeout` + trials
   with termination `budget`) is at most the arm's trials. A crash, a time-out and a budget
   stop are scored as a failed trial by the tool, not as an error, so a broken set-up could
   otherwise look like an effect. All trials stay in the gate.
4. The store's manifest carries the expected experiment id, and `arci gate` on the store
   recomputes the decision from the stored trials and reports that it matches the stored
   one. An interrupted run or an ERROR supplies no statistical conclusion.

These checks do not establish the independence assumptions, and they do not give a 2.5%
error rate conditional on passing them.

## One start

One start, into a new and empty output folder. If the run is interrupted or ends in ERROR,
that is published as the result of this registration. A new run would be a new
registration that lists this one.

If it ends INCONCLUSIVE: no added rounds; no second run reported in its place; no other
wording under this registration; and the observed difference is not read as an effect, as
"nearly", or as "no effect".

## What will not be claimed, whatever the verdict

- Nothing about the 12B model or "the gap": it is in neither arm.
- Nothing about capability or cause, and not that naming the next step is what helped.
  A BLOCK supports "this replacement message helped on these 8 cells". Telling apart "a
  message" from "this message" would need a control message that names no next step.
- Nothing about the other 16 tasks, the other three conditions or the full suite.
- No comparison of run 3's counts with run 2's as an effect: other seeds, another release.
- Success rates from a run that stopped early are reported as counts, without fixed-sample
  confidence intervals.

## Command

```sh
cd plan/exec/v2/study
RUN3_ENV=<the environment above> sh run-3.sh real
```

The wrapper takes a permanent one-start marker, so that a second start is refused. It
changes into `order-desk-empty-message/`, sets the three `ARCI_QUICKSTART` variables (both
model ids `ollama:qwen3.5:4b-mlx-ctx32k`, temperature 0.7), switches tracing off and sets
the audit path. It refuses to go on unless this file, the digest list and every registered
file are committed unchanged in the commit the published branch points to, every digest
matches, the installed versions and the model id are the registered ones, and the
registered settings match. It makes one call to the model outside the experiment so that
the first trial is not a cold start; if that call fails it stops. Then it runs, under
`caffeinate`, with the environment's own Python:

```sh
python -m arci run arci.yaml --workers 1 --out ../runs-run-3
```
