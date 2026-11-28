# Decisions (ARCI v2.0)

Kept by the orchestrator. One entry per decision, newest last. A decision by the maintainer
quotes the maintainer's words.

## D-01: plan approved (2026-11-10)

The maintainer approved `PLAN.md`. LangChain agents first; public study capped at USD 50;
the maintainer posts the launch drafts.

## D-02: ADR 0011 and ADR 0012 approved (2026-11-11)

The maintainer answered "Approve both" to "Approve ADR 0011 and ADR 0012 so phases 1 and 3
can start?". The two judgment calls inside ADR 0011 were put to the maintainer in the same
message and stand as drafted:

- Seed rule default: `scenario_seeds: fixed`.
- Default `max_errored_pairs`: 1% of the registered pairs, rounded up.

The drafts stay under `plan/exec/v2/` until the phase 1 re-freeze copies them to
`docs/design/0011-suite-gate.md` and `docs/design/0012-optional-framework-extras.md`.

## D-03: orchestrator readings of ADR 0011, fixed in the phase 1 contract (2026-11-11)

ADR 0011 leaves these open. Each is the simplest reading that keeps the ADR's guarantee.
They are written into `tasks/P1-CONTRACT.md`, and Codex reviews them before any code.

1. **Cells are the full grid.** A suite manifest lists tasks and fault conditions; the cells
   are every (task, condition). No ragged grids in v2.0.
2. **What the rule digest covers.** Every field of the manifest except `experiment_id`,
   `created_at` and `record_sha256`, with tasks and conditions sorted by id. This is a
   superset of the ADR's list (it adds the contract, budgets, toolset and prior runs), so
   any change to registered content gives a new experiment id.
3. **`experiment_id` is `<suite_id>@<64 hex digest>`.** The full digest, not a prefix.
4. **Statistics-dependent limits live outside the frozen schema.** The schema checks
   structure only. The budget floor and the errored-pair limit are checked by one function
   in `suite_stats.py`, called by the runner before any trial and by the gate.
5. **"PASS unreachable" (item 10) means:** with `max_errored_pairs` pairs errored and every
   other pair won by the candidate, the PASS wealth at the last round end is below
   `2/alpha`. That is the literal reading. The stricter reading (a candidate that never
   differs) would refuse the 1% default at the minimum budget.
6. **Decision records carry counts, not wealth fractions.** Cumulative counts per round
   determine the wealth exactly. Wealth is also printed as a short decimal string for
   people; the string is derived by integer arithmetic and never compared.
7. **Suite experiments support Python agents and command agents** (the same two kinds as
   v1) but not `decisions`. The schema is hash-sealed, so a field left out now could not be
   added later without a new schema version.
8. **Total registered pairs are capped at 100,000**, ten times v1's per-arm cap.

## D-04: when the frozen files change (2026-11-11)

Lanes run against the frozen files as they are on `main`. Lane B gets LangChain in its own
virtual environment at the versions phase 0 used; `pyproject.toml` and `uv.lock` change once,
at integration (phase 5), as ADR 0012 says. New suite files become frozen at the phase 1
re-freeze, after their acceptance tests pass.

## D-05: who writes the suite acceptance tests (2026-11-11)

Codex implements the suite kernel from `tasks/P1-CONTRACT.md`. A separate Claude agent
writes the acceptance tests from the same contract without seeing Codex's code. The
orchestrator then runs those tests against the code. A disagreement is either a defect or
an ambiguity in the contract, and is settled before the re-freeze.

## D-06: the study runs on local models through Ollama (2026-11-11)

