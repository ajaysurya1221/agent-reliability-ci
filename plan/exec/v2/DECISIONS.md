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
