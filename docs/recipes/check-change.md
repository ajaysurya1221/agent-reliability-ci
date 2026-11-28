# Test a harness change with your own command

Use `arci check-change` when you have changed a prompt, a tool reply, a skill or a setting.
Give it two commands that run the same tasks and grade them the same way. Choose how much
loss in pass probability you can tolerate. ARCI tests whether the mean loss on the
registered tasks falls above or below that margin. Each task gets equal weight.

## A pytest example

Suppose your tests read a prompt from the file named by `AGENT_PROMPT`. Keep both prompt
files in the current checkout. Each test should run the agent afresh and check its answer.
Run this from the directory containing the tests.

```sh
arci check-change \
  --baseline 'env AGENT_PROMPT=prompts/old.txt python -m pytest tests/agent --junitxml={out}' \
  --candidate 'env AGENT_PROMPT=prompts/new.txt python -m pytest tests/agent --junitxml={out}' \
  --out-dir prompt-comparison
```

The baseline runs once for discovery. Its JUnit case names (`classname::name`) become the
task list. Its outcomes never count. ARCI writes `rule.yaml`, its rule digest in `rule.sha256`,
then `plan.json` with both templates, the settings, tasks and launch order. It prints the plan
before starting either evaluated side. Each evaluated round runs both commands once, in the
registered order. The baseline runs again even in round 1. Immediately before and after each
launch, and before the verdict, ARCI checks the registration files and earlier sealed decisions
against what it wrote. A changed or missing record stops the campaign with ERROR.

For example, with 20 tests, if the old prompt passes all 20 and the new prompt fails all 20 in
round 1, the verdict starts like this.

```text
arci check-change verdict
BLOCK: on these 20 tasks the new version is worse than the old one by more than the allowed loss of 1/10, 10 points.
Old version passed 20 of 20 task runs. New version passed 0 of 20.
```

The exit code is 1. The launch record shows three launches including discovery.
To replay this example, use the indexed snapshots named in the sealed decision.

```sh
arci verdict prompt-comparison/rule.yaml \
  --baseline prompt-comparison/round-001/baseline.snapshot.xml \
  --candidate prompt-comparison/round-001/candidate.snapshot.xml
```

## Budget before running

One launch runs your whole test command, including its model calls and setup. One evaluated
round costs two launches. A pair is one task run on both sides. Add `--plan-only` to spend one
baseline launch on discovery and exit 0 after writing the registration. To run the comparison
afterwards, use a new directory. Without `--out-dir`, each invocation creates a unique directory
under `./arci-changes/`. An explicit directory must not exist.

| Tasks | Round cap | Max launches, including discovery | Earliest PASS, all wins | Earliest BLOCK, all losses | PASS with all ties |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 80 | 161 | round 2 | round 3 | round 16 |
| 20 | 20 | 41 | round 1 | round 1 | round 4 |
| 200 | 2 | 5 | round 1 | round 1 | round 1 |

These are extremes for complete rounds with no errors. They give no estimate of how soon your
change will decide. To compute the table, we used `default_max_rounds` and
`default_max_errored_pairs` from `arci.suite_stats` for each task count. We passed a
`SuiteRule` with alpha `1/20`, margin `1/10` and stakes `1/4` and `1/2` to `check_rule_plan`,
`earliest_pass_round`, `earliest_block_round` and `never_differs_pass_round`. Maximum launches
equal one plus twice the round cap.

Set the allowed mean loss with `--margin`, a positive fraction in lowest terms below one.
The default `1/10` means ten percentage points. The default cap is the smallest allowed cap
covering at least 400 pairs. Tight margins can require more. Set `--max-rounds N` to register
a different cap before evaluation. The released plan must allow PASS with all ties and allow
PASS when the error allowance is spent and every other pair is a win. It accepts at most
100,000 registered pairs. If even that many pairs cannot establish PASS when the sides always
tie, ARCI refuses the margin before spending a discovery launch. Fewer than three rounds gives
a warning.

## Commands, results and errors

Each template must contain `{out}`. ARCI splits the template using POSIX quoting, replaces
every `{out}` inside each argument with a fresh absolute path, then starts the program directly
in your current directory. Paths containing spaces work. Shell operators need an explicit
shell such as `sh -c '...'`. Each child receives `ARCI_CHANGE_ARM` (`baseline` or `candidate`)
and `ARCI_CHANGE_ROUND` (0 for discovery, then 1, 2 and so on).
The timeout defaults to 600 seconds per launch. Use `--timeout-seconds` to change it.
Each launch has its own process group. When the command exits or times out, ARCI stops any
remaining processes in that group before it reads the result or starts another launch.
If you press Ctrl-C during a launch, ARCI stops its process group, records the cancellation
in `verdict.txt` and exits with status 130.