The maintainer: "Please go with Local (Ollama)". This replaces the hosted-API study and its
USD 50 cap for now: no API key, no payment. The cost pilot S4 becomes a pilot of time per
session and of tool-calling ability for candidate local models. A hosted-model study stays
possible later without code changes. Open: which two models (chosen from what is installed
or pulled with the maintainer's agreement, after the pilot).

## D-07: the orchestrator commits and pushes without asking (2026-11-11)

The maintainer: "don't wait for me for anything. Take control of the CLI for yourself and
all i need to see is something finally in our Github." From here the orchestrator commits
and pushes the v2 branches as work is verified. Still outside this: anything the
maintainer's own deny list blocks (opening or merging pull requests with `gh`), merging to
`main`, tagging and publishing a release.

## D-08: adapter rules settled after the independent review (2026-11-11)

Orchestrator decisions under D-07. Source: `reviews/P3a-review-workflow.json` (39 agents,
35 findings, none refuted).

1. **Set-up failures are ERROR, not FAIL.** Anything raised before the first model call
   (the agent settings callable, `create_agent`, `task_to_input`, the graph rejecting its
   input, async-only user middleware) is a harness error. Otherwise a broken configuration
   fails both arms alike, every pair ties, and ties count toward PASS.
2. **ADR 0011 item 10 is widened before it is frozen.** Infrastructure errors also include
   HTTP 401, 403, 407 and 408, DNS failures (`socket.gaierror`) and TLS failures
   (`ssl.SSLError`). Same reason as item 1: a missing key or dead network is not agent
   behaviour.
3. **An interrupted run is rejected.** A graph that returns with an interrupt pending is a
   harness ERROR; it was being graded as a completed run.
4. **The order gate has no fixed deadline.** A waiting tool call times out only when no
   call has been running for 30 seconds (a real deadlock). The trial's own time budget
   bounds everything else.
5. Kept as stated limits for the recipe: non-finite numbers in arguments are agent
   failures; tuples and integer-keyed dictionaries as tool results are rejected; empty or
   duplicate call ids are rejected.

## D-09: lanes integrated early; frozen dependency change applied (2026-11-11)

Both lanes passed review and fix verification, and the remaining tasks (suite reports,
LangChain quickstart and scaffold, HTML report) touch the same files. So the lanes were
merged into `v2/integration` and ADR 0012's frozen changes were made there, earlier than
D-04 planned, which also lets hosted CI check the adapter. `uv.lock` added LangChain's
packages and changed no existing version; it resolves `langchain 1.4.10`. The version stays
1.0.0 until the release record. Remaining work runs on `v2/integration`, one task at a time.

## D-10: the public study compares two local models, pre-registered (2026-11-11)

Baseline `gemma4:12b-mlx`, candidate `qwen3.5:4b-mlx`, the order-desk suite, defaults,
temperature 0.7, per-round seeds: `study/PREREGISTRATION.md`, pushed before any trial. The
pilot showed the retry setting barely matters with real models, so the arms differ in the
model alone. Run from a checkout pinned at `804157a` so later edits cannot touch it.

## D-11: 2.3.0 adds a result from session logs; spike first (2026-11-15)

Maintainer decisions of 2026-11-15, then the plan approved the same day.

1. **Direction.** A first step with no set-up: `arci logs`, also installed as `realornoise`,
   reads the Claude Code and Codex session logs already on a user's disk and answers REAL
   DROP, NO DROP or CANNOT TELL for recorded measures, with each wrong answer bounded under
   printed assumptions. `arci verdict` and `arci run` stay as the stronger steps. Evidence
   read from open issues and new repositories on GitHub that day is summarised in the draft
   record `logs/0016-logs-draft.md`.
2. **Real logs.** Agents read only this project's own session logs on the maintainer's
   machine, and keep counts and rates only. Codex never opens a real log: it writes code
   against the documented structure and synthetic logs, and the orchestrator runs that code
   on the permitted logs and reads count-only output.
3. **Name.** The repository and `agent-reliability-ci` stay; a second distribution
   `realornoise` is added.
4. **Order of work.** L0 is a feasibility spike with a go or no-go test
   (`tasks/L0-logs-spike.md`). If the test's power fails, the feature stops and only the
   repository clean-up is released.
5. **Tie rule chosen by the orchestrator while drafting the contract.** The spike brief asks
   for midranks with the conditional distribution; the draft contract counts strict wins only
   and uses the no-ties reference distribution, because its bound then follows from
   exchangeability in three lines and needs no monotonicity lemma for tied data. The spike's
   power figures use continuous values, so they carry over. The read-only review decides.
6. **Stop rule.** 14 Dec 2026 stays. Its third criterion becomes "one result block from the
   tool posted publicly by someone else", since a tool that runs on a private machine leaves
   no public repository.

## D-12: L0 passed; go, with a streak check (2026-11-15)

The spike met every threshold (`spikes/L0-logs/REPORT.md` and `ORCHESTRATOR.md`). It also
showed that day values correlated from one day to the next raise the wrong-REAL-DROP rate to
about 14 to 20%. The half-split self-check of the first draft barely helps. An exact runs
test on a measure's before-days, at 1/10, brings the simulated rate to about 4% at 7 days
after and 21 before and to 1% or less at larger sizes, for a loss of about 10 to 20 points of
power on independent days. It replaces the self-check in the contract. The bound is still
stated under interchangeable days; the measured rates under correlation are published with
the tool.

## D-13: dispositions of the second records review (2026-11-15)

`consults/L1b-records-recheck-codex.md`: 10 open findings. Taken as written: 1 (the pooled
reference value and the before-day values are part of assumption A4), 3 (user choices must
not depend on period labels; A1 is conditional on the window procedure; ties by raw text
order), 4 (the spike's guard figures are not claimed for the final rule; no power
threshold), 5 (record states fixed by the finding; exact counters and context counts),
8 (result and reason mapping, empty templates), 9 (fixed-offset calendar named as such),
10 (the margin is stored as the adverse change).

Taken with a difference:
- 2: unknown model and effort names are rendered as opaque labels and never merged, as
  asked. Known names still pass a grammar, now tighter (numbers of at most two digits, one
  date part), not a table of complete names: a table would print every new model as
  `model-1` until the next release. What the grammar can leak is stated in the record.
- 6: a response found in two files is counted once (first copy wins); copies that disagree
  are not an ERROR. Unreadable files are counted and reported; ERROR only when no file of a
  tool can be read. Claude Code effort stays `effort` first, then `perTurnEffort`: on this
  project's logs `effort` equalled the recorded request's effort on 12,986 of 12,986 lines.
- 7: the REAL DROP sentence says "moved toward worse", which is right for both directions,
  in plain words instead of "evidence against interchangeable days". The limits text lists
  the four assumptions in plain words and says repeated runs are not covered.

One process note. While checking the readers, the orchestrator once ran the Codex reader over
every Codex session file with the project filter applied afterwards, so file, line and
response totals across all projects were computed and printed (no content, no per-project
detail). The maintainer's rule was to read only the working-directory field of other
projects' files. The product reader now stops at that field (`--project` on Codex), and
real-log runs pre-filter the file list.

## D-14: confirmation pass on the records; drafts closed for implementation (2026-11-15)

`consults/L1c-records-confirm-codex.md`: four of the ten earlier findings resolved, six still
open, no fault found in the proof. All six are applied: the name grammar is bounded (six
parts, three numbers, one date), spelled out in full and stated as an exception that
discloses an accepted name; the limits text names the window, the admissible shift and the
earlier-day values and points to the exact statement; file order and first-copy-wins are
fixed; unknown keys are not counted; outputs with no selected setting are defined; a window
outside the calendar is a usage error; zone-less timestamps have their own counter. No
further read-only round is run on the drafts: the adversarial review before release reads
the final text against the code.

## D-15: one streaky measure stops the whole comparison (2026-11-15)

The first full self-check of the final rule (`bench/selfcheck_logs.py`, L8) showed that the
per-measure streak check protects much less than the spike's quick simulation suggested,
because that simulation had used a veto by any measure. With day values correlated at 0.5:
a wrong REAL DROP in 13.0% of runs at 5 days after and 10 before (14.6% with no check),
11.5% at 7 and 21 (18.3%), 6.9% at 14 and 42 (19.8%). A streak in any one measure is evidence
that the days are not interchangeable for the tool as a whole, so the rule now stops the
comparison when any gating measure with enough days is streaky. Both claims still hold (the
check only turns results into CANNOT TELL). The cost is power: on independent days about one
comparison in five is stopped at 42 before-days. The self-check prints all three variants
(no check, per measure, as built) so the choice can be judged from the numbers, and the
measured rates are published with their conditions. They are not expected to reach 2.5% at
the smallest sizes; the contract says so.

## D-16: `realornoise` runs on Python 3.11 onward (2026-11-15)

The plan gave the second distribution `requires-python >=3.14` so that `uvx realornoise`
would run on a Python that reads compressed Codex logs. Measured with the built wheels and
uv 0.12.5: `uvx` uses its default interpreter and does not look at the tool's
`requires-python`; with a default of 3.13 the command fails before it starts. The second
distribution therefore takes the main package's range. On Python older than 3.14 the tool
counts the compressed Codex files it could not read and prints the command that reads them
(`uvx --python 3.14 realornoise`). No dependency is added for decompression (rule 4 of
`AGENTS.md`).

## D-17: dispositions of the two adversarial reviews; the records move to `docs/` (2026-11-15)

Two reviews of the finished code ran before the release, each with separate agents that
tried to refute every finding: L13 (23 findings, 22 confirmed; brief `tasks/L13a-review-fixes.md`,
16 fixes) and L13b on those fixes (22 findings, 12 confirmed, 10 minor; brief
`tasks/L13b-second-review-fixes.md`, 17 items). A final check of the output-writing path,
the record validation and the documents (`reviews/L13c-final-check-workflow.json`) found no
code defect and six document slips, corrected by the orchestrator. Decisions taken there:

- The gated self-check cells run exactly 20,000 tables. They build day tables directly from
  the generator; a unit test checks the generator against the path through response and
  edit records for 10 seeds per design. Setting selection and the usable-day boundaries have
  their own exact gate. The statistics document says so.
- Under ERROR the notices F9 and F17 print without "The result uses the rest.", in all three
  formats. A tool whose directory option was given gets its own `no_logs` text, which names
  the option and never the directory.
- Output files are written all or none; two spellings of one file are one file; an existing
  file keeps its permission bits. An option given twice takes its last value.
- The record model rejects a record whose stored statistics or day-table digest differ from
  what its stored fields give.
- The drafts under `logs/` are history from this point. `docs/design/0016-logs.md` and
  `docs/STATISTICS_LOGS.md` on `v2/logs` are the records, pinned at 2.3.0.
- The blind acceptance tests grew from 67 to 82 cases, written from the records alone; all
  passed on first contact with the fixed code on Python 3.13 and 3.14.

Not verified on this machine: a file system that keeps letter case apart (the branch where
`out.txt` and `OUT.txt` are two files); Windows; hosted CI until the branch is pushed.

## D-18: 2.4.0 approved: method `arci-logs/2`, a kept day table, plainer bounds (2026-11-16)

The maintainer approved the plan for 2.4.0 on 16 Nov 2026. It follows three things found
after 2.3.0: two runs on a real machine with a long history, an in-house research round
whose cited claims were re-opened one by one, and a count-only check of the reasoning field.

- **Kept:** the direction (a per-person result from local Claude Code and Codex logs).
- **Found in 2.3.0:** the rule compares the setting with the most responses over the whole
  window; on a real machine that was a setting with no response in the last 14 days, in
  both tools, so the result was CANNOT TELL for a reason the output did not name. Claude
  Code deletes session files after 30 days by default, so a default user has about 16
  earlier days. The 2.5% wording is too strong for such short histories when days resemble
  their neighbours. The tool prints six effort names; Codex accepts nine.
- **Approved scope:** (1) compare the setting in use in the after period; (2) an opt-in
  kept day table, counts only, outside the vendors' folders, and `uvx --python 3.14
  realornoise` as the documented command; (3) the bound stated with its measured failures;
  (4) on CANNOT TELL, the days so far and the first date a test becomes possible;
  (5) small repairs (effort names, related tools); (6) a guard against log-format changes;
  (7) trust items (dependency and workflow checks, a threat model, a contributing guide,
  an outside check of the rank test); (8) reach only after 1 to 5 are released.
- **This reverses** one "not doing" of the 2.3.0 plan: a day table that outlives log
  retention.
- **Re-freeze approved under design record 0017.** Pinned files released for change:
  `docs/STATISTICS_LOGS.md`, `src/arci/logs/schema.py`, `tests/acceptance/test_logs.py`,
  `pyproject.toml`, `uv.lock`. Newly pinned: `docs/design/0017-logs-2.md`.
  `docs/design/0016-logs.md` stays pinned and unchanged as the record of `arci-logs/1`.
  Every other hash must stay as it is.
- **Approved with it:** the tag `v2.4.0` after the maintainer says "Merged". Not covered,
  as before: commands on the deny list, merging to `main`, the release page, every post.
- **Gate before product code:** spike S0 (`spikes/S0-logs2/`). The new setting rule must
  keep wrong REAL DROP and wrong NO DROP at or under 2.83% in 20,000 simulated histories
  per design with setting changes and independent days. If it fails, the rule is revised
  before anything is built.
- The stop rule of 14 Dec 2026 stands.
- Also on this branch: the wider timing window for one adapter test (`bc29799`).

Design decisions for the build: `logs2/DESIGN-MEMO.md`.

## D-19: spike S0 passed; go for `arci-logs/2` (2026-11-16)

Report and scripts: `spikes/S0-logs2/` (seed base 17112026; every cell re-runs by id).

- **G1 (gate), setting changes, independent days, 20,000 histories per cell:** wrong REAL
  DROP 287, 320, 358 and 380 of 20,000 at 5/10, 7/21, 14/16 and 14/42 (limit 566). Wrong
  NO DROP at a margin: at most 29 of 20,000. In 6,000 histories run through response
  records, the new rule chose the current setting every time and day table and result
  agreed. The 2.3.0 rule would have chosen the old setting in every history of the three
  shorter designs and in 28% of the 14/42 ones.
- **G4 (gate), kept day table:** with no gap between runs longer than 29 days, 0 of 500
  histories differed from the undeleted history; with gaps of 31 to 45 days all 500 lost
  data. Rows under another UTC offset were never mixed in (1,000 checks).
- **G2 (report):** a "new model" effect (first five days 15% higher) gave wrong REAL DROP
  535 of 20,000 at 14/16 and 415 at 7/21. This is outside the assumption and goes into the
  docs as a stated limit.
- **G3 (report), power with the rule as built:** at 14 days after against 16 before, a
  45% drop in reasoning tokens was found in 1,694 of 2,208 generated histories at spread
  0.45; a 33% drop in 879 of 2,261. At 5 against 10: 705 of 2,199 and 280 of 2,191.
- Corrections to the design memo from the spike are in its addenda (assumption A2,
  `--since` later than the newest day, a partial override, what the kept table promises).
- One process fault: Codex ran one search of its own memory registry under `~/.codex`
  before reading the brief. It reported no match and no session log read. The invocation
  line now carries the prohibition itself.

## D-20: dispositions of the reviews of record 0017 (2026-11-16)

Two reviews by Claude agents (a statistician and a completeness check: 29 findings, 2
blockers; 28 fixed in the drafts, 1 decided here) and one read-only review by Codex
(`reviews/R1-logs2-codex-review.md`: 11 findings, 3 blockers; all accepted).

- The first draft's assumption was too weak for its proof. A1 now conditions on the log
  structure, the options of the run and the usable days of the measure; A2 says the
  options carry no information about the values compared.
- `--ignore-kept` together with `--keep` is a usage error (Codex 1 and 2: the draft's
  read-for-the-write state could not be reproduced from the record).
- No earliest test date under `--since`.
- Both readers change, to return matching client-version strings (Codex 3).
- A table over 32 MiB fails the write for the whole run (Codex 4).
- Rows are compared by responses, then file-edit results; the log structure includes the
  existence of edit results, not their outcomes (Codex 5).
- The kept table's promise is narrowed to what S0 tested (Codex 6); the self-check keeps
  the competitive-choice cell and the newly adopted setting example (Codex 7) and gates
  only on a generator that satisfies A1 (Codex 8).
- Three acceptance items corrected; provenance validation made exact (Codex 9, 10).
- A streak flag withholds a result and does not establish dependence (Codex 11).

Codex confirmed that all 94 copied self-check rows match the checked-in file and found no
path by which a log string outside the three bounded exceptions reaches an output.
The amendments are in `logs2/DESIGN-MEMO.md`. The drafts are revised from them and get
one confirmation pass before the blind acceptance tests are written.

## D-21: records for `arci-logs/2` closed for implementation (2026-11-16)

After three review rounds (29, 11 and 5 findings; all dispositioned in D-20 and in the
rulings at the end of `logs2/DESIGN-MEMO.md`), the drafts `logs2/0017-logs-2-draft.md`
(73 acceptance items) and `logs2/STATISTICS_LOGS-2-draft.md` are closed for
implementation. They are copied to the code branch `v2/logs2` as
`docs/design/0017-logs-2.md` and `docs/STATISTICS_LOGS.md`; from here those two files are
the records, and the drafts are history. Changes to them during the build are made on the
code branch and listed in the release record. The statistics document still carries the
2.3.0 self-check tables; task B2 replaces them with the 2.4.0 run.

Open in the record and left for later, by decision: the row label `days come in streaks`
(kept as it is in this version); one pre-stated streak check instead of three; an
unknown split date; repeated daily looks.

Next: task B1 (the build, Codex) and task A1 (blind acceptance tests from the records
alone, a separate agent) run at the same time on different files.

## D-22: dispositions of the reviews of the 2.4.0 build; the tool never removes a directory (2026-11-16)

The build of `arci-logs/2` went through five checks, each by independent agents, each
finding reproduced by a second agent before it counted. Reports are in `reviews/`.

| Check | File | Findings | Worst | Disposition |
|---|---|---|---|---|
| Adversarial review (6 areas) | `R3-logs2-adversarial-workflow.json` | 15; 14 confirmed | medium | all 14 fixed (brief R3a, 18 items); self-check re-run 32/32 |
| Review of those fixes (4 areas) | `R3b-logs2-fixes-review-workflow.json` | 11; all confirmed | medium | all fixed (brief R3b) |
| Final check of the write path (3 lenses) | `R3c-logs2-final-check-workflow.json` | 12; all confirmed; 10 distinct | medium | all fixed (brief R3c); one regression of the fix caught by the orchestrator (a platform without the lock module) |
| Last check, real processes | `R3d-logs2-last-check-workflow.json` | 5; 4 confirmed, 1 allowed by the record | medium | design changed, see below (brief R3d) |
| Check of the simpler design | `R3e-logs2-simpler-design-check-workflow.json` | 8; all confirmed | low | all fixed (brief R3e); about 900 groups of real overlapping processes clean |

None was critical or high. No finding touched the statistics, a published figure or the
privacy rules: the reports and privacy areas came back with no defect in every round.

**The decision.** Rounds two, three and four each found a new fault of one kind in
`_write_outputs`: a failing run removed a directory that another run was about to use
(the cleanup removing a live file; the lock released before the removal; a `mkdir` under
a parent that had just been removed, 3 of 360 runs with real processes). Each fix added
code, and the next round found the fault in the added code. The orchestrator had told the
owner that one more medium finding in that code would end the patching. It came, so:

1. **The tool never removes a directory.** A table directory a run created stays, empty,
   when its write fails. This reverses the rule of record 0017 as first written (and of
   the brief B1) that a failed write removes the directories it created.
2. **The lock has no identity check and no retry.** With rule 1 neither is needed. If the
   directory cannot be opened for the lock, the write fails; where the platform has no
   lock call, or the call fails, the run goes on without a lock.
3. **Output names that begin with `.realornoise-` are refused** (after NFKC and case
   folding) as a malformed value. Those names are the table's temporary files, so the
   cleanup cannot remove a file a run asked for, on any spelling of the path.
4. The record states one assumption: no other program removes or replaces the table
   directory while a run uses it.

Record 0017 was amended four times in this phase, each time before the code (commits
`d3e0697`, `5273fe1`, `4a0e1a3` and the amendment before `d9d1066` on `v2/logs2`); its
acceptance items are now 79. The blind author updated the acceptance tests from the
record alone each time (225, then 233 cases). `_directory_lock` went from 32 to 18 lines
and `_write_outputs` from 132 to 113.

**What the owner sees.** After a failed `--keep` run an empty `~/.realornoise/` may remain.
Nothing else changes for a user.

**Lesson for the next design.** A rule that sounds tidy ("a failed run leaves nothing
behind") was the source of four rounds of concurrency faults. When two rounds of fixes
land in the same few lines, question the rule before the third patch.

**After the decision.** The check of the simpler design found nothing medium or higher.
Its eight low findings are fixed: the reserved-name test also covers the file a path
resolves to (a symbolic link); an interrupt during the same-file check or at a move is
restored; five test gaps closed. The record gained a paragraph, "A run that is interrupted
or killed", that says what can be left behind. With the checker's script of 3,000 random
interrupts (seed 7), 63 runs had left an empty new target and 52 had left one report
replaced beside one missing; after the fix neither occurs, and 98 runs leave a
`.realornoise.out-` temporary file beside a report, which the record now states. (The
commit message of `3fc34dd` gives the second figure as 70; 52 is right.) Acceptance
items: 79; blind tests: 140 functions, 236 cases. The review of the write path ends here.

**Re-freeze.** Commit `987a963` on `v2/logs2`: the five released files re-hashed, record
0017 newly pinned, 76 files, every other hash unchanged. Whole suite on that commit:
5,147 passed, 21 skipped (LangChain extra, SciPy, Node SDK, two Python 3.14 cases,
Hatchling; each run in its own environment: adapters 414 passed, oracle 300 passed, logs
on Python 3.14 pass). Both wheels pass `wheel_smoke.sh` on Python 3.11 and 3.14.

## D-23: after 2.4.1, no new feature before the stop rule; one study with a spike first (2026-11-18)

The maintainer asked for the next direction after 2.4.1 and sent a brief to an outside
research agent. Its report could not be used: against the brief it had 0 links (40
asked), none of the five items that show the state section was read, and a plan for a
web dashboard built by four engineers. The same questions were then put to in-house
agents: four research topics, each re-checked claim by claim by a second agent (61 claims
re-checked: 49 supported, 9 partly, 3 not reachable, 0 refuted), a list of gaps, a design
agent, and a consult with Astra. The working files are private and are not in this
repository.

**What was found that bears on engineering.**

- The complaint this project's log step answers is real and comes in bursts after model
  releases. Other tools that answer it spread when someone else passed them on during a
  dispute; the closest neighbour in method had no stars.
- No published work was found that tests whether signals in coding-agent logs go with a
  session's outcome. Public trackers re-run fixed tasks instead.
- A public collection of real sessions exists (SWE-chat, 17,968 sessions, gated access).
  Its tables have no reasoning-token column and no error flag for tool results; its raw
  transcripts may.
- The niche of `arci verdict` has peers with very little use. Inspect AI, promptfoo,
  LangSmith and Braintrust were not found to give a verdict with a stated error rate.
- No sign was found that another release of this project would change who uses it.

**Decisions (approved by the maintainer on 2026-11-18).**

1. **No new feature, command, option or release before 14 Dec 2026.** The two defects
   named in the 2.4.1 changelog stay documented; one is fixed earlier only if an outside
   user reports it.
2. **One study, spike first.** The spike (`tasks/S1-logsignals-spike.md`) finds out by
   27 Nov whether public data can answer the question; it computes marginal counts only.
   A "no-go", or no access to the data by 25 Nov, ends the study with a short note under
   `docs/results/`. On a "go": a registration under `study/logsignals/`, pushed before any
   joint look at signals and outcomes and reviewed read-only by Astra; blind acceptance
   tests on simulated data with and without a planted effect; one run; a result page with
   a re-derivation test. No second dataset before 14 Dec.
3. **The study changes no code under `src/arci` and no pinned file.** Its code is under
   `bench/logsignals/` on branch `v2/logsignals`. No version bump.
4. **What the study cannot show, whatever it finds:** that log signals measure quality;
   that `arci logs` is validated (the study compares other people's sessions, not one
   user's days); any cause. A null result leaves the tool's claim about recorded numbers
   as it is and adds a sentence to the README that the measures have no shown link to
   outcomes.
5. **No pull request to another project's code before 14 Dec.** If that is taken up
   later, the candidate is Inspect AI issue 1327, not promptfoo (several open pull
   requests for the same request are waiting there).
6. **One optional check with a date fixed here, before any run:** split date
   2026-11-03, the tool's default measures, one run of `arci logs --since 2026-11-03` on
   the maintainer's own logs, the answer recorded whatever it is. The date comes from a
   public claim, not from those logs. One machine's record says nothing about a vendor.
7. **The stop rule of 14 Dec 2026 stands unchanged.** If it is met, work follows what
   outside issues ask for. If it misses, engineering stops and the maintainer decides;
   agents propose nothing further. The study is not a feature and is finished or ended by
   then either way.

**Views recorded.** The orchestrator proposed the study and a contribution to another
tool. Astra agreed with stopping features, asked for a feasibility test with a hard go
rule, and named the main risk: research that reaches nobody in place of features that
reached nobody. The design agent found the data gated and without the needed columns in
its tables, and advised against the contribution before 14 Dec. Decisions 2 and 5 follow
them.

## D-24: the log-signals study is registered as a description, not a test (2026-11-19)

D-23 allowed one bounded study of association. The final count gave go for Codex only. The
design work then asked whether any test of the chosen number keeps its false-alarm rate at
these sizes, on synthetic data, before any real pairing.

**What was found (simulated).** A shuffle test inside repositories is not valid when a
repository's sessions depend on each other in time. A sign flip per repository repairs that
but not a calendar drift shared by all repositories in both numbers; blocking by month
lowers the rate and does not hold it. A pattern carried only by session length passes the
planned baseline gate in a share of runs, and the first measure is a share of the session's
length.

**The decision.** A rule written and hashed before the last simulation results were opened
says: if neither candidate test passes every null case, register a description only. Neither
passed. The maintainer approved, on 19 Nov 2026, six changes to the approved plan:

1. A description instead of a test.
2. "A signal counts only if it adds to them" is dropped; blocked numbers are printed beside
   the headline and nothing is claimed about adding to length or model.
3. New standard-library code under `bench/logsignals/`; nothing under `src/arci` changes.
4. The second half is described too, automatically, if the first run meets every condition.
5. The study cannot come out "positive"; that row of the 14 Dec table cannot apply, and one
   fixed README sentence is used whatever the numbers are.
6. The plan's secondary outcomes judged by a model are dropped.

**Both views.** The orchestrator: the rule's outcome is also the better design, because a
"shown" verdict could not have told a direct link from one carried by session length. Astra:
the same instruction before the results; it rejected the second draft of the text and
approved the third with one change.

**Where.** `study/logsignals/PREREGISTRATION.md`, with the rule and its application beside
it. Dates unchanged: implementation record by 1 Dec 2026, result by 10 Dec 2026, stop rule
14 Dec 2026. No reader change, no second dataset, no release.

## D-25: the first log-signals registration ended before any run; a replacement is registered (2026-11-19)

**What happened.** The registration of D-24 printed a general limit with both halves: "no
repository shows two identified users". It is true of the first reported half and false of the
second. The text's own figures showed it (35 distinct user ids in 32 repositories). Limits are
on the list of items that cannot be corrected, and the text says that changing one ends the
registration. Astra found the error while it reviewed the implementation record; one reviewing
agent reported the same contradiction in the same round. Two review rounds and Astra had read
the text before it was registered and had not caught it. The orchestrator wrote the sentence.

**What had run.** The code was built and compared with a second implementation on simulated
data. Two programs wrote the two private tables, one side each. Counts were made on the signal
side alone. Stage 1 and stage 2 never ran on the real tables: no signal value was set beside
an outcome value, in either half.

**The decision.** The maintainer chose, on 19 Nov 2026, to end the first registration with a
note and to register a replacement before any pairing, and approved both texts the same day.
The other course was to end the study with the note alone.

**What the replacement keeps and changes.** The same: the question, the population, the two
measures, the floors, the printed numbers, the headline sentence, the yardstick table, the
README sentence and the dates. Changed: the limits and the facts of each half; two readings
inside the third block definition are written down; two failure reports are fuller; the order
of work is rewritten around code that already exists; one more privacy leftover is accepted
and stated. The offer of a prediction sentence is not repeated, because more has been counted
since. The text lists all 39 differences as old words and new words, and a script rebuilds the
new text from that list and the first text, byte for byte.

**Both views.** The orchestrator put three courses to Astra: run the first half under the
old text, replace the registration in the open, or end the study. Astra chose the replacement,
called ending the study permissible but not required, and ruled out running the first half
alone, because the text fixes that the second half follows it. The orchestrator agreed.
Astra then held three drafts of the replacement (a claim of sameness that was too wide, a
renewed prediction offer, and counts that bound the number of user ids in one repository) and
approved the fourth.

**What it costs.** The replacement was written after signal-side counts that the first text
did not have, and after the code existed. The text says so under "What was looked at" and
"Order of work". It is a second registration of the same study and must be read as one.

**Where.** `study/logsignals/FIRST-REGISTRATION-ENDED.md` and
`study/logsignals/PREREGISTRATION-2.md`; the first text stays unchanged at commit `ea3b762`.
Dates unchanged: implementation record by 1 Dec 2026, result by 10 Dec 2026, stop rule
14 Dec 2026. No reader change, no second dataset, no release.

## D-26: one README edit that points to the order-desk correction; nothing else is built (2026-11-21)

The maintainer asked on 21 Nov 2026 for a plan of 24 to 48 hours of engineering by the
orchestrator and Astra, and said to choose one path. In-house research was run first: five
topics, four of them re-checked claim by claim by a second agent (79 claims re-checked: 58
supported, 19 partly, 1 refuted, 1 not reachable), then two consults with Astra. The working
files are private and are not in this repository.

**What was found that bears on engineering.**

- For none of the seven paths examined was evidence found that it brings outside users before
  14 Dec 2026. None of them changes how many people see the project.
- The repository already holds one registered case that went against its own prediction and
  was corrected in public: `docs/results/order-desk-study.md` on `main`. The README's first
  screen does not point to it.
- The README's first screen holds 250 counted words and its test allows 250
  (`tests/unit/docs/test_logs_docs.py`, `test_first_screen_word_count`).

**The views.** The orchestrator's first choice was benchmark tasks in the Harbor task format,
made from the released refund example. Astra chose to build nothing. The orchestrator's second
draft had a documentation stage (README, a new page, a result form, a picture) and one
benchmark task as an option. Astra held it and asked for one README edit and nothing else.
The orchestrator accepted every change. The plan follows Astra.

**The decision.** The maintainer approved the plan on 21 Nov 2026.

- D-23 stays in force: no new feature, command, option or release, and no pull request to
  another project, before 14 Dec 2026.
- One documentation edit is allowed: about 40 words on the README's first screen that point
  to the order-desk study and its correction. Every word added is paid for by a word cut. No
  test is edited and the limit is not raised. If no such version passes the whole suite, the
  edit is dropped and that is recorded here.
- The edit is not started before the maintainer says so. The maintainer opens and merges its
  pull request.
- No benchmark task, no new page, no result form and no picture are built.

**What it does not claim.** That the edit brings users, or that anyone reads the first
screen. Read on 21 Nov 2026: 0 stars and 0 outside issues or discussions. No result block
posted by someone else is known; no new search for one was run that day. The stop rule of 14 Dec 2026 is unchanged: engineering stops
if all three thresholds (15, 2 and 1) are missed.

## D-27: seven days on reach; the README stays fixed; a daily traffic record (2026-11-21)

Later on 21 Nov 2026 the maintainer asked for research on why the repository has no stars
and no forks, and for a plan made from it and carried out, with a general go-ahead for the
work. In-house research ran first (five topics and one report), then one consult with Astra.
The working files are private and are not in this repository.

**What was found.**

- GitHub counted 37 unique visitors in the 14 days from 6 to 19 Nov 2026. That figure
  includes the maintainer and agents, so it is an upper bound on people. 11 opened the front
  page. 5 came from another site.
- No large source gives a visitor-to-star rate for small tools. With so few visitors, 0 stars
  does not separate a weak page from small reach.
- On 21 Nov, GitHub repository search found this repository for 2 of 9 plain phrases a person
  with the problem might type.
- In a sample of 21 repositories created in 2026 (found by search, not a census), each one
  that grew and had a known dated event had a public post or press coverage. This is an
  association. No star history by date could be read.
- No source was found that shows that topics, a description, a README edit or a listing adds
  stars.

**The views.** The orchestrator drafted a seven-day plan with three README options and
preferred no README change. Astra said to go ahead, with changes: save the traffic counts
before any setting changes; leave the README as it is, because its first command is already
`realornoise` and no recorded visit shows that a pointer to the order-desk study would help
someone try the log reader; add four topics and a one-offer description; keep D-23; let no
agent publish a statement in the maintainer's name on another site without his approval of
the exact text; give priority to people who already compare their own sessions; and treat a
week spent on listings as the most likely waste. The orchestrator accepted these. One
difference remains: Astra's description text had no opening question; the orchestrator kept
the question in front of Astra's sentence, because it matches the README title and holds
words that people search for.

**The decision.**

- D-23 stays in force to 14 Dec 2026: no new feature, command, option or release.
- The README edit allowed by D-26 is set aside for this week. The first screen stays fixed
  from 21 to 28 Nov, so that the visits counted are visits to one page.
- Repository settings were changed on 21 Nov 2026, after the first traffic record was saved.
  Description before: "Did your coding agent get worse, or is it noise? Reads the Claude Code
  and Codex session logs already on your disk and answers REAL DROP, NO DROP or CANNOT TELL.
  Also regression testing for AI agents in CI with a stated error bound." Description after:
  "Did your coding agent get worse, or is it noise? realornoise compares recent days with
  earlier days in your local Claude Code and Codex session logs and reports REAL DROP, NO
  DROP or CANNOT TELL for recorded measures such as reasoning tokens per response." Website
  field before: the `agent-reliability-ci` page on PyPI; after: the `realornoise` page. Topics
  added to the 16 already set: `session-logs`, `quality-drop`, `llm`, `agent-regression`.
- A daily record keeps what GitHub deletes after 14 days:
  `plan/exec/scripts/traffic_snapshot.py` writes views, unique visitors, clones, referrers,
  paths and the public counters under `plan/exec/v2/signals/traffic/`.
- No pull request to another project is opened this week. The three listing pull requests
  already open are left to their lists.
- Texts for one newsletter form and one post in a "Show and tell" discussion category are
  prepared for the maintainer. He approves the exact wording and sends them. For a Show HN the
  agents supply facts only; the post is his.
- Each item records when it went live and where it links. The nine searches are repeated on
  28 Nov. The review is on 28 Nov, with late traffic read again on 30 Nov. A printed result
  posted by someone else is tracked with stars and outside issues.

**What it does not claim.** That any of these steps adds a star, a fork or a user. Read on
21 Nov 2026: 0 stars, 0 forks, 0 watchers, 0 outside issues, 0 discussions. The stop rule of
14 Dec 2026 is unchanged.

## D-28: one more study run on the order-desk question; no change to the product (2026-11-21)

**What led to it.** On 21 Nov the maintainer asked whether the project could use its own
tool to show something sooner. Read that day: the only outside comments the project has
had came from a result made with the tool (the order-desk study), and one reader's question
about run 3 is unanswered: run 3 tested one message that names the next step against the
text `null`, so it cannot tell "a message" from "this message". Run 3's registration says
so, and says that telling them apart needs a control message that names no next step.

**The views.** Astra, consulted, said to do this run before 28 Nov and no other form of
use of the tool on the project's own work: the model, the eight tasks, the fault and the
check already exist, and a reader asked the question. It said that D-23 allowed one named
study, which is finished, so this run needs its own decision. The orchestrator agreed, and
set aside a comparison of coding-agent settings (more cost, and it invites statements
about a vendor).

**The decision.**

- One registered run, run 4 of the order-desk study: on the eight stock-note tasks, with
  the first lookup returning the injected empty result, run 3's message that names the next
  step against a message of similar length that names none. One local model in both arms.
- The registration (both texts, the rule, the cap, the conditions for reading the verdict,
  the predictions) is committed and pushed before any trial. One start.
- The result is published whatever it is, under `plan/exec/v2/study/`. A reply to the
  reader who asked is prepared; the maintainer approves the exact wording and posts it.
- D-23 is otherwise unchanged: no feature, command, option or release before 14 Dec 2026.
  D-27 is unchanged: the README stays fixed to 28 Nov and the review dates stand.
- Stop: the work is dropped if the set-up takes more than two agent-hours. The run ends at
  the registered cap, at an error, or at a failed delivery check, and no round is added.

**What it does not claim.** That the run brings a user, a star or a reader. The
maintainer's own run of the tool is not use by someone else.

## D-29: further study runs only for a question someone outside asks (2026-11-21)

**What led to it.** Run 4 (D-28) answered a reader's question the same day it was asked
for. The maintainer then asked whether to keep using the tool on the project's own work.
Astra, consulted, said to hold a fifth run and to adopt a rule, and found a wrong statement
in run 4's record while answering (which arm ran first; corrected the same day). Its
warning: each run the project starts by itself raises another question about a model, a
wording or a task, and the weeks to 14 Dec can be spent answering the project's own
questions. The orchestrator agreed. The maintainer approved the rule.

**The decision, to 14 Dec 2026.**

- At most one registered run for each new, unanswered question that someone outside the
  project asks in public (a comment, an issue, a discussion, a reply).
- The question is answered from existing results first. A run is made only if they do not
  answer it.
- Before any live trial, a smoke trial included, the question, the arms, the cap and the
  stopping rule are committed and pushed. The set-up is checked with a fake model transport
  and offline tests, which call no model. This closes the fault of run 4, where 16 smoke
  trials came before the registration.
- No run is started only to have a run. A comparison on the 12B model and a guide for
  repeating run 4 on another machine wait until someone asks for them.
- D-23 and D-27 are unchanged. The reviews of 28 and 30 Nov, the re-runs of 4 and 6 Dec
  and the stop rule of 14 Dec stand.

**What it does not claim.** That a run brings a user, or that any result compares this
tool with another. A run the project makes for itself is not use by someone else; a
person outside repeating a run would be.

## D-30: the maintainer sets D-29 aside for one run on the project's own work (2026-11-21)

**What led to it.** About an hour after D-29 the maintainer asked for a run on his own
machine that uses the tool on real work of the project. The orchestrator and Astra both
advised against an exception: no one outside asked; the one candidate found needs some
hundreds of coding-agent runs; and a verdict on the project's own tickets does not show
that anyone else needs the tool. The maintainer read both views and chose to run it. The
decision is his.

**The decision.**

- One registered comparison with `arci verdict`: the coding agent the project uses for
  worker jobs, at the reasoning effort the workers were given on 21 Nov ("high"), against
  the higher effort used for consults ("xhigh"), on past tickets of this project with a
  check that runs without a person. The question is the project's own: may worker jobs
  stay at the lower effort.
- D-29's second point holds without exception: the question, the arms, the tasks, the
  check, the rule, the cap and the stopping rule are committed and pushed before any live
  trial, a smoke trial included. The set-up is checked with a stand-in for the agent that
  calls no model.
- One start. The run ends at a verdict, at the registered cap, or when the agent's
  service refuses further runs; no round is added afterwards.
- Everything else in D-23, D-27 and D-29 is unchanged. No further run of the project's
  own choosing follows from this one.

**What it does not claim.** Anything about the vendor's model in general, about other
people's tasks, or about use of the tool by anyone else. One machine, one period of hours,
the project's own tickets.

## D-31: one benchmark of the verdict rule against other release gates, before 14 Dec (2026-11-25)

**What led to it.** The maintainer asked what large companies lack for reliable agents and where
ARCI fits. Two research rounds (private) found the most-named obstacles are cost, value,
governance, integration and data quality, which ARCI does not serve, and one narrow fit: a release
decision for an agent change with the rule and thresholds fixed in advance and a record a reviewer
can recompute. No buyer was found asking for exactly this, and other gates come close (a fixed
score threshold as in AWS AgentCore and Braintrust, McNemar's test as in NVIDIA NeMo `nel compare`,
bootstrap intervals, evalsig's sequential monitoring). Astra proposed two benchmarks and advised
waiting until 14 Dec to run them. The orchestrator advised running the first now, since it changes
no product code. The maintainer chose to run it now.

**The decision.**

- One registered benchmark, B1: simulated paired pass/fail results with a known true difference,
  fed to the released `arci verdict` rule (2.4.1) and to rival gates rebuilt from their public
  documentation, to measure wrong decisions and the number of trials each needs.
- The protocol, every setting, the pass and fail criteria and the rule that says "stop this
  direction" are committed and pushed before any registered simulation runs. Code is checked with
  hand-made inputs only.
- No product code changes; nothing is released. D-23, D-27 and D-29 are otherwise unchanged; the
  stop rule of 14 Dec stands. B2 (recomputation by a second party) waits until after 14 Dec.

**What it does not claim.** That any company wants this, or that a benchmark result brings users.
A simulation measures the rule, not agents or their graders.

## D-32: the maintainer sets the 14 Dec checkpoint aside; building resumes (2026-11-25)

**What led to it.** After the result of benchmark B1, the maintainer wrote on 25 Nov 2026:
"Ignore 14 Dec checkpoint and let's keep on improvising. Taking a big leap is okay too."

**The decision.**

- D-23's rule "no new feature and no release before 14 Dec" no longer holds, and the stop rule of
  14 Dec is no longer a checkpoint. The counts it named (stars, outside issues or discussions, an
  outside posted result) are still recorded in `signals/`, as facts and not as a gate.
- D-29's limit of one registered run per outside question is lifted with it. What stays from D-29
  and D-31: any run whose result will be stated in public is registered and pushed before its first
  live trial or registered simulation, and is counted again by an agent that reads no write-up.
- A larger change of direction is allowed. Before one is chosen, the consultant (Astra) is asked
  and independent proposals are judged against the evidence already gathered (the two research
  rounds of 25 Nov, B1, the reader trial of 24 Nov); the choice is recorded here as its own
  decision, with what would count as failure.

**What does not change.** Merging to `main`, opening pull requests and publishing releases stay
with the maintainer. The pinned files, the privacy rule for local logs, and the wording rules
(never "first" or "only"; B1 is quoted with its weakness; simulated results say nothing about
real agents) stand.

## D-33: next direction: does a tool server's own failure reply help an agent recover; a three-day benchmark decides before any product code (2026-11-25)

**What led to it.** After D-32 the orchestrator asked for the next direction three ways, all on
25 Nov: the consultant (Astra) twice, a panel of five independent proposals scored by three judges
(does anyone want it; does it exist already; can it be built and proven), and a vetting of the
leading idea by six agents, one of them hostile. No proposal scored above 5 of 10 on demand, and
the panel wrote that the evidence supports no large leap. Two findings shaped the choice. The only
outside engagement this project has had is about recovery after a failed or empty tool result
(runs 3 to 6). And record-and-replay of agent traffic, statistical gates for pull requests, and
gates for coding-agent settings each have several existing tools.

**The decision.**

- Subject: a tool server (an MCP server) and the text of its own failure replies. The question a
  maintainer of such a server could act on: "does this reply, as my server sends it, let a model
  recover, or should I reword it?" The server under test is the real one, run locally on a seeded
  fixture; no production traffic is needed.
- Before any code under `src/arci`: one registered benchmark, Reply-0, of at most three laptop
  days, as study code. The server's own reply to a provoked bad call (missing argument, wrong
  type, bad enum, unknown value) is the candidate arm; a sentence that names the corrected call,
  built only from what the server knows, is the baseline arm, so BLOCK means "an edit worth
  making". Grading is against an answer key fixed beforehand, never "did it retry". Read-only
  tools only. Two local models. The verdicts of two existing rule-based checkers on the same
  replies are recorded before the first trial.
- Pass needs all four: (a) the control (the order desk, raw empty result against the naming
  sentence) gives BLOCK; (b) at least one decided BLOCK on a server this project did not write;
  (c) at least one decided cell where the measured verdict contradicts both rule-based checkers;
  (d) that reply, edited in the server itself with the rewrite switched off and on held-out
  tasks, gives the same decision. CANNOT TELL counts as a miss.
- On a pass: build the smallest tool a server maintainer can run, as additive modules. On a fail,
  or past three laptop days: this direction ends with no product code, and the corrected
  "recovery board" benchmark of the panel (Board-0) runs instead; its criteria K1 to K3 can end
  feature work.

**What is not claimed, now or after a pass.** That reply wording changes recovery, or that naming
the tool or the call helps: that is published (arXiv 2609.35381; also 2609.00072, 2611.11581,
2610.10062, 2610.32555). That fault proxies, an empty-result test, grading without a judge model or
provoking real servers are new (tool-eval-bench, AgentCheck, MCP-Injector, mcp-fault-bench, and
the checkers `mcp-linter` and `mcp-lint` exist). That results on small local models carry to
hosted models. That anyone who publishes a server has asked for this: none has. Nothing is filed
on anyone else's tracker.

**Set aside by this decision.** The gate for coding-agent settings (the orchestrator's first
leaning; Astra showed that the hard part is tasks that separate two settings, and a tool for it
exists), record-and-replay "worlds", a second version of the decision rule, and plug-ins.

## D-34: Reply-0 failed on criterion (c); the failure-reply direction ends with no product code; Board-0 is next (2026-11-25)

**What led to it.** Reply-0 ran on 25 Nov as registered (`cd8f77a`, `3e54310`, `394d396`): 1,868
trials on two local models, one start, no error, every run verified by two counts, a blind recount
and the consultant's regrade. Result page: [study/reply-0/result.md](study/reply-0/result.md).

- (a) met: the control gave BLOCK on the 4B model (sentence 16 of 16, blanked result 0 of 16).
- (b) met: the git server's bare `Commit history:` reply gave BLOCK on both models (2 of 16 and
  0 of 16 against 16 of 16).
- (c) missed: the filesystem server's "no such file" reply gave CANNOT TELL on 4B (91 of 120
  against 106 of 120) and PASS on 12B (80 of 80 each). On 4B the corrected read was made in every
  trial of both arms; the failed answers held the right text with extra words.
- (d) not run: nothing qualified.

**The decision.** D-33's rule applies as written: any missed criterion ends the direction. No code
under `src/arci` is written for a failure-reply check. Board-0, the corrected recovery-board
benchmark of the panel, is the next step; it is registered before any trial, and its criteria K1
to K3 can end feature work.

**What is kept from Reply-0, with its limits.** The git result is the strongest measured finding:
a reply that looks like an empty success stopped both models. The shown-only follow-up limits it:
on 4B a generic "check the arguments and call again" sentence did as well as the sentence that
names the call (80 of 80 each), so the comparison supports "bare header against a sentence" and
not "naming the call". Unprompted, neither model made any of the wrong calls (0 of 16 in each of
six model and cell combinations), so nothing here says how often this happens. Two small local
models; nothing carries to hosted models. Nothing is claimed as new and nothing is filed on anyone
else's tracker.

**Predictions.** Both written predictions (the consultant's about 10% chance of a pass; the
orchestrator's "(a) and (b) met, (c) missed, (d) not run") matched the outcome.

## D-35: Board-0 as it will be registered; a fail stops the Board and nothing else (2026-11-26)

**What led to it.** D-34 made Board-0 the next step and the maintainer wrote "Start Board-0" on
26 Nov. Before anything was built, the orchestrator ran the day-1 check the panel had asked for
(four sources read: no published per-model table of recovery after an empty tool result, split by
reply wording, on local models; two of the papers were not read to the end) and asked the
consultant (Astra) ten design questions. The maintainer then answered two questions.

**The decision.**

- **One comparison, not two.** After a correct lookup whose result is blanked once, the model
  gets either the empty text as delivered (candidate) or the stock sentence "The lookup returned
  no data. Repeat the same call with the same arguments." (baseline). The bare-error cell of the
  proposal is dropped: arXiv 2611.11581 covers explicit errors on 13 open models.
- **Five local models, two task families, two days.** The two installed models plus
  `llama3.1:8b`, `mistral-nemo:12b` and `granite3.3:8b` (downloads approved by the maintainer,
  about 17 GB). Eight order-desk tasks and eight calendar-desk tasks written by a worker that had
  not read the earlier runs, equal weight every round. 16 pairs a round, at most 26 rounds: the
  largest cap for which the released `arci plan` gives exact projections for the whole grid.
  Everything runs twice, on two calendar days.
- **The answer is a tool call.** Reply-0 lost many trials to right answers wrapped in extra
  words. In Board-0 the model ends a trial with `submit_answer(value)`, graded by exact typed
  match against the seeded key. No retry hint in the prompt.
- **Study code first.** No `arci board` command under `src/arci` before the benchmark passes.
- **Criteria K1 to K5** as in the registration: reach beyond the 4B model, a table that is not
  flat, the same decisions on both days, enough decided runs at a usable cost, and evidence a
  stranger can check offline.
- **What a fail stops.** The maintainer chose on 26 Nov: if K1, K2 or K3 misses, the numbers are
  published and work on the Board stops; any other feature needs its own evidence first. This
  replaces the wording of D-33 and of the panel ("can end feature work"). A miss of K4 or K5
  alone allows one registered repair and one rerun.

**Not claimed, now or after a pass.** That reply wording changes recovery (published: arXiv
2609.35381, 2611.11581, 2610.10062); that a recovery benchmark on local models is new
(tool-eval-bench has error-recovery scenarios and one on an empty search); that five small local
models speak for hosted models or for real agents; that anyone asked for this table.

## D-36: Board-0: all five registered criteria hold; the numbers are published and nothing is built (2026-11-28)

**What led to it.** Board-0 (D-35) ran as registered: day 1 on 27 Nov 2026 (00:56 to 01:10 local
time), day 2 on 28 Nov (00:05 to 00:18), 20 runs, each started once and finished, 992 trials on
five local models. The registered report was read, an agent that saw only raw files counted and
graded everything again, the consultant (Astra) reviewed the result page and its eight
corrections were made, and a fresh offline agent checked the evidence file.
Result page: `study/RESULT-board-0.md`. Evidence: `study/board0-evidence.zip`, SHA-256
`35f70d9b3a787a1e429fd623dd550b80d77b99da60ea7ce2291d74d9204e5340`.

**The outcome, criterion by criterion.**

- **K1 holds.** Day 1: Gemma 4 12B and Llama 3.1 8B give BLOCK. On Gemma the empty arm is 100
  points below the sentence arm in orders (0/16 against 16/16) and 62.5 points below in calendar
  (1/16 against 11/16).
- **K2 holds as written.** Day 1: three models give BLOCK and Qwen 2.5 7B gives PASS with its
  empty arm at 16/16 in orders and 14/16 in calendar. Both written predictions expected K2 to
  miss. It held because that model passed more trials with the empty result than with the
  sentence (30/32 against 11/32 on day 1, 29/32 against 11/32 on day 2). That is a count; no
  cause is known.
- **K3 holds.** No model changes between PASS and BLOCK. Four of the five day-1 decisions are the
  same decision on day 2. Mistral NeMo 12B's day 2 is not rated (4 of 8 calendar tasks in the
  clean row) and so is not a decision.
- **K4 holds.** 9 of 10 model-days are decisions; the median model-day took 127.76 seconds.
- **K5 holds.** The verifier accepted the evidence file offline (10 of 10 stored verdicts
  reproduced, every trial regraded) and rejected three altered copies (one grade, one rule, one
  verdict), each with its own matching digest.

**What this allows, and what is decided.** By the registered rule a pass of all five allows an
`arci board` command to be built as additive modules. It does not require it. Nothing is built.
A web review of 27 Nov found recovery after tool failures to be a field with several larger
published benchmarks, and one published leaderboard near this one with almost no visible use
(one case, not a rate). The consultant advised against a leaderboard as a destination. The
maintainer chose on 27 Nov that nothing new is built before one outside person has tried an idea
by hand; that choice gets its own entry. The registered 30-day check stands: by 28 Dec 2026, one
row run and sent in by someone outside the project, or three outside questions about recovery,
count as the table having mattered; otherwise it stays a dated record.

**Stated plainly.**

- Mistral NeMo 12B passed 0 of 80 trials in both arms on both days. Its PASS is a tie at zero and
  K2 does not rest on it.
- The pin was corrected by amendment 1 after its first results were known, and Granite 3.3 8B
  was replaced by the spare Qwen 2.5 7B under amendment 2. So the table has four makers, with two
  models from one maker.
- Between the two days the model server was stopped and started again (same version and
  settings) and another study's first day (Size-0) ran on the same laptop. A check before day 2
  confirmed the server version, the five model digests and the context size.
- The K5 agent's first attempt failed because the verifier calls the released `arci` command by
  name; with the command's folder on the search path it ran. The blind recount used `jq`; its
  Python version could not run in its sandbox and was run by the orchestrator afterwards with
  the same totals.
- The scheduled task that was to finish Board-0 at 01:30 was switched off and the work done in
  the main session, so that the write-up could carry the facts above.

**Not claimed.** As in D-35 and the registration: nothing about hosted models, larger models or
real agents; no claim that reply wording changing recovery, a local-model recovery benchmark or
an empty-result test is new; no claim that anyone asked for this table.

## D-37: Size-0: the size reading is withheld; the rows are published as they are (2026-11-28)

**What led to it.** A reader of the order-desk write-up asked whether the 4B model's 0 of 24 in
Run 6 was about model size and proposed one family at more than one size. The maintainer
approved the study and two model downloads on 27 Nov, and on the same day moved its first day
into the idle hours between Board-0's two days. Registered and pushed before any probe or trial
(`b381114`, then `3d4ee3d`, which corrected one test that assumed a placeholder registration;
the 14 run descriptions are byte-identical in both). Day 1 ran 27 Nov 17:09 to 18:08 local time,
day 2 on 28 Nov 00:19 to 01:04, after Board-0's last run. All 14 runs started once and finished.
Result page: `study/RESULT-size-0.md`. Evidence: `study/size0-evidence/claims.zip`, SHA-256
`fcb0bb543a83392927558f850e6e70f976dcced81d80347a847841a66a7516be`.

**The outcome.** The registered rule needs all three Qwen 3.5 builds rated and complete on both
days. The 2B build is not rated on either day: with the order supplied it passed 23 of 160 and
16 of 160 trials, and 0 of 8 order ids qualified. So the size reading is withheld and no sentence
about size is written. The rows, "looked the order up again / exposed":

- 2B (not rated): 33/160 and 32/160.
- 4B: 1/144 and 0/160. Run 6 recorded 0/24.
- 9B: 56/160 and 58/160.
- Gemma 4 12B (reference, day 1): 160/160. The 24 of 24 reported on the public thread on 22 Nov
  had no stored trial records; this count has them.

An agent that read no write-up recounted all 14 runs with the same counts. The study's checker
verified the unpacked evidence. The consultant (Astra) reviewed the page; its eight corrections
were made.

**Stated plainly.**

- A link to the registration had been promised on the public thread before the first trial. It
  was not posted there before the first trial. The pushed commit is the public time stamp.
- The first registration commit was pushed while one test failed; the orchestrator had chained
  the test run and the push without stopping on failure. Corrected before any probe or trial.
- Predictions: the consultant's 9B estimate (about 35%) was close; the orchestrator's (about
  50%) was not. Both expected the 4B build near zero. The 2B build's clean failure had been
  given about a 40% chance by the orchestrator.
- These are three separately released builds of one family, one prompt, one scripted mistake,
  one laptop. Nothing here speaks for parameter count as a cause, for hosted models or for real
  agents.

**What follows.** A reply to the reader with these rows, for the maintainer to post. No further
size run is planned; a new run would need a new outside question and its own registration.

## D-38: before anything new is built, one outside person tries the idea by hand (2026-11-28)

**What led to it.** On 27 Nov the maintainer asked whether the project is moving in the right
direction and pointed to six widely used agent-skill repositories as models. A web review (23
sources, 25 checked claims; private notes) found that recovery after tool failures is covered by
several larger published benchmarks, that a leaderboard near Board-0's has almost no visible use
(one case), that Show HN is restricted for new accounts, and nothing for or against demand for
the log tool. The consultant (Astra) then challenged the orchestrator's reading of both.

**The decision** (the maintainer, 27 Nov: "Yes, test first").

- Board-0 and Size-0 are published as registered. No leaderboard is built as a destination.
- Nothing taken from the six repositories is built yet. The leading idea is a skill that lets a
  coding agent run the user's own tests on an old and a new version of an agent, prompt or
  skill, and has `arci verdict` decide. An existing test folder in someone's project shows that
  they test changes; it does not show that this decision is their bottleneck.
- The test, by hand, with released code only: one person outside the project supplies two
  versions and their test command; the orchestrator runs the existing command line; nothing new
  is written.
- **Counts as demand:** they supply both versions and the command, and use the answer
  (INCONCLUSIVE included) in their real decision. Any set-up they wished were automatic is noted.
- **Counts as a miss:** they decline, or no usable reply within 14 days of the maintainer posting
  the question. A miss ends this idea; another idea needs its own evidence.
- The question goes to the one reader who has asked this project questions, in the reply that
  carries the Size-0 rows, and may be repeated in the project's own discussion thread. Nothing is
  asked on anyone else's tracker.

**A correction.** On 27 Nov the orchestrator told the maintainer, and wrote into the research
brief, that "no new feature before 14 Dec" and the 14 Dec stop rule were in force. D-32 had
lifted both on 25 Nov. The maintainer was told the same evening. The research's remark that the
stop rule is sound rested on that wrong premise and is not relied on.

**Not decided here.** Any change to the README, any support for further coding agents, any
automatic saving of daily counts. Each waits for the test and for the maintainer.

## D-39: Same-0 is published; ARCI is described as a test bench for harness changes, as a hypothesis with a fail rule (2026-11-28)

**What led to it.** With Board-0 and Size-0 published, the maintainer wrote on 28 Nov before
going away for the night: "have you proved anything? ... any new benchmarks to run? do we need
to pivot (approved)? ... Prove something in the morning!" The consultant (Astra) was asked what
could honestly be shown by morning and whether a pivot is supported. Its answer: no new live
run; one count on published records with a single primary question; and the pivot recorded as a
positioning hypothesis, with D-38 unchanged as the gate for building.

**Same-0, the count.** Registered and pushed before any of its numbers were computed
(`e95fe53`), then counted by two agents separately with equal results (`b59c859`). Size-0's 14
runs compare an agent with an identical copy. The registered sentence: "With identical
configurations, 0 of 14 three-round comparisons showed the second copy ten points or more behind
the first, and 3 of 14 showed it ten points or more ahead." Secondary: the two copies' scores
differed in 64 of 135 single rounds. The orchestrator predicted two drops and saw none. The
released rule's stored verdicts on the same runs were 7 PASS, 7 INCONCLUSIVE, 0 BLOCK; that is
printed and not claimed as mistakes avoided. Page: `study/RESULT-same-0.md`.

**What the three results show together, and no more.**

- Board-0: one sentence added to a tool result took three local models from 0 to 13% to 84 to
  100% of trials passed, and took a fourth from 30/32 to 11/32. The same change helped some
  models and hurt another.
- Size-0: under a prompt that says "Retry an empty lookup once", the repeat lookup was counted
  in 1/144 and 0/160 trials for one build, 56/160 and 58/160 for another, and 160/160 for the
  reference model. The size reading is withheld; these are counts per build.
- Same-0: with nothing changed at all, three runs a side put two copies ten points or more
  apart in 3 of 14 comparisons.

**The decision.**

- No code, package or command changes. The pivot is in what the project says it is for: **a
  test bench for harness changes.** Someone changes a prompt, a tool's reply, a skill or a
  setting of an agent, runs the old and the new version on the same tasks, and gets PASS, BLOCK
  or INCONCLUSIVE with the assumptions printed. Local-model studies and the Board-0 table become
  evidence for that purpose and are not a product line.
- This is a hypothesis about what people want. Nothing above shows demand: nobody outside the
  project has used the tool.
- **Fail rule.** D-38's hand test decides. If the one outside person declines, the idea ends at
  once. If there is no usable reply within 14 days of the maintainer posting the question, it
  ends then (12 December 2026 if posted on 28 November). It counts as support only if they
  supply two versions and a test command and use the answer, INCONCLUSIVE included, in a real
  decision. Board-0's own 30-day check (28 December) is separate and unchanged.
- Until that test is read: nothing new is built, no leaderboard, no skill, no automatic
  saving. Wording on the README changes only through a pull request the maintainer merges.
- No thread post was made on 28 Nov before the maintainer's return; `launch/devto-reply-7.md`
  waits for him.

**Not claimed.** That the three results are new findings in the field (each has published
relatives; see the result pages). Anything about hosted models, larger models or real agents.
That a harness test bench is wanted.

## D-40: one improvement is built before the hand test: `arci check-change` (2026-11-28)

**What led to it.** On the morning of 28 Nov the maintainer read the night's report and wrote:
"no. That's for tomorrow. Today is for ARCI improvements!!!!" Asked which improvement, with the
note that choosing one sets aside D-38's "nothing new is built before one outside person has
tried the idea by hand" for today, he chose "One-command test".

**The decision.**

- One command is built, `arci check-change`: the user gives the test command for the old version
  and for the new version of an agent, prompt, skill or setting; the tool runs both in paired
  rounds with the released rule and answers PASS, BLOCK or INCONCLUSIVE. Design record:
  `docs/design/0019-check-change.md` on the branch `v2/change-check` (from `main` at `c1c88f3`),
  with 18 acceptance items. The consultant (Astra) designed the interface against the released
  code. No new statistic; additive code; no frozen file edited.
- D-38 is set aside for this command only. Its hand test with one outside person stays the test
  of demand, and D-39's fail rule stays as written. Nothing else from D-38's list is built (no
  skill, no leaderboard, no automatic saving, no README change).
- The maintainer opens and merges the pull request and decides on any release. The thread posts
  wait for another day, as he said.

**Stated plainly.** Nobody outside the project asked for this command. It is built on the
maintainer's decision and the orchestrator's recommendation, before any evidence of demand.
