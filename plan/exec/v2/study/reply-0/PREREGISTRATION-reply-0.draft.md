# Reply-0 registration: does a server's own failure reply let a model recover

Registered 25 November 2026, before any model trial. The file keeps its draft name because
the digest list and the launcher pin that name. The wrapper verifies the pushed commit
before any live request. DESIGN.md specifies the offline rehearsals.

## The question, the setup
Can a model recover from a server's own failure reply, or would rewording it help?
D-33 makes product work contingent on (a)–(d). Each cell pairs one reply with one model.
The relay records tool traffic in a ledger. CANNOT TELL is printed as INCONCLUSIVE.

Day 1: 66 read-only bad calls; none returned a full corrected call, 39 named the wrong
argument. mcp-lint 1.0.4 and mcp-linter 1.2.0 (P4) passed all 66 and all 64 registered
reference-server replies. Before sealing, check all 72 bare keys and full good replies.

Servers: filesystem, `@modelcontextprotocol/server-filesystem` 2.4.0, 10 read-only tools;
git, `mcp-server-git` 2026.11.18, 8 read-only tools; order desk, a study stand-in over
`arci.mcp_toolset_server` 2.4.1, 2 reading tools. Python 3.13.12, ARCI 2.4.1, Node 24.18.0;
git 2.55.0 at `/opt/homebrew/bin/git`. Servers have no network and an empty HOME.
The relay hides writing tools. Fixture: 12 files and 5 commits, built by fixture.py at
`$FX` = `/Users/Shared/arci-reply0/fx` (no symlinks). The day-one record is ENVIRONMENT.md.
The fixture manifest and regenerated tasks/tasks.json have these respective SHA-256 values:
`9c0f4a2dcfaf924b46228be3a0d8dfe2248517bf9039302c44103dc63f1a84ea`
`76ee13ca3c4eaa54514ae4c08cef1cc75e93e81c8b43ac4073dee5e267b922a1`
Models via Ollama as in run 6 (temperature 0.7, reasoning off, context 32768, no sampling
seed), "4B" then "12B", each with its sha256. Ollama: `0.32.14`, from `ollama --version`.
`qwen3.5:4b-mlx-ctx32k` `c01efed5a36459ab6ffffa0b158636a014d8b30b4d5493167cba9916ed558430`
`gemma4:12b-mlx-ctx32k` `a5c533115db870b8db2e39657686a8742a5e7182bd00403b851dd1af28e4efbc`

## Cells and tasks: the bad call, the server's reply, the sentence
- **C0, control.** Order desk, `lookup_order` with the right order id; ARCI's released fault
  `empty_result` blanks the first result (`content: []`), so the model reads an empty text,
  which mcp-lint fails and mcp-linter does not grade. Sentence (runs 3 to 5): `lookup_order
  returned an empty result. Call lookup_order again with the same order_id.`
- **G1.** git `git_log` with `start_timestamp` in a form git cannot read, e.g. "20260115".
  Reply, marked as a success: `Commit history:\n`. Sentence: `No commit matched
  start_timestamp "20260115". If that is meant as a date, write it as YYYY-MM-DD (for
  example 2024-01-15) and call git_log again with the same repo_path.`
- **F2.** filesystem `search_files` with a pattern without `*`, e.g. "todo". Reply, a
  success: `No matches found`. Sentence: `No entry matched the pattern "todo". A pattern
  with no wildcard matches only an entry whose path below the given path is exactly that
  text. Call search_files again with the same path and the pattern "**/*todo*".` The rule
  fires on this successful empty search only for a full match of `^[A-Za-z0-9._-]+$`.
  Relay and edited server use the same registered predicate and sentence on every call.
  Compare complete results at the opening and at a later call outside the predicate.
- **F1.** filesystem `read_text_file` with a file name that is not there. Reply, an error:
  `ENOENT: no such file or directory, lstat '<path>'`. Sentence: `There is no file at
  <path>. Call list_directory with path "<folder>" to see the files that exist, then call
  read_text_file with the full path of the right one.`
- **F0 and G2, shown only** (texts in `tasks/tasks.json`). F0: `read_text_file` without
  `path`, an SDK text. G2: `git_branch` with a `branch_type` not allowed.
- **Every sentence** uses only tool names, the arguments of the failed call and fixed words:
  what the server knows at that moment. Nothing from the fixture, the task or the key.

Unknown values on filesystem, git and order desk accounted for 13, 11 and 2 bad calls.
Bad enums accounted for 1, 1 and 0; missing/wrong types accounted for 18, 16 and 4.
F1, F2 and G1 were chosen as the weakest server-authored replies. That selection limits
generalisability. F0 is an SDK validation error; G2 lacks a held-out set. Both are shown
only. F2's proposed wildcard always finds the file because each bare pattern is part of
its name. The result concerns wildcard guidance for precisely that case.

