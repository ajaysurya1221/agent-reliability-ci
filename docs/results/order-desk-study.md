# Order-desk study: can a 4B local model replace a 12B one?

Two pre-registered runs of the LangChain quickstart suite (24 tasks by 4 conditions = 96
cells per round) on one laptop with Ollama, one worker, no spend. Baseline
`gemma4:12b-mlx`, candidate `qwen3.5:4b-mlx`, temperature 0.7, reasoning off, per-round
seeds, both arms with identical settings apart from the model. Rule: alpha 1/20, margin 10
points, at most 5 rounds.

Each run was registered in a pushed commit, with a written prediction, before its first
trial: run 1 at
[`8ff0c3a`](https://github.com/ajaysurya1221/agent-reliability-ci/commit/8ff0c3a), run 2 at
[`6fbdb1c`](https://github.com/ajaysurya1221/agent-reliability-ci/commit/6fbdb1c). The
working records (pre-registrations, rendered reports, full write-ups) are on the branch
[`v2/phase0`](https://github.com/ajaysurya1221/agent-reliability-ci/tree/v2/phase0/plan/exec/v2/study).
The run stores and logs are kept by the maintainer and are not in the repository.

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

These cuts were chosen after seeing the data. Since 2.1.0 the never-called count and the
two uninjected-failure counts appear in every suite report ("Tool outcomes"); the first-call
count was computed by hand from the store.

## What the two runs do and do not show

In run 2, 77 of the candidate's 428 passes came after a tool error that, under run 1's
set-up, would have ended the trial. The observed gap was 10.8 points (52 of 480) against
27.1 points (26 of 96) in run 1; the runs differ in rounds and seeds, so the difference
between them is not a measured effect.
Run 2 did not reach `PASS`: the observed gap, 10.8 points, sits on the 10-point margin,
where this test needs the most pairs, and the registered budget was not extended. Neither
run says anything about other tasks, other prompts, or these models in general. Each is one
run on one machine.

Thanks to u/Significant_Tune9219 for the comment that led to run 2, and to
u/ChemicalExcellent463 for asking what the 4B model did when it skipped the lookup.
