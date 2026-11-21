# Codex effort comparison draft. May project workers stay at high?

This comparison is separate from the order-desk study and is not one of its numbered runs.

Publication date (UTC) 2026-11-21, in the commit that adds this file; the actual push time is in the result
SHA-256 of codex-effort/digests.sha256 04f30ec8181586c456258b40af43f09bfdd03cee40861de86e4b19c7923e3cb9

## Question and decision

May the project keep using high reasoning effort for workers that must return a passing fix on these tickets within 1,200 seconds of agent wall time?
The comparison is high minus xhigh in mean probability of passing the registered check.
Each of ten tickets has equal weight. A ten-point shortfall is the decision boundary.
An eligible PASS supports keeping high for this deadline-bound work. An eligible BLOCK supports choosing xhigh.
INCONCLUSIVE or ERROR leaves the question open.

On 21 November the project used high for six worker assignments and xhigh for three
consults. D-29 reserved further runs through 14 December for new outside questions.
Nobody outside asked this question. The orchestrator and the consultant both advised
against an exception. The maintainer chose this one comparison in D-30. The requirement
to push the question, tasks, check, cap and stopping rule before any live trial stands.

## Arms

One laptop. One CLI executable. One model. Each invocation gets the same ticket text
as its partner. TASK is the full task string from that ticket's JSON, passed as one
argument. The cwd is a fresh export of the ticket's parent. Standard input is closed.
The per-invocation wall limit is 1,200 seconds. The two commands in shell notation are

```sh
codex exec -m gpt-6.2-astra -c 'model_reasoning_effort="xhigh"' \
  -s workspace-write -c 'approval_policy="never"' --skip-git-repo-check --json --ephemeral -o "$LAST" "$TASK"

codex exec -m gpt-6.2-astra -c 'model_reasoning_effort="high"' \
  -s workspace-write -c 'approval_policy="never"' --skip-git-repo-check --json --ephemeral -o "$LAST" "$TASK"
```

LAST is the absolute private work root followed by
`/rNN-TICKET-ARM.last.txt`. The driver captures the complete JSONL stdout as a private
transcript and keeps stderr separately. Both arms require the owner's signed-in profile.
A fresh profile per trial is unavailable. `--ephemeral` disables persistence of this
session on disk. The work root is `/Users/ajay/Developer/.arci-worktrees/codex-effort-private`.
The agent's PATH begins with `/Users/ajay/Developer/.arci-worktrees/codex-effort-agent-env/bin`.
Its Python has the dependencies and no installed ARCI. PYTHONPATH points to the export's src.

The first command is the baseline. The second is the candidate. CODEX_BIN selects one
executable for the campaign. Record the CLI version, the SHA-256 of the launcher and
the native executable it resolves to, the model name, Python version and ARCI version
at the start. Check both executable hashes for every invocation and save them with the
trial. The model service is hosted. Sampling is unseeded.

## Tickets

An agent selected these ten past fixes from origin/main before any live trial. It
preferred recent fixes, a small source edit, a short symptom and fast, local checks.
This is a deliberate selection. The parent visible checks had to pass. Each regression
witness had to fail on the parent and pass on the fix.
Preservation cases had to pass on both. The grader had to accept the scoped historical
patch in the parent and reject the untouched tree within 90 seconds. An earlier
log-reader candidate was dropped because its scoped reference patch failed.
No live success rate informed selection. The public fixes may be in model training data.

| Ticket | Parent | Fix | Symptom |
|---|---|---|---|
| csv-spaces | bebe900 | ea19251 | Blank lines reject a valid outcomes CSV |
| fault-report | c71a0b6 | 3023b96 | A later fault occurrence is misattributed |
| init-write | 314cbbd | 4451a90 | A failed flush can leave a published descriptor |
| interrupted-report | 973fc3e | 3fc34dd | An interrupt leaves mismatched reports |
| keep-output | 4a0e1a3 | f2674d7 | Cleanup removes a requested report |
| kept-read | 901e037 | 074fd7f | A reader misses a newly installed table |
| round-label | 1275d9f | b1551b6 | Alternate spellings identify one round |
| shorthand | 0dd4e2b | 314cbbd | One malformed condition loses a diagnostic |
| snapshot | dd380d8 | 92f6ae0 | A failed snapshot loses the prior tool state |
| store-lines | f3da872 | 1559f90 | Unicode in a field splits a stored record |