The file tasks are in `tasks/tasks.json`: rows n1 to n8 (main) and d1 to d8 (held-out), each
with the file under `$FX/files`, the question, the expected strings, the decoys, F1's wrong
file name and F2's bare pattern; F0 uses the n rows only. The F1 ask is `One of the files in
the folder <folder> answers this question: <question> Reply with the answer only.` F2
names the search root; F0 names the file. Before sealing, regenerate the exact reply
transcripts in tasks/check/ with tasks/check_tasks.py. G1 asks `Which commits
in the git repository at $FX/repo were made on or after <date>? Reply with their commit
messages only, one per line.`
Bad: `start_timestamp` YYYYMMDD; good: YYYY-MM-DD. Expected: the newest k of the five commit
messages in `$FX/manifest.json`. Main: 7, 9, 11 January 2026 (k = 3); 15, 25 January, 1
February (2); 10, 20 February (1). Held-out: 8, 10 January (3); 14, 20, 30 January (2); 5,
15, 25 February (1). G2: four asks about branches, two bad values each. C0 asks `How many
cents were paid in total for order <id>? Reply with the number only.` for ORD-103 to ORD-124
in steps of three; expected: that order's `total_cents` in the seeded world of the trial. A
trial passes on its final answer alone (600 raw characters maximum). Trim the answer.
Normalise each line with NFKC, casefold and collapsed whitespace. Strip surrounding quotes
(straight, curly or backticks), round/square/curly brackets and spaces, one final period,
then wrappers again. Remove commas only in a whole unsigned integer grouped in thousands.
A scalar must be the complete value on one line. Extra values, prose and negations fail,
including "Bram de Wit, not Asha Verma" for Bram de Wit, or "-260" and "260.5" for 260.
For branches and commit messages require the expected lines once each, in any order. Reject
"main release-1" for "release-1". Derive file keys from the requested row, field or item.
Test the bare key and whole good reply on every task, including git and C0. A paste with
decoys or extra material must fail. An actual answer-only reply may pass.

## What every trial does
The agent (the loop of `examples/ollama_mcp_agent`, ported) reads the tool list and makes
the scripted opening. C0 carries order_id in the server task. The first model request uses
only the registered system prompt, ask and opening history as messages. The model has
8 steps, 12 tool calls and 120 s. Its last message without a tool call is the answer.
Baseline arm, `naming-sentence`: the reply's text is replaced by the
cell's sentence. Candidate arm, `reply-as-given`: the text as sent. Only the text differs;
the error flag is never changed and never shown to the model. The relay replaces every reply
of the trial that fits the cell's rule, as an edited server would, so ARCI's sealed record
shows the delivered text. In C0 the fault acts after the relay, so the agent replaces the
first lookup's empty text. Unscripted row, shown only, after the clean row: per model and
eligible main task, 2 trials with no scripted call and no sentence; 8 tasks by 2 trials by
the three eligible cells is 48 trials a model, 96 in all. Reported per cell: in how many of
its 16 trials the ledger shows a reply fitting its rule. Report zero exposure as
"0/16 for this model and cell".
Clean row, before any pair: for each model and each task of a cell it may run (4B all 72;
12B the 56 of C0, G1, F2, F1), 2 trials with the first good call scripted in place of the
bad one, no sentence, no fault: 144 + 112 = 256 trials. A task is dropped for a model if
neither passes, and an errored trial counts as not passed; main and held-out sets count
apart. Kept tasks 8, 7, 6, 5 give 15, 18, 20, 24 rounds; with fewer than 5 the cell is not
run: CANNOT TELL.

## Rule, size, and what it can decide
The released rule as in run 6: alpha 1/20, margin 1/10, stakes 1/4 and 1/2, threshold 40
each way, on the mean pass-rate difference over kept tasks. Eight kept tasks allow 120
pairs. Seven allow 126. The maximum is 252 trials per suite. Read at round ends only; stop
at the first PASS, BLOCK or ERROR. CANNOT TELL at the cap. Errored pairs stay and count
against both sides; four are tolerated. ARCI chooses arm order, with one worker and
per-round scenario seeds. Exact projections assume independent arms, the same joint law
for each task and round, and no errors. Run `arci plan` on the four plan-TxR descriptors
with rates B and C and agreement B*C + (1-B)*(1-C). The 128 recomputed rows are
in projections/registered-rows.json. Compared with 8 × 15, verdict probabilities move by
at most 0.047 and expected pair counts by up to 5.96. The 8 × 15 projections follow.

| Sentence/reply | PASS | BLOCK | CANNOT TELL | Mean pairs |
|---|---:|---:|---:|---:|
| 90/90 | 0.417 | <0.001 | 0.583 | 105 |
| 90/80 | 0.007 | 0.004 | 0.989 | 120 |
| 90/70 | <0.001 | 0.245 | 0.755 | 112 |
| 90/60 | <0.001 | 0.849 | 0.151 | 79 |
| 90/50 | <0.001 | 0.996 | 0.004 | 50 |
| 75/45 | <0.001 | 0.702 | 0.298 | 87 |
| 60/30 | <0.001 | 0.682 | 0.318 | 88 |
| 50/30 | <0.001 | 0.159 | 0.841 | 114 |

Under independent pairs, stable task laws and no arm-order effect, the false-BLOCK bound
is 2.5% per cell when the true shortfall is ten points or less.

## Criteria (a) to (d), as in D-33, and reading conditions R1 to R4
- (a) C0 gives BLOCK on 4B, read on the 4B model only: the maintainer's decision, since D-33
  names no model, runs 3, 4 and 6 were on 4B, and 12B repeated all 120 empty lookups unaided
  in run 2. C0 on 12B is shown only. (a) shows this agent, grader and rule can give BLOCK
  with a model. It does not exercise the relay's rewrite. Each C0 pair shares one seed; the
  eight orders of a round have eight seeds and amounts (the released per-round schedule).
- (b) At least one statistical BLOCK among the six eligible cells (G1, F2, F1 on 4B and
  12B), all on servers this project did not write.
- (c) Both checkers must return pass and at least one must have assessed the error text.
  Only a statistical F1 BLOCK satisfying R1 to R4 meets (c). On F1, mcp-linter assessed
  ENOENT and mcp-lint returned recoverable. On G1 and F2, mcp-linter excuses the success
  reply and flags it without the excuse. Silence on those texts cannot satisfy (c).
- (d) Confirm the first qualifying F1 with at least five kept held-out tasks, once, on
  the same model. Baseline uses the server with the F1 edit, candidate the shipped server;
  relay rewriting is off throughout. Require another statistical BLOCK satisfying R1 to R4.

Every required BLOCK must be statistical and satisfy R1 to R4. PASS, CANNOT TELL, ERROR,
hard-violation BLOCK and unrun are misses. Across six main cells the false-BLOCK bound is
15%. Under the joint null that neither F1 model exceeds the margin on either task set,
two F1 screens and one fresh confirmation give a bound of 0.125% if the 2.5% confirmation
bound holds conditional on selection. This is not an unconditional overall pass chance.
Under independent fresh trials at 90/60, 75/45 and 60/30, the projected chance of two
BLOCKs on a fixed model is about 0.72, 0.49 and 0.46 respectively. Publish every outcome.
Two independent counts and a reader blind to the write-up must agree.
- R1. The registration was pushed first; file digests, versions, model digests and context
  32768 match.
- R2. Exactly one ledger and one receipt per scheduled trial through the stopping round.
  Independently compute delivery from the registered call, exact fixture reply, assigned
  arm and rule. Compare that expectation with the ledger, sealed tool record and actual
  first request. Persist the sent bytes when its response arrives. For C0 check the
  original lookup in the ledger, the sealed ARCI empty_result injection and the assigned
  first-request text separately. For (d) verify
  server identity, zero relay text rewrites and its registered text in all three records.
- R3. No crash; at most 5% per arm hit 120 s. Call/step budget failures stay in the counts.
- R4. Fixture unchanged. A10 requires `arci gate` "stored decision: MATCH" on suites only.
  For plain clean and unscripted pairs, verify the schedule and both independent counts.

## Order of runs, the clock, and what runs before the clean row
Order: clean, unscripted, C0 on 4B. Stop if C0 lacks a valid statistical BLOCK.
After valid C0, run F1 on 4B first, then F1 on 12B if needed regardless of G1/F2 outcomes.
Confirm immediately on the first qualifying F1 with at least five kept held-out tasks.
A failed confirmation is final. No second attempt. With no qualifying set, (d) is unrun.
After valid C0 run and publish G1 and F2 on both models as measured results, even if the
strict path fails. They may meet (b) but cannot complete a pass. Finish remaining rows
within the clock: any unrun F1 on 12B, F0 and G2 on 4B, C0 on 12B and the generic
follow-up (baseline naming sentence, candidate generic_sentence). F0 BLOCK or generic
PASS limits attribution to the published comparison. Day 3 ends at 23:59 local time on
the second calendar day after 25 November with a study commit or a trial start.
An unfinished run is "not run". Start a shown-only run only if its cap fits the time left
at measured clean-row speed. Otherwise report "not run: time". Any missed criterion ends
the product direction; Board-0 is next. After push and before clean, test wiring with two
requests per model using a made-up tool and an ask in no task. Test (i) a scripted call
with non-empty tool text and (ii) one with empty tool text. Record HTTP status and whether
a message came back. Save and publish the words without using them. If (i) fails, stop,
correct harness/agent.py, amend and push once with the failed output, and run the
check once more. If only (ii) fails, C0's candidate text is the four characters `null`,
said in the result. Otherwise C0's candidate text stays the empty string, which is what this
path really delivers. The warm-up request is `Reply with OK.` with no tools. Descriptor
digests cannot be registered before the clean row, because the kept tasks set the rounds.
They go into a second, dated note, pushed after the clean row and before the first deciding
run; that note gives each descriptor's sha256 and nothing else.

## Interpretation and cost
A pass supports the F1 edit for the tested model after a scripted missing-file call.
Report spontaneous exposure separately. A deadline, failed delivery audit or insufficient
kept tasks can end the product decision while leaving recovery unanswered. Even at 90%
versus 70% success, CANNOT TELL occurs about 76% of the time under the projection.
The control changes run 6's prompt, question and tool path. F1 already names the folder;
F2's suggested wildcard contains part of the right filename by construction.

Not claimed, now or after a pass: that wording changes recovery or naming the call helps
(arXiv 2609.35381; 2609.00072, 2611.11581, 2610.10062, 2610.32555); that fault proxies, an
empty-result test, grading without a judge model or provoking real servers are new
(tool-eval-bench, AgentCheck, MCP-Injector, mcp-fault-bench, `mcp-linter`, `mcp-lint`); that
two small local models speak for hosted models; that BLOCK means "ship this sentence"; that
any maintainer asked. No issues are filed. Budget 192 trials on 4B and 160 on 12B before
suites. Fourteen suites give an upper bound of 3,880 trials. At the stated slow rates,
six 4B and eight 12B suites allow 14.46 hours before timeout overhead (4B 3–5 s/trial,
12B 6–20 s/trial). Report clean-row timings. Up to 12 tolerated timeouts add 24 min/suite.

## Launch and publication
Before wiring, warm-up or any other live request, verify the pushed registration commit
and input digests. Atomically claim the canonical model/cell/run slot before warm-up, in
one study-wide claim directory; keep the claim after interruption. Close inherited stdin.
One start only, one live suite at a time. REPLY0_NO_SANDBOX=1 skips nested sandbox-exec.
Pin the harness, tasks, edited diffs, orderdesk files, probe.py, fixture.py, both checker
feeders and fixture manifest. Use neutral launch paths before sealing. Verify the assembled
allowlist and scan its contents, including logs, for personal paths before publication.
Publish only these relative files (braces enumerate names, RUN is a scheduled identifier):

- `{DESIGN.md,PREREGISTRATION-reply-0.draft.md,ENVIRONMENT.md,reply0-digests.sha256}`
- `{fixture.py,probe.py,orderdesk/orderdesk_world.py,orderdesk/task.json}`
- `tasks/{tasks.json,make_tasks.py,reply0_grade.py,file_keys.py,f2_parity.py}`
  and `tasks/{check_tasks.py,run_checkers.sh,check/tasks.check.json}`.
- `checkers/{feed_mcp_lint.mjs,feed_mcp_linter.py,verdicts.json}` and
  `tasks/check/registered-{filesystem,git}.{mcp-lint,mcp-linter}.json`, plus
  `tasks/check/registered-{filesystem,git}.not-excused.mcp-linter.json`.
- `projections/registered-rows.json` and `projections/plan-{8x15,7x18,6x20,5x24}.yaml`.
- `harness/{relay,agent,offline_model,reply0_oracle,make_suites,clean_row,wiring_check}.py`,
  `harness/{make_edited,audit,count_a,count_b,make_digests}.py`,
  `harness/{INTERFACE.md,DEVIATIONS.md,run-reply0.sh,edits/{F1,F2,G1}.diff}`.
- `clean-row/kept.json`, `descriptor-digests.sha256`, `wiring.json`, `result.md`.
- `runs/RUN/{descriptor.yaml,manifest.json,trials.jsonl,events.jsonl,decision.json}`,
  `runs/RUN/{ledger.jsonl,receipts.jsonl,audit.json,count_a.json,count_b.json,run.log}`.
  Include the suite gate output in run.log. Each RUN must occur in the registered schedule.
Exclude boundary-check/runs and boundary-check/runs-repeat. Never copy a directory.
Report every scheduled, missed and interrupted run. No retries, extra rounds or tasks.

## Predictions
The consultant (Astra): about a 10% chance of an overall pass. (a) 75% a valid BLOCK on
the 4B control. (b) 70% given (a), G1 the likeliest BLOCK. (c) 25% given (a): ENOENT and
the folder named in the ask already suggest listing it. (d) most likely not run; if
reached, 55% a confirming BLOCK.
The orchestrator (Claude): (a) BLOCK. (b) met, by G1 on the 4B model. (c) not met: F1
gives PASS or CANNOT TELL on both models. (d) not run. Overall: fail.
The maintainer: none supplied before registration.
