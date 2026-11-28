# A verdict from results another tool produced

`arci verdict` reads pass/fail results that another tool wrote (Inspect AI logs, pytest JUnit
XML, or plain CSV / JSONL) and gives PASS, BLOCK or INCONCLUSIVE for a candidate against its
baseline, with ARCI's existing decision rule.

ARCI does not run anything on this path: no fault injection, no fault accounting, no replay.
It reads labels another tool wrote, checks the task list and the rounds, and applies one rule
from one file. The contract is [STATISTICS_OUTCOMES.md](../STATISTICS_OUTCOMES.md); the design
record is [0015](../design/0015-imported-outcomes.md). Commands below run from a clone's root.

## Try it in one command

```sh
arci verdict --example
```

```text
Descriptive verdict: the rule file declares it was written after outcomes existed. The error bound is not claimed.
VERDICT: BLOCK (exit 1)

BLOCK threshold crossed

1 of 5 registered rounds supplied
```

The example is round 1 of the [order-desk study](../results/order-desk-study.md), exported from
its store: 96 task ids, the candidate worse on 26 of them.

## Two kinds of verdict

- **Descriptive.** You already have result files and write the rule afterwards. The arithmetic
  is the same, but the rule did not come before the data, so the output starts with
  "Descriptive verdict" and the error bound is not claimed. `arci verdict-rule` always writes
  this kind (`fixed_before_runs: false`), because it reads files that already exist.
- **With the error bound.** You fix the rule file first, then run both arms, then run
  `arci verdict`. See "To claim the error bound" below.

## On results you already have (descriptive)

### Inspect AI

One JSON log per arm; its epochs are the rounds. A `.eval` file is not read directly: run
`inspect log dump FILE.eval > FILE.json` first. When a log has more than one scorer, name the
one to read with `--score` when you write the rule.

```sh
arci verdict-rule --tasks tests/unit/outcomes/real/inspect/baseline.json --score match --out inspect-rule.yaml
arci verdict inspect-rule.yaml --baseline tests/unit/outcomes/real/inspect/baseline.json --candidate tests/unit/outcomes/real/inspect/candidate.json
```

```text
Descriptive verdict: the rule file declares it was written after outcomes existed. The error bound is not claimed.
VERDICT: INCONCLUSIVE (exit 2)

no test crossed

3 of 45 registered rounds supplied

if every further pair is a non-errored tie, PASS is reached after 30 more complete rounds (270 more pairs)
```

Those two logs are test fixtures with 9 samples and 3 epochs, far too few to decide anything.

### CSV or JSONL

Three fields: `task_id`, `outcome` (`pass`, `fail` or `error`) and optionally `round`. Without
`round`, give one file per repetition and the order of the files is the order of the rounds.

```sh
arci verdict examples/outcomes/order-desk/run-2/rule.yaml --baseline examples/outcomes/order-desk/run-2/baseline.csv --candidate examples/outcomes/order-desk/run-2/candidate.csv
```

```text
Descriptive verdict: the rule file declares it was written after outcomes existed. The error bound is not claimed.
VERDICT: INCONCLUSIVE (exit 2)

no test crossed

5 of 5 registered rounds supplied

if every further pair is a non-errored tie, PASS is not reached inside the registered rounds
```

### pytest JUnit XML

One XML file per repetition for each arm, given in the order they were run. The id is
`classname::name`. A failed assertion is `fail`; a set-up error or a skipped test is an errored
pair, so deselect tests at the source (`pytest --deselect`), not in the rule. Not run here:

```sh
arci verdict-rule --tasks base-1.xml --out rule.yaml
arci verdict rule.yaml --baseline base-1.xml base-2.xml base-3.xml --candidate cand-1.xml cand-2.xml cand-3.xml
```

## To claim the error bound

1. Write the rule before either arm is run: the task list, the margin, the number of rounds.
   `arci verdict-rule` can draft it from an earlier result file, but the rule then applies to
   fresh runs of both arms, not to that file.
2. Set `fixed_before_runs: true` in the rule file, only if step 1 is true. ARCI cannot check
   this declaration.
3. Run both arms for the registered rounds, then run `arci verdict`.

The output then starts with the verdict line and states the bound: a wrong PASS and a wrong
BLOCK each have probability at most 2.5% at the default alpha, under the assumptions in
[STATISTICS_SUITE.md](../STATISTICS_SUITE.md) and six conditions ARCI cannot check:

1. the rule and its task list were fixed before either arm ran;
2. outcomes are independent across tasks and rounds, with no response cache shared between them;
3. each task behaves the same in every round;
4. pairing and round order were fixed in advance, and no round was left out or replaced;
5. infrastructure failures are labelled `error`, not `fail`;
6. the protocol was fixed before execution and both arms were graded by the same criterion.

PASS means "not worse by the margin or more". It never means an improvement is real.

## How many repetitions

One run of a small suite decides almost nothing. Model projections, not measurements
(independent tasks, the same in every round, no errors, baseline pass rate 9/10, defaults):

| Tasks | Rounds | PASS when the candidate is also 9/10 | BLOCK when the candidate is 7/10 |
|---:|---:|---:|---:|
| 50 | 1 | 0.040 | 0.022 |
| 50 | 3 | 0.504 | 0.292 |
| 50 | 8 | 0.962 | 0.800 |
| 100 | 1 | 0.263 | 0.138 |
| 200 | 2 | 0.954 | 0.767 |

INCONCLUSIVE with "k of N registered rounds supplied" means: run more repetitions under the
same rule and call the command again. A changed rule needs fresh runs of both arms.

## Adding rounds later

```sh
arci verdict rule.yaml --baseline b1.csv b2.csv b3.csv --candidate c1.csv c2.csv c3.csv --previous decision.json
```

`--previous` takes the `--json` output of the earlier call. It refuses the new call when the
rule differs or when an earlier round's outcomes have changed. It does not show that any run
happened or that the rule came before the data.

## In CI

Not run here. Exit codes: 0 PASS, 1 BLOCK, 2 INCONCLUSIVE, 3 ERROR (an input was refused).

```yaml
- run: |
    code=0
    arci verdict rule.yaml --baseline base-*.xml --candidate cand-*.xml --markdown verdict.md || code=$?
    cat verdict.md >> "$GITHUB_STEP_SUMMARY"
    exit "$code"
```

Shell globs sort by name, so number the files with leading zeros if there are ten or more.

## Not in 2.2.0

Reading `.eval` directly; more than one Inspect log per arm; promptfoo; a verdict mode in the
GitHub Action; HTML output; score columns in CSV and JSONL.

Since 2.5.0, promptfoo JSON can be converted to JSONL with `arci convert --from promptfoo` (see the [promptfoo recipe](promptfoo.md)) before `arci verdict-rule` and `arci verdict`.