The ten JSON files in codex-effort/tickets contain the full commit IDs, verbatim tasks,
allowed files, exact visible and hidden case IDs and any registered hidden additions.
csv-spaces uses only the blank-line hunk from outcomes.py. Other reference patches use
the named source files from the fix. interrupted-report covers all, none and mixed prior
outputs at moves 1, 2 and 4, before and after each. keep-output checks that cleanup still
removes regular temporary files. fault-report varies declaration order and occurrence.
store-lines covers U+0085, U+2028 and U+2029. round-label retains historical -0 as zero.
kept-read schedules the replacement on CPython's file-open audit event, across open APIs.
Visible checks are selected existing tests of the affected behaviour. The keep-output
ticket uses its historical naming rules. Release 2.4.1 later reserved that name prefix.

## Check and labels

The driver exports the parent outside the checkout, without a .git directory. The task
limits the agent to that export. The hidden test is installed only after the agent exits.
The grader takes a fresh parent export. It inventories paths, types, modes and contents,
including ignored files. It saves the submitted diff and its SHA-256. It applies the diff
and checks that the applied files match the submission. Edits to tests are forbidden.

Run the parent's visible cases first. Install the historical hidden file and any frozen
supplement only in the clean grading export. Run every grading process with
`/Users/ajay/Developer/.arci-worktrees/codex-effort-agent-env/bin/python` and PYTHONPATH set
to that export's src. Visible and hidden stages together receive 90 seconds. Verify the
full set of JUnit case identities, including parameters, exit status and individual results.
A macOS sandbox confines grader writes to per-process scratch and restricts reads to
the clean tree, scratch and runtime files. The published-tip preflight must demonstrate
these restrictions with stand-ins before admission. Only the harness tests and ARCI
verdict use run4-env.

- **Pass** requires a completed agent turn, successful exit, a nonempty allowed patch
  that applies exactly, and a passing result for every registered case.
- **Fail** includes a wrong, empty or out-of-scope patch, a documented agent crash,
  a reproducible submission fault, or a 1,200-second deadline miss with agent work
  still active in the terminal events.
- **Error** includes missing executables, grader infrastructure faults and service
  failures. Use the exit status and terminal CLI events for quota, authentication,
  throttling, transport, 5xx and exhausted retries. A documented service stall still
  active at the limit is an error. Fresh agent work after a transient diagnostic can
  establish recovery. Tool output and stderr cannot attribute termination.
  An unattributed termination is an error and bars interpreting any crossing.
- For ambiguous pytest exits, timeouts, malformed, skipped or mismatched results,
  run the registered reference under the same stage allowance. If the reference
  passes, repeat the submission on a fresh export with that same allowance. Only the
  same reproduced submission fault earns fail. A failed control or unstable result
  earns error. Diagnostic controls can take additional wall time. No agent is retried.

### Assumptions about live CLI evidence

The installed CLI documents JSONL stdout, a separate last-message file and ephemeral
sessions. Grading uses the transcript and patch even when the last-message file is absent.
Stand-ins exercise the following assumptions. Live event behaviour remains unverified.

| Assumption | How the driver handles missing or conflicting evidence |
|---|---|
| Terminal ordering and exit codes identify completion. | Grading requires exit zero, a terminal `turn.completed`, and concrete work after `turn.started`. Any `turn.failed` survives later completion and yields service or unattributed `error`. Missing completion, conflicting exits and a bare signal yield unattributed `error` unless a diagnostic establishes the cause. |
| Quota, retry and refusal wording and origin identify a service fault or recovery. | An unresolved CLI service diagnostic yields `error`, including on exit zero. An unfamiliar CLI error or a recognizable refusal reported only by the model yields unattributed `error` and bars interpretation. The model's free text is checked for refusal wording. A plan or a lack of work at the limit also gives unattributed `error`. A deadline fail requires a still-open command, file change or model message. |
| Tool payloads identify items and expose the command, paths and working directory needed to resolve reads. | An unknown tool, unusable ID, missing command, unresolved relative read or malformed stream yields `unauditable` and bars interpretation. Observed outside reads take precedence. The audit covers only events the CLI emits. |

The first registered rounds can expose live setup failures, but successful rounds cannot independently validate grading, failure attribution or audit completeness.

### Private transcript audit

