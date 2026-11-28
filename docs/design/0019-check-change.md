# 0019: `arci check-change`, one command for a change to an agent's harness

Record by the orchestrator, 2026-11-28. The maintainer chose this work on 2026-11-28 ("One-command
test"), knowing that it sets aside, for this one improvement, the decision of the day before to
build nothing until one person outside the project had tried the idea by hand (decisions D-38 and
D-40 in `plan/exec/v2/DECISIONS.md` on the branch `v2/phase0`). An independent consultant (Codex,
read-only) designed the interface and the acceptance items against the released code; where this
record departs from its answer, the departure is listed at the end. Nobody outside the project has
asked for this command or used it.

## Why

Someone changes a prompt, a tool's reply, a skill or a setting of an agent and wants to know
whether the new version is worse than the old one. With 2.4.1 they must run their tests several
times on each version by hand, keep the result files apart, run `arci verdict-rule`, run
`arci verdict` with every file, and, to claim the error bound, follow the manual procedure in
`docs/recipes/verdict.md` ("To claim the error bound"). `arci check-change` does those steps in
the documented order with one command. It adds no statistics: the rule, the pairing and the
sequential reading are the released ones (`docs/STATISTICS_OUTCOMES.md`, `docs/STATISTICS_SUITE.md`).

## Decision

```text
arci check-change --baseline 'CMD' --candidate 'CMD'
    [--format junit|csv|jsonl] [--margin 1/10] [--max-rounds N]
    [--out-dir DIR] [--timeout-seconds 600] [--plan-only]
```

- `--baseline` and `--candidate` are command templates. Each must contain the placeholder `{out}`
  at least once. The tool splits a template into arguments (as a POSIX shell would, with
  `shlex.split`), replaces `{out}` inside every argument with a fresh absolute path, and starts
  the program directly, without a shell, from the caller's directory. A user who needs a shell
  writes `sh -c '...'` themselves. The child also receives `ARCI_CHANGE_ARM` (`baseline` or
  `candidate`) and `ARCI_CHANGE_ROUND` (0 for discovery, then 1, 2, ...) in its environment.
- The command must write one results file to `{out}` in a format `arci verdict` already imports:
  pytest JUnit XML (the default), CSV or JSONL. One file is one round of one side. The tool
  assigns the round; a round label inside the file that contradicts it is an error.
- `--margin` is the allowed loss, as in the released rule (default `1/10`). `--max-rounds`
  defaults to the smallest number of rounds for which tasks times rounds is at least 400 pairs,
  and never fewer than the released plan checks allow.
- `--out-dir` is created exclusively (it must not exist). Default: a new, unique child of
  `./arci-changes/`.
- `--plan-only` runs discovery, writes the registration files, prints the plan and stops with
  exit 0 before any evaluated launch.

### Order of work

1. **Discovery.** One baseline launch that is never scored. Its task ids define the task list.
   Its output is kept.
2. **Registration, before either evaluated side runs.** The tool writes, in this order: the rule
   (`rule.yaml`, with `fixed_before_runs: true`, built by the released `discover_rule`), its
   digest (`rule.sha256`), and `plan.json` (both command templates, format, margin, round cap,
   timeout, the task list, and for every round which side runs first, from the released
   `suite_schedule.arm_order` keyed by the rule digest). Then it prints the plan: tasks found,
   round cap, the largest number of launches including discovery, and the earliest rounds at
   which PASS or BLOCK can be reached (the released `earliest_pass_round`, `earliest_block_round`
   and `never_differs_pass_round`), with the note that these are extremes and not estimates.
3. **Rounds.** Round 1 runs the baseline again. In every round both sides are launched once, in
   the registered order. After each complete round the released sequential rule is applied to the
   complete prefix (`decide_outcomes` with the previous decision). The tool stops at PASS or
   BLOCK, or at the cap with INCONCLUSIVE. Nothing is launched after the stop.
4. **Output.** First, under a heading that names this command, two plain sentences: what the
   verdict means for these tasks and this margin (fixed text per verdict, below), and how many
   task runs each side passed. Then the verdict block that `arci verdict` prints for the same
   files (the released terminal renderer), followed by: the launch record,
   the passes of each side in absolute numbers, every task the candidate lost in two or more
   rounds with its loss count, the assumptions below, and an index of every file written.

### The plain sentences

- PASS: "PASS: on these N tasks the new version is not worse than the old one by more than the
  allowed loss of M. It does not say the new version is better."
- BLOCK: "BLOCK: on these N tasks the new version is worse than the old one by more than the
  allowed loss of M."
- INCONCLUSIVE: "INCONCLUSIVE: after R rounds the runs do not decide either way. That is an
  answer, not a failure: there is not enough evidence yet."
- ERROR: "ERROR: the campaign could not be completed, so there is no verdict." and the reason.
- Then: "Old version passed X of Y task runs. New version passed Z of Y." (not printed when no
  evaluated round is complete).

M is printed as the registered fraction and, when it is a whole number of hundredths, also in
points ("1/10, 10 points"). In the launch record every line names its exit status in words.

### Exit codes

`0` PASS (or `--plan-only`), `1` BLOCK, `2` INCONCLUSIVE at the cap, `3` ERROR. These are the
released codes of `arci verdict`.

### What ends the campaign with ERROR

A launch that cannot start, a timeout, a signal, an exit status other than 0 or 1, a missing,
empty or unreadable results file, a results path that is a symbolic link or not a regular file
(the file is opened without following links and the bytes read once are the bytes scored), a
results file that existed before the launch or carries a JUnit `timestamp` that denotes the same
instant as an earlier round of the same side (compared as instants where the value parses, as
text otherwise), a duplicate or unknown task id, a contradicting round label, a registration
file (`rule.yaml`, `rule.sha256`, `plan.json`) or an earlier sealed decision that no longer
equals what the tool wrote (both are held in memory and compared after every launch and before
any verdict), or a reader failure of any kind while importing a results file. The evidence so far is kept. No round is retried, skipped or
replaced, and an earlier usable prefix is not turned into a verdict. Every launch runs in its
own process group; when a launch ends for any reason, whatever is left of that group is stopped
before results are read or another launch starts. The group is signalled while its leader's
process id is still reserved (the leader is reaped only afterwards), so that an unrelated
process can never be hit, and the leader's own exit status is the one recorded. A helper that
puts itself into a new session of its own is outside the group and is not stopped: that is a
stated limit. The registration files and all earlier sealed decisions are compared with the
copies in memory immediately before every launch as well as after it. Every results file is
captured once into a snapshot the tool owns; the snapshot's digest is held in memory, the
released reader is given the snapshots, and a results file or snapshot that no longer matches
its digest ends the campaign with ERROR. Memory use does not grow with the number of rounds; a single results file is read into
memory while it is hashed and parsed, as the released reader does. Earlier captures are
verified before every launch too. The sealed decisions name the snapshots, and the manual
replay uses the snapshots; the files the test command wrote are kept beside them for
inspection. When the command itself is interrupted or told to terminate, it stops the running
launch's process group, reaps its leader, writes that the campaign was cancelled (no verdict)
and ends with the conventional status for that signal. On a platform where it cannot wait for
a child without reaping it, it says so and refuses to start. A margin for which no number of pairs up to the released ceiling can reach a verdict is
refused before discovery.

**This command is not a sandbox.** It catches accidents and the reuse it can see. A test command
that deliberately rewrites the tool's files while it runs, a fresh hard link to an old results
file, and model answers served from a response cache are all outside what it can detect, and the
recipe says so. `--margin` and `--max-rounds` are validated
before discovery is launched, as far as they can be without the task list. A wrapper script is the
place to map another test runner's failure codes to 0 or 1.

Inside two valid files, a task missing on either side or marked as an error counts as one errored
pair, scored as the released rule scores it. More errored pairs than the released tolerance
(`ceil(registered pairs / 100)`) is ERROR.

### Files written

`plan.json`, `rule.yaml`, `rule.sha256`, `discovery/` (output, stdout, stderr, exit status),
`round-NNN/baseline.*` and `round-NNN/candidate.*` (results, stdout, stderr, exit status), the
sealed decision after every round, and `verdict.txt` (what was printed).

## What the bound means here, and when it is not claimed

The rule is fixed before fresh runs, so the command prints the bounded verdict of the released
rule: read at complete round ends, with the default alpha of 1/20, a wrong PASS when the mean
difference is at or below minus the margin, and a wrong BLOCK when it is at or above it, each have
probability at most 2.5% over the campaign, **under conditions the tool cannot check and prints
every time**: every round really reruns the agent (no cached or replayed answers); pairs are
fresh and jointly independent; the tasks, inputs, versions, grading and retry policy stay fixed
for the whole campaign; there is no effect of which side runs first; infrastructure failures are
labelled as errors and not as task failures; the round order is intact. PASS means "not worse
than the margin on these tasks", never "better" and never "equal".

Results that already exist, or a rule written after looking at results, go through the released
descriptive `arci verdict`. This command does not import them.

## Three ways it can mislead, and what the tool prints

1. **Cached answers.** A fresh file can hold recycled model responses. The tool refuses the reuse
   it can see (the two file checks above) and prints that matching outcomes alone cannot show a
   cache.
2. **A deterministic command.** Ties in every round reach PASS even when both sides fail every
   task. The tool prints absolute passes per side, and a warning when both sides produced
   identical outcomes for every task in every round.
3. **One task that keeps losing.** A candidate that always loses one task of many can still PASS,
   because the rule is about the mean. The tool lists every task lost in two or more rounds.

## Code

New module `src/arci/change.py`; one dispatch entry and one sub-parser in `src/arci/cli.py`
(not a frozen file). Reused, unchanged: `outcomes.discover_rule`, `load_rule`, `rule_sha256`,
`decide_outcomes`; `suite_schedule.arm_order`; `suite_stats.earliest_pass_round`,
`earliest_block_round`, `never_differs_pass_round`, `check_rule_plan`;
`outcome_report.render_terminal`; the importers. Standard library, `pydantic` and `pyyaml` only.
No frozen file is edited. This record is added to `FROZEN.sha256` by the orchestrator.

## Acceptance items

All offline, with fake commands (small scripts that write results files).

1. Discovery is launched once, is not scored, and its task ids are the rule's tasks.
2. `rule.yaml`, `rule.sha256` and `plan.json` exist, and are complete, before the first evaluated
   launch starts (the fake command records what exists when it runs).
3. In every round both sides are launched exactly once, in the order stored in `plan.json`, and
   that order equals `suite_schedule.arm_order` for the rule digest.
4. `{out}` is replaced inside an argument (`--junitxml={out}`), paths with spaces work, and no
   shell is involved (a template containing `;` or `$(...)` runs no second program).
5. Nothing is launched after the stopping round.
6. For each of `junit`, `csv` and `jsonl`: running `arci verdict` by hand on the files the
   command wrote gives the same counts, the same stopping round and the same exit code.
7. Twenty tasks, the candidate loses all of them: BLOCK at round 1, exit 1.
8. Twenty tasks, two losses and eighteen ties every round: INCONCLUSIVE at the cap, exit 2.
9. Both sides always pass every task: PASS, exit 0, and the deterministic-command warning is
   printed. Both sides always fail every task: PASS, exit 0, the same warning, and the absolute
   passes show zero.
10. Each structural failure listed under "What ends the campaign with ERROR" gives exit 3, keeps
    the files written so far, and starts no further launch. Tested one by one.
11. Errored pairs at the tolerance are accepted; one more is ERROR.
12. A results file that existed before the launch, and a JUnit file with a repeated `timestamp`,
    are each refused with exit 3.
13. `--plan-only` writes the registration files, prints the plan and makes no evaluated launch.
14. An existing `--out-dir` is refused before anything is launched.
15. The task that the candidate loses in two or more rounds is named in the output with its
    count.
19. A results path that is a symbolic link, including a link to an old results file, is refused
    with exit 3. So is a round directory replaced by a link.
20. After a wrapper that starts a helper process and then fails, and after a timeout with a
    grandchild, no process of that launch is alive when the command returns.
21. Deleting or changing `plan.json`, `rule.yaml` or `rule.sha256` during the campaign gives
    exit 3 before the next launch and before any verdict.
22. Replacing an earlier `decision.json` during the campaign gives exit 3; the predecessor of
    every decision is the seal the tool holds in memory.
23. Two JUnit timestamps that denote the same instant in different spellings (for example
    different numbers of trailing zeros) count as repeated.
24. An invalid `--max-rounds` (for example 0) or `--margin` is refused before discovery starts.
25. With exactly one candidate loss in one round and no other difference, neither the
    deterministic-command warning nor the lost-task list is printed, and the note about caches
    still is.
26. When the released renderer points to flags this command does not have, the first line after
    the released block names the file that holds the full table.
27. The two plain sentences are printed first for each of PASS, BLOCK, INCONCLUSIVE and ERROR,
    with the right numbers, and every launch-record line names its exit status in words.
28. A results file changed after it was captured (for example by a helper that outlives the
    launch in a session of its own) gives exit 3; running `arci verdict` by hand on the files
    left by a finished campaign reproduces its verdict.
29. With a registration file changed between two launches, no further launch is started.
30. A helper started by the test command in the same process group is gone when the launch
    returns, the recorded exit status is the leader's own, and no signal is sent after the
    leader has been reaped.
31. A margin that can never reach a verdict (for example 1/20000) is refused before discovery.
32. Sending an interrupt or a terminate signal to the command while a test command with a
    helper is running leaves no process of that launch alive, writes the cancellation to
    `verdict.txt` and gives no verdict.
33. The sealed decisions and the file index name the snapshots; `arci verdict` on the snapshots
    reproduces the verdict even when an original results file is changed after the campaign's
    last check.
34. When the first launch of a round overwrites an earlier round's results file, the second
    launch of that round is not started and the exit code is 3.
35. A returned input whose digest does not match the scored bytes is refused even when both
    files on disk are intact.
16. Self-comparison, by simulation: 10,000 seeded campaigns in which both sides draw outcomes
    from the same law (several pass rates, including 0.5). The one-sided 95% binomial upper limit
    on the share of BLOCK is at most 2.5%. The test says in its name and docstring that this is
    a finite check of the released rule through this command's bookkeeping, not a proof. Items
    16 and 17 must go through the same assessment code as a real campaign (the released
    `decide_outcomes` on complete prefixes with the previous decision): with that function
    replaced by one that raises, both tests must fail.
17. Known difference, by simulation: the candidate's pass rate is 30 points below the baseline's
    on 20 tasks; at least 95% of 1,000 seeded campaigns end in BLOCK and none in PASS.
18. `ruff format`, `ruff check` and `basedpyright` are clean on the new files; the whole existing
    test suite still passes; `shasum -a 256 -c FROZEN.sha256` passes.

## Documents

One recipe, `docs/recipes/check-change.md`: what it is for, a worked example with pytest, what
each launch costs (the plan table), the conditions, the three ways it can mislead, what PASS,
BLOCK and INCONCLUSIVE mean in plain words, and what is left out. One entry under "Unreleased" in
`CHANGELOG.md`. The README's first screen is not changed by this work.

## Not in this version, on purpose

Inspect AI logs (one log holds many epochs, which does not fit one file per round), resuming an
interrupted campaign, running launches in parallel, checking out two versions of a repository,
any new statistic, reusing the discovery run as round 1, and extending the cap after seeing
results.

## What may and must not be said

May: that it runs the released rule on fresh paired runs of the user's own test command, with
the conditions printed. Must not: "first", "only" or any claim of novelty; that PASS means the
change is an improvement or safe; anything about real agents or hosted models from the offline
fixtures and simulations used to test it; that anyone outside the project uses it.

## Departures from the consultant's answer

- `--plan-only` is added (the consultant asked for the plan to be printed before the budget is
  spent; this lets a user stop there).
- The environment variables `ARCI_CHANGE_ARM` and `ARCI_CHANGE_ROUND` are added for wrappers.
- The consultant's simulation item covered the self-comparison; item 17 adds a known difference.
- Items 19 to 26 and the additions to the ERROR list come from a hostile review of the first
  build on 2026-11-28 (eleven findings, all accepted). Items 27 to 31, the snapshot rule and the
  "not a sandbox" paragraph come from the orchestrator's end-to-end try and a second hostile
  review the same day (eight findings; the one about a same-user helper racing the tool's
  temporary files is answered by that paragraph, not by code). Items 32 to 35 and the corrected
  sentence about memory come from a third review (four findings; memory growth with the size of
  one results file is accepted as a stated property, not fixed).
