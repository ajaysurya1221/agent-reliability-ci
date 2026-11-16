# Order-desk study: can a 4B local model replace a 12B one?

Three pre-registered runs on one laptop with Ollama, one worker, no spend. Runs 1 and 2
ask the question in the title. Run 3 asks a different question, about the 4B model alone.

The test tool is ARCI, the tool in this repository. A cell is one task under one
condition. The four conditions are: clean (no fault), a tool timeout, a tool error once,
and an empty result from the order lookup. In each round every cell is run once in each
arm; the two trials of a cell are a pair.

**Runs 1 and 2 compare two models** on the LangChain quickstart suite (24 tasks by 4
conditions = 96 cells per round). Baseline `gemma4:12b-mlx`, candidate `qwen3.5:4b-mlx`,
temperature 0.7, reasoning off, per-round seeds, both arms with identical settings apart
from the model. Rule: alpha 1/20, margin 10 percentage points of pass rate, at most 5
rounds.

**Run 3 is a different comparison.** It does not compare the two models. Both arms use the
4B model. One arm gives the model a short message when an order lookup comes back empty.
The other arm gives it `null`, as in run 2. The run uses 8 cells, chosen after run 2. The
arm with the message passed more often. The tool prints this result as `BLOCK`, because
the arm without the message is labelled the candidate. So `BLOCK` in run 3 does not mean
that the 4B model failed again. Run 3 has its own section and its own table below:
[Run 3](#run-3-2026-11-16-a-message-at-the-empty-lookup-one-model-in-both-arms).

Runs 1 and 2 were each registered in a pushed commit, with a written prediction, before
the first trial: run 1 at
[`8ff0c3a`](https://github.com/ajaysurya1221/agent-reliability-ci/commit/8ff0c3a), run 2 at
[`6fbdb1c`](https://github.com/ajaysurya1221/agent-reliability-ci/commit/6fbdb1c). The
working records (pre-registrations, rendered reports, full write-ups) are at commit
[`d46367d`](https://github.com/ajaysurya1221/agent-reliability-ci/tree/d46367d/plan/exec/v2/study).

The sealed stores of all three runs are in the repository under
[`order-desk-study/`](order-desk-study/README.md). A test re-derives each decision from the
stored trials. The logs of runs 1 and 2 are kept by the maintainer and are not in the
repository.

## Runs 1 and 2: the 12B model against the 4B model

| | Run 1 (2026-11-11) | Run 2 (2026-11-13) |
|---|---|---|
| Set-up | A tool's `ValueError` (a wrong argument) ends the trial | The same, but a tool's `ValueError` is returned to the model, in both arms |
| Prediction written first | `PASS` (wrong) | `INCONCLUSIVE`, low confidence (right) |
| Verdict | `BLOCK` at round 1 | `INCONCLUSIVE` after 5 rounds |
| Baseline passed | 96 of 96 | 480 of 480 |
| Candidate passed | 70 of 96 (72.9%) | 428 of 480 (89.2%) |
| Pairs: only baseline passed / tie / only candidate passed | 26 / 70 / 0 | 52 / 428 / 0 |
| BLOCK wealth, PASS wealth (threshold 40) | 156.2, 0.0019 | 0.49, 0.020 |
| Injected fault fired, candidate, per faulted condition | 18 to 20 of 24 | 119 to 120 of 120 |
| Wall time | 17 min 43 s | 76 min 47 s |
| Report | [order-desk-study.html](order-desk-study.html) | [order-desk-study-run-2.html](order-desk-study-run-2.html) |

The runs differ in more than the one change (run 2 has five rounds, so other seeds), so the
table describes two experiments; it is not a measured effect of the change.

## Correction to run 1 (2026-11-13)

The first write-up of run 1 said of the candidate's failures: "This is a capability gap on
one task type, not a robustness gap." That claimed more than was measured. A reader,
u/Significant_Tune9219, pointed out in the
[r/LangChain thread](https://www.reddit.com/r/LangChain/comments/1xtror1/i_put_create_agent_behind_a_faultinjecting/)
that the run could not separate the 4B model reasoning worse from the 4B model needing
tighter tool contracts. The stored run confirmed it:

- 23 of the candidate's 26 failures were `ValueError: unknown SKU` from `check_stock`.
- In 21 of those 23, the model's first and only call was `check_stock` with the order id
  as the SKU; it never called `lookup_order`.
- The tool raised. The retry middleware handled only timeouts and runtime errors, so the
  model was never shown the error. One wrong call ended the trial.

So run 1 measured: the 4B model makes a wrong first call more often, in a set-up where a
wrong call is fatal. Its verdict stands for that set-up. Run 2 was registered to ask the
reader's question.

## What run 2 showed (descriptive; none of this is part of the verdict)

Candidate, 480 trials. The baseline's count is 0 on every line.

| | Candidate |
|---|---|
| Never called `lookup_order` | 2 (both failed) |
| First tool call was not `lookup_order` | 108 (all `check_stock`, all on stock-note tasks) |
| Had a tool failure with no injected fault, then passed | 77 |
| Had one, then failed | 47 |

Of the 115 failed `check_stock` calls behind those counts, 112 passed the order id as the
SKU.

- The wrong first call is as common as in run 1: 108 of 160 stock-note trials.
- Shown the error, the model went on to look the order up in 106 of the 108, and 68 of
  the 108 passed.
- Most of the remaining failures (41 of 52) are in trials with both an injected fault and
  an uninjected tool failure. On stock-note tasks
  under the injected empty result, the candidate passed 7 of 40; after a wrong first call
  there, 0 of 26. Under the clean and timeout conditions the same wrong first call was
  followed by a pass in 52 of 58 trials.
- Under the empty result the baseline called `lookup_order` a second time in all 120
  trials; the candidate in 87 of 120.

These cuts were chosen after seeing the data. Since ARCI 2.1.0 the never-called count and the
two uninjected-failure counts appear in every suite report ("Tool outcomes"); the first-call
count was computed by hand from the store.

## What runs 1 and 2 do and do not show

In run 2, 77 of the candidate's 428 passes came after a tool error that, under run 1's
set-up, would have ended the trial. The observed gap was 10.8 points (52 of 480) against
27.1 points (26 of 96) in run 1; the runs differ in rounds and seeds, so the difference
between them is not a measured effect.
Run 2 did not reach `PASS`: the observed gap, 10.8 points, sits on the 10-point margin,
where this test needs the most pairs, and the registered budget was not extended. Neither
of these two runs says anything about other tasks, other prompts, or these models in
general. Each is one
run on one machine.

## Run 3 (2026-11-16): a message at the empty lookup, one model in both arms

Two readers of the post about runs 1 and 2 each asked about a further variant. "Agentic
Affairs" (dev.to) asked for a retry of the empty lookup in code. "Halfcycle" (Hashnode)
asked whether a message that names the next step, at the point of failure, would close the
gap. In run 2, 34 of the candidate's 52 failures were under the injected empty result.
That result reaches the model as a successful tool result whose whole content is the text
`null`.

Run 3 answers a narrower question than either reader asked. It does not test a retry in
code. It does not measure the gap between the two models. It tests one message against
`null`, with the 4B model, on 8 cells.

**Read this before the table.** Run 3 does not compare the two models: both arms use the
4B model. And the roles are swapped. The test has three verdicts. `PASS` says the
candidate arm is not worse than the baseline arm by more than the margin. `BLOCK` says it
is worse by more than the margin. `INCONCLUSIVE` says the rounds ran out first. No verdict
says that an arm is better. So, to test whether the message helps, the arm with the
message is set as the baseline and run 2's set-up is set as the candidate. `BLOCK` in this
run means that the set-up without the message passes less often, by more than the margin.
It is not a second failure of the 4B model against the 12B one.

| | Run 3 (2026-11-16) |
|---|---|
| Baseline arm (with the message) | 4B, run 2's set-up, plus one middleware (code that sits between the model and the tools): when a `lookup_order` result is a successful tool message whose content is `null`, the content becomes "lookup_order returned an empty result. Call lookup_order again with the same order_id." |
| Candidate arm (run 2's set-up, no message) | 4B, run 2's set-up unchanged: the model gets `null` |
| The same in both arms | the model, temperature 0.7, reasoning off, the system prompt (it ends "Retry an empty lookup once."), the tools, the check, the budgets |
| Grid | the 8 stock-note tasks under the injected empty result (8 cells a round), chosen after seeing run 2 |
| Rule | alpha 1/20, margin 10 percentage points on these 8 cells, at most 40 rounds, per-round seeds, stop at the first verdict |
| Prediction written first | none was supplied |
| Verdict | statistical `BLOCK` at round 2. The tool's reason line is "regression established". Here that means: the arm without the message did worse than the arm with it. |
| Baseline (with the message) passed | 15 of 16 |
| Candidate (run 2's set-up) passed | 2 of 16 |
| Pairs: only the arm with the message passed / both the same / only run 2's set-up passed | 13 / 3 (2 both passed, 1 both failed) / 0 |
| Run 3 BLOCK wealth and PASS wealth (threshold 40) | 42.79 and 0.013 |
| Injected fault fired, baseline and candidate | 16 of 16 and 15 of 16 |
| Wall time | 2 min 3 s |

The verdict says that the gain is more than 10 percentage points on these 8 cells. It does
not say how much more. The two counts, 15 of 16 and 2 of 16, come from 16 pairs in a run
that stopped early. Do not quote them as pass rates. No confidence interval is given for
them.

A statistical `BLOCK` is a `BLOCK` that the test reached from the pass and fail counts.
The tool can also give a `BLOCK` when one candidate trial breaks a hard rule (a hard
violation). A pair with a trial that ended in an error is an errored pair. Neither
happened in run 3.

Wealth is the test's running score for a verdict. There is one score for `BLOCK` and one
for `PASS`. A score goes up when the pairs support that verdict. The test gives a verdict
when a score reaches 40 at the end of a round. Alpha 1/20 is shared by the two verdicts,
so each has a bound of 1/40, which is 2.5%. That is where the 40 comes from.

### What the verdict says

On these 8 cells, with this 4B model, this prompt and temperature 0.7, the registered test
decided that the arm in which the `null` of the empty lookup is replaced by the message
passes more often than the arm with `null`, by more than 10 percentage points of mean pass
rate over the 8 cells. This is a threshold decision, not an estimate of the size of the
gain.

Under the rule's assumptions (independent cells and rounds, each cell with the same chance
of passing in every round, no effect of which arm runs first), the chance of a statistical
`BLOCK` is at most 2.5% if, in every round, the mean gain over that round's scenario
instances on these 8 cells is 10 points or less. ARCI does not check those assumptions,
and there is no guarantee averaged over seeds. This is a third experiment on related data,
chosen after seeing runs 1 and 2; the bound applies to this registered experiment alone,
and no error guarantee across the three experiments is claimed. The three results are not
pooled.

The test checks for a verdict at the end of each round. The run stopped after round 2. On
8 cells, round 2 is the first round at which this rule can give `PASS` or a statistical
`BLOCK`.

### Counts (descriptive; registered in advance; they decide nothing)

| | With the message | Run 2's set-up |
|---|---|---|
| Trials | 16 | 16 |
| Passed | 15 | 2 |
| Failed | 1 | 14 |
| Errored | 0 | 0 |
| Termination `completed` | 16 | 16 |
| Ended on a budget or the time limit | 0 | 0 |
| First tool call was not `lookup_order` | 9 | 11 |
| Never called `lookup_order` | 0 | 1 |
| Empty result delivered (the call recorded as successful in each) | 16 | 15 |
| Then read the order again | 16 (15 passed) | 2 (2 passed) |
| Then did not read it again | 0 | 13 (0 passed) |
| Had a tool failure that was not injected | 9 (8 passed) | 14 (1 passed) |

The injected empty result fired in 15 of the 16 trials of run 2's set-up. In the other
trial (round 2, desk-06) the model made no tool call, so there was no lookup to empty.
That trial failed. The tool failures that were not injected were all `check_stock` calls
that returned an error.

Passes per task, with the message then without (2 trials per task and arm): desk-03 2 and
0; desk-06 2 and 0; desk-09 2 and 1; desk-12 2 and 0; desk-15 2 and 0; desk-18 1 and 0;
desk-21 2 and 0; desk-24 2 and 1. Two scripts written separately computed the counts and
agree, and a recount from the store by an agent that had read no write-up gave the same
numbers.

### What run 3 does not show

- Nothing about the 12B model or the gap between the models: the 12B is in neither arm.
- Nothing about capability or cause, and not that naming the next step is what helped.
  One message was compared with `null`. A message of the same length that names no next
  step was not tested.
- Nothing about the other 16 tasks, the other three conditions or the full suite.
- No size of the gain beyond "more than 10 percentage points on these 8 cells".
- No effect read from run 3's counts against run 2's: other seeds, another release (ARCI
  2.4.0; run 2 used 2.0.0).

### Registration, checks and errata

- Registered at
  [`c217ae6`](https://github.com/ajaysurya1221/agent-reliability-ci/commit/c217ae6), pushed
  19 seconds before the start script began. One start; the script refuses a second.
- A smoke run is a short trial run to check that the set-up works. One came before the
  registration and is disclosed in it: 16 trials with the real model under another suite
  id and another rule, 6 of 8 with the message and 3 of 8 without. It is not evidence and
  is not pooled.
- The registration fixed four conditions for reading the verdict as a statement about the
  message. (1) The start checks passed: the registration published and unchanged, 17 file
  digests, the software versions, the model id. (2) The middleware replaced `null` with
  the message 16 times, and the empty result reached the arm with the message 16 times.
  The audit file records what the middleware wrote, not what the model received, and its
  lines cannot be matched to single trials, so the equal counts are supporting evidence
  only. (3) No trial crashed, and none ran out of time or budget (the registration allowed
  at most one trial in 20 per arm). (4) The store carries the registered experiment id,
  and the stored decision matches a recomputation. All four hold. They do not show that
  the independence assumptions are true. They also do not mean that the 2.5% bound holds
  for runs that pass these checks.
- Erratum 1: the registration says nothing was changed after the smoke run. That is not
  true of the script that starts the run. After the smoke run and before the registration,
  start checks were added to it: a marker that allows only one start, checks that the
  registration is committed and published, checks of the versions and the model id, a stop
  if the warm-up call fails, and a check-only mode. The other study files were not changed
  after the smoke run, as far as file times show. The registered digest of the script is
  the digest of the version that ran.
- Erratum 2: the registration says that 32 of the candidate's 34 failures under the empty
  result in run 2 were on the 8 stock-note tasks. The store gives 33 of 34 (the candidate
  passed 7 of 40 on these cells). 32 is the number of those failures in which the model
  got the empty result and did not read the order again. This does not change the grid,
  the rule or the verdict.
- Not run: the retry in code that "Agentic Affairs" asked for. If the code repeats the
  lookup, the model gets the order without doing anything. The result would be nearly
  fixed in advance and would say little about the model. The working records hold a
  scripted test, with no model, that shows how such a retry behaves.
- Working records (pre-registration, result file with the errata, digests, logs, count
  scripts) at commit
  [`49d86b3`](https://github.com/ajaysurya1221/agent-reliability-ci/tree/49d86b3/plan/exec/v2/study);
  the reviews are beside them in
  [`reviews/`](https://github.com/ajaysurya1221/agent-reliability-ci/tree/49d86b3/plan/exec/v2/reviews).
  The sealed store is under [`order-desk-study/run-3/`](order-desk-study/README.md); a test
  recomputes its decision from the stored trials. Recomputing the decision is not
  rerunning the model.

Thanks to u/Significant_Tune9219 for the comment that led to run 2, to
u/ChemicalExcellent463 for asking what the 4B model did when it skipped the lookup, and to
"Agentic Affairs" and "Halfcycle" for the questions that led to run 3.