Every task ends with “Use this working directory as your only source of project
information. Run local checks here. Do not consult repository history or external sources.”
Each agent gets a Git-free export. A private filesystem mount is unavailable.
The audit sees commands and their outputs, not file opens made inside a program the agent ran.

Scan each admitted trial while its export and surviving symlinks still exist, including
partial rounds. Inspect command text and working directory, tool names and arguments,
and output evidence of reads, searches, listings, copies, imports or inspection.
Expand home, available variables, relative paths, case aliases and visible symlinks.
A banner merely naming a path is insufficient. Flag the main checkout, other worktrees,
site-packages/arci or dist-packages/arci anywhere, Git directories and object/history
access, sibling exports, transcripts, grader outputs and other external project reads.
Network, web, MCP and session-history lookups also qualify. The trial's export and
registered runtime loads are allowed. Treat an explicit external file or directory
operand outside those roots conservatively as a potential source of project information.
Count documented denied attempts separately.
Record clean, outside_read or unauditable, event IDs, relative export root and the
SHA-256 of the private JSONL bytes. An observed outside read takes precedence.
Otherwise an absent, empty or unparseable stream is unauditable. Keep the stderr and last message private as well. A clean scan only
describes the available events. Preserve the original grades and CSV membership.

## Rule and stops

Use ARCI 2.4.1 verdict with codex-effort/rule.yaml. Alpha is 1/20. The margin is 1/10.
The stakes are 1/4 and 1/2. Each crossing threshold is 40. The only looks are complete
round ends. Each round includes both arms on all ten tickets. At most 16 rounds,
160 pairs or 320 invocations. Stop at the first PASS, BLOCK or ERROR. At the cap a
non-crossing is INCONCLUSIVE. Never extend the cap or replace a failed or missing trial.

For rounds 1, 3, 5 and so on, sort tickets by SHA-256 of UTF-8 ticket ID, colon and
decimal round number, with ID breaking a tie. The first five run baseline first.
Reverse each pair in the following even round. Each ticket has eight starts per arm
across 16 rounds. Each round has five starts per arm. Save the schedule before dispatch.
Use up to four pairs at once, four by default. Finish and record one arm before starting
its partner. Never carry a pair or a look across a round boundary.

Allow two errored pairs, the default rounded up from one percent of 160. This allows
an isolated service fault without discarding the run. Either arm's error counts once
per pair. Up to tolerance it counts as a loss for PASS and a win for BLOCK. When a third
distinct pair errors, stop admission immediately with ERROR. Three consecutive errored
trials also stop admission with ERROR, even if they belong to only two pairs. Consecutive
means the coordinator's recorded completion order across workers. Record the reasons.

Stop admitting work after eight hours of collection. Finish admitted trials and record
them. This can run past eight hours by one invocation and grading. Preserve partial
round records. Only complete rounds enter the CSVs. State the reason for any early
stop. An earlier INCONCLUSIVE prefix cannot answer the question after an error stop.
A clock stop without a crossing is INCONCLUSIVE. If no round completed, say so.

The projections below assume the full cap is available. At four busy workers the pooled
allowance is six minutes per invocation including grading. When durations are equal,
ten pairs need three waves per round and the allowance is five minutes. Neither is
a measured runtime. The service can refuse more work before either limit.

## Planner projections

Exact absorbing calculation from ARCI 2.4.1 suite_stats, reproduced by plan_size.py.
All ten tickets have the same stated pass rates. Arms, tickets and rounds are independent
in these models. Rates stay fixed. There are no errors. The entries are probabilities
of the first crossing by round 16, or of neither crossing. Displayed values are rounded.

| Margin | All-tie round | xhigh / high | PASS | BLOCK | INCONCLUSIVE |
|---|---:|---|---:|---:|---:|
| 1/20 | 17 | 90% / 90% | .12358 | .00005 | .87637 |
| 1/20 | 17 | 75% / 75% | .06692 | .00074 | .93234 |
| 1/20 | 17 | 90% / 70% | .00000 | .77681 | .22319 |
| 1/10 | 8 | 90% / 90% | .58606 | .00000 | .41394 |
| 1/10 | 8 | 75% / 75% | .27707 | .00004 | .72289 |
| 1/10 | 8 | 90% / 70% | .00004 | .36838 | .63158 |
| 3/20 | 6 | 90% / 90% | .94050 | .00000 | .05950 |
| 3/20 | 6 | 75% / 75% | .64088 | .00000 | .35911 |
| 3/20 | 6 | 90% / 70% | .00072 | .07598 | .92329 |

