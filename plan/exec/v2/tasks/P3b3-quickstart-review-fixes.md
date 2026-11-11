# TASK P3b3: fixes to the LangChain quickstart after review and the local-model pilot

Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-integration` (branch `v2/integration`,
your quickstart is committed). You own the files P3b and P3b2 gave you, plus
`src/arci/cli.py` and `src/arci/suite_runner.py` for item 2 only. Another task is editing
report code in a different worktree: do not touch `report.py`, `triage.py`, `diff.py`,
`planning.py`. No state-changing git, no network. Frozen files untouched.

Inputs: the review `plan/exec/v2/reviews/P3b-review-workflow.json` (20 findings with
reproductions) and the pilot `plan/exec/v2/pilot/PILOT.md` (two local Ollama models, 144
real sessions), both under `/Users/ajay/Developer/agent-reliability-ci/`. Every fix gets a
test that fails without it.

1. **Both arms failing everything must not look like a clean PASS** (blocking). Replacing
   the tasks as the README says gave `VERDICT: PASS`, exit 0, with all 192 trials failing,
   because the offline model only understands the shipped wording and a 0% tie is still a
   tie. The verdict is statistically correct (the candidate is not worse); the output hid
   why. So:
   - the offline model raises a clear set-up error for a prompt it does not understand
     (harness ERROR, not a tied FAIL), and the README says the offline model only solves
     the shipped tasks and must be replaced with the tasks;
   - see item 2.
2. **`arci run` and `arci gate` for suites print per-arm success counts** beside the pair
   counts (`baseline 0/96 passed, candidate 0/96 passed`), and one fixed warning line when
   the baseline passed fewer than half of its trials: a non-inferiority PASS then says
   little. When a run ends in ERROR, print the first harness-error detail and how many
   trials share it. No verdict logic changes.
3. **Exactly one model variable set is a set-up error**, not a silent comparison of a real
   model with the scripted one.
4. **What is compared must be in the sealed registration.** Today the model ids come from
   the environment at trial time, so different experiments get the same experiment id.
   Make the resolved model id of each arm, the temperature and the reasoning setting part
   of the sealed manifest, by whatever the descriptor already offers (for example
   `candidate_id` per arm, or the fixtures digest over the example's files with the
   settings in a file), and make the run refuse with a clear message when the environment
   disagrees with what is registered. Say in the README what changes the experiment id and
   what does not. If the descriptor offers nothing suitable, stop and report what would be
   needed.
5. **Real models need randomness between rounds** (pilot item 1). At temperature 0 every
   repetition is identical. With real models the example uses a temperature above 0 (one
   value for both arms, default 0.7, overridable by one variable and sealed per item 4) and
   `scenario_seeds: per_round`; the README explains why in two sentences. The offline path
   stays deterministic and says so, and says that with fixed seeds and a deterministic
   model every round is identical, so its BLOCK is by construction, not a measurement.
6. **The planted regression is honest** (review): the candidate's offline behaviour must
   differ from the baseline's only through the declared difference (no retry) under the
   injected faults; the scripted model itself behaves the same for both arms. If that makes
   the offline verdict something other than BLOCK at round 1, say what it is.
7. **The plain refund tasks** (pilot item 2): one model failed all 8 in the clean
   condition. Read `check.py` and the prompt against the task text and fix any place where
   the check demands something the task and prompt do not ask for. `check.py` must not
   grade an unrecognised action as a stock-note task: unknown action is a grader error.
8. **`arci init --langchain` in a non-empty directory** says to run it in an empty
   directory and does not suggest `--force`, which it rejects. The init check must not be
   fooled by a `tools/` or `agent/` package already in the directory.
9. **Tests**: the end-to-end timeouts leave at least a factor of three over the measured
   time; the non-LangChain init tests run in the core environment.
10. **README and recipe**: which suite commands exist (`report`, `triage`, `diff` and
    `plan` are being built in parallel: write that they are available, and list
    `minimize`, `bundle`, `replay`, `trace-check` as not built for suites); a one-line way
    to list failing trials; pin the install line to the first version that has the extra
    (`>=2.0.0`); an added fault on a tool some tasks never call is diluted into ties, and
    fault accounting in the report shows it; a tool that raises on a wrong argument crashes
    the run unless the agent handles it (pilot item 3); set-up ERROR covers what the code
    actually does; LangSmith tracing off in the printed next command.

Acceptance: the commands of P3b. Report under 50 lines: per item the change and its test;
the offline verdict and round; command tails; anything you could not do.