Write one regular result file per launch. ARCI refuses symbolic links at the result path or
in place of the round directory. ARCI saves a snapshot alongside the original, for example
`round-001/baseline.snapshot.xml`. It records a digest as it copies the file. The reader
gets the discovery snapshot for the task list and the round snapshots for scoring. ARCI
checks earlier originals and snapshots against their digests immediately before each launch,
when assessing a round and before reporting the verdict. A mismatch ends the campaign with ERROR.
The reader loads one results file into memory at a time to hash and parse it.

The default format is pytest JUnit XML. Assertion failures
count as failures. Skipped tests and setup errors count as errors. Use `--format csv` or
`--format jsonl` for rows with `task_id` and `outcome` (`pass`, `fail` or `error`). An optional
`round` field must agree with the assigned round, including round 0.

A command may exit 0 or 1 with a valid file. Use a wrapper to translate another runner's
test-failure status. Failure to start, timeout, signal or another exit status stops the
campaign with ERROR. So does a missing, empty, unreadable or malformed file, a file already
at the output path before launch, a repeated JUnit timestamp on the same side, a duplicate
or unknown task, or a conflicting round label. Evidence already written stays in place.
ARCI compares timestamps as instants when it can parse them and as text otherwise.
There is no retry, skipped round, replacement or fallback to an earlier verdict.

Within valid files, a missing task or an error on either side counts as one errored pair.
Each such pair counts against both decisions. The cumulative allowance is one percent of
registered pairs, rounded up. One more gives ERROR at that round end.

## Read the verdict

- **PASS (0)** means the evidence puts the mean loss below the margin on these tasks.
  It establishes neither improvement, equality, safety nor performance on other tasks.
- **BLOCK (1)** means the evidence puts the mean loss above the margin on these tasks.
- **INCONCLUSIVE (2)** means the cap was reached with too little evidence in either direction.
- **ERROR (3)** means the campaign could not give a usable verdict.

ARCI reads the released rule at each complete round end and stops on a decision. Look in
`discovery/` and `round-NNN/` for each child's result, stdout, stderr and exit status.
Each complete evaluated round has a sealed decision. `verdict.txt` contains the printed plan,
verdict, launch record, absolute passes, repeated losses, conditions and file index.
The imported-verdict block describes the result reader. The separate launch record shows
which commands check-change started. If the terminal table is shortened, the next line after
the verdict block gives the path to the sealed decision with the full table.

## When the error bound applies

At the default alpha of 1/20, a wrong PASS when the true mean difference (candidate minus
baseline) is at or below minus the margin has probability at most 2.5% over this campaign.
A wrong BLOCK when the difference is at or above minus the margin also has probability at
most 2.5%. These bounds require all of the following.

- Fix the rule, task list, pairing and round order before either evaluated side runs.
- Really rerun the agent for every task. Use fresh pairs, jointly independent across tasks
  and rounds. Disable response caches and replay. Dependence within a pair is allowed.
- Keep each task's outcome law stable across rounds. Hold inputs, versions, settings, grading
  and retry policy fixed. Use the same grading criterion on both sides.
- Running one side before the other must have no effect. Reset any state that could carry over.
- Label infrastructure failures as errors.
- Keep the registered order intact. Never omit or replace rounds, extend the cap after seeing
  outcomes, or retry the same campaign until it passes.

## What it cannot see

A new file can contain old model answers from a response cache. A command can also create
a fresh hard link, a new name for an old results file. File contents and matching outcomes
cannot tell you whether the model ran again. Disable caches and have the command write new results.

Use test commands you trust. A command runs with your permissions and can deliberately
rewrite ARCI's own files while it reads them. ARCI checks for changes at specific times.
A helper that starts a separate session leaves the launch's process group and can keep running.

A deterministic command can reach PASS on ties even when both sides fail every task. Read
the identical-outcomes warning and the absolute passes. A mean can also hide one failing
task. The report names every task the candidate lost in two or more rounds and gives its count.

Use descriptive `arci verdict` for existing results or a rule written after seeing results.
This command does not import those campaigns, read multi-epoch Inspect AI logs, check out
versions, run launches in parallel, resume an interrupted campaign or add new statistics.
See the [imported-outcomes rule](../STATISTICS_OUTCOMES.md) and its
[round-end bound](../STATISTICS_SUITE.md).