Five points needs 170 all-tie pairs. ARCI refuses that rule at 160 pairs. Its row gives
the mathematical projection only. Fifteen points would accept a shortfall approaching
15 fixes per 100 and has only a 7.6% chance to block the modelled 20-point drop.
At the registered ten-point margin the consultant reproduced 0.586057 PASS at
90% / 90% and 0.631580 INCONCLUSIVE at 90% / 70%. The margin allows one additional
failed fix per ten jobs. None of these choices has a
good chance of deciding in all three scenarios. An inconclusive run is expected often.

## Reading the result

PASS supports a mean difference above minus ten percentage points on these ten tickets.
This includes a tie or a high lead. BLOCK supports a difference below minus ten points.
At the exact boundary both directional null hypotheses hold. INCONCLUSIVE decides
neither direction. ERROR gives no statistical conclusion.

The conditional assumptions concern fresh, independent pairs across tickets and rounds,
a stable law for each ticket, and no arm-order effect. Within a pair the arms may depend
on each other. The registration must precede both arms. Pairing, grading and error labels
must follow it. Under these assumptions each directional error has probability at most
2.5%. ARCI cannot check shared responses, prior knowledge or a hosted model change.

Read a verdict as an answer only when all of the following hold.

1. The final registration and digest list were public before any live call, including
   smoke calls. The full stand-in suite passed with `RUN5_CHECK_CONFINEMENT=1` in the
   owner's terminal outside any sandbox before sealing. The published-tip start check
   then passed.
2. Each admitted trial has one start and one matching record. Confirm its ticket, arm,
   order, patch digest and grading evidence. Account for every attempted pair.
3. The registered rule and both CSVs reproduce the saved decision. Complete-round
   records match the CSV rows. Report any service or time stop and partial round.
4. Both arms have zero outside_read trials, zero unauditable trials and zero
   unattributed terminations across all admitted work. At most two pairs errored.
   No three-error stop, leakage or other protocol breach occurred.
   If a condition fails, publish what happened and leave the question open.

## One start and publication

The driver checks the current origin v2/phase0 tip, checkout, registration, manifest and
all listed bytes. It repeats the published-file check after the stand-in tests. Before
the real executable is queried it atomically creates the permanent shared directory
`/Users/ajay/Developer/.arci-worktrees/codex-effort.started` and the local
marker `codex-effort/codex-effort.started`. Campaign output goes in `codex-effort/runs-codex-effort`. Every checkout uses this same absolute shared marker. The separate
`--check-start` preflight consumes neither marker. No second
start, no live smoke, no replacement ticket. The start runs under caffeinate.

For every outcome publish the final registration, push time and commit, start evidence,
versions, schedule, trial records, both complete-round CSVs when available, round
decisions and recomputation. Include the stopping reason, partial work, diff digests,
reviewed patches and grader outputs. Report deviations, all failed checks, pass/fail/error
counts by arm and ticket, all three audit counts by arm and ticket, denied attempts,
distinct affected pairs, and seconds per trial. Publish counts of all agent time limits
and genuine deadline misses by arm. This result answers a deadline-bound worker decision only. Count elapsed times per arm
in four bands. The cut points in seconds are 120, 300 and 1,200. A cut point starts the
next band. Keep raw transcripts private and disclose any redactions from published evidence.

The finding covers these public tickets on one machine during this campaign. It gives
no general verdict about the vendor's model or other work. The check measures test
outcomes. Seconds describe this run. It measures no resource savings or general speedup.
Some later parent trees already include earlier repairs. A model can know a public fix.

## Predictions recorded before the start

The consultant recorded INCONCLUSIVE before collection.

- The consultant (Astra): INCONCLUSIVE.
- The orchestrator (Claude): INCONCLUSIVE.
- The maintainer: none supplied before registration.

Both were stated before any trial. No live trial of any kind preceded this registration.

Checks by the orchestrator before sealing, on 21 Nov 2026: the whole stand-in suite was
run outside any sandbox with the confinement check on (131 passed). On the first such run
14 tests failed: the confined grader could not start, because its profile did not allow
reading the root directory entry. The builders work inside a sandbox and could not have
seen this. One line of `codex-effort/grade.py` was changed to allow it; reads of the
project's other checkouts and writes outside the scratch folder were confirmed to stay
refused; the digest list was refreshed after the change.
