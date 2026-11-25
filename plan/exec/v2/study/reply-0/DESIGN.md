# Reply-0 harness design

Written 25 November 2026, day 1 of 3. Design only: no model was called and nothing under
`src/`, `tests/` or `docs/` is touched. The registration draft is
`PREREGISTRATION-reply-0.draft.md`; this file says how its trials are run and checked.
Everything here is study code under `plan/exec/v2/study/reply-0/`.

The fixture is `$FX` = `/Users/Shared/arci-reply0/fx`. The registered task digest is
`76ee13ca3c4eaa54514ae4c08cef1cc75e93e81c8b43ac4073dee5e267b922a1`.
Section 6 distinguishes the task checks from the production rehearsals still due before
freeze. The registration controls scheduling, interpretation and publication.

Words. Boundary: the ARCI process between agent and tool server; it records every call and
decides whether a trial was valid. Relay: a small study program between the boundary and the
real server. Ledger: a file the relay writes, one line per call: what the real server was
sent and what it answered. Arm: one side of a comparison. Opening: the first tool call of a
trial, made by the harness and not by the model. Receipt: one durable record per trial holding
the first request actually sent. Stand-in: a fixed script that plays the model in checks that must
not call a model.

## 1. One trial, as a picture

```
arci run (released 2.4.1, one worker, started with a small fixed environment)
 |
 |-- boundary: records tool calls, applies the control's fault, enforces 12 calls / 120 s
 |     |
 |     +-- relay.py --ledger --rules ... -- sandbox-exec (network denied) REAL SERVER
 |           reads  $ARCI_WORKDIR/reply0-arm.json   which arm this trial is
 |           writes $ARCI_WORKDIR/ledger.jsonl      one line per call, written before
 |                                                  the reply is passed on
 |
 +-- arm command: agent.py --arm NAME --opening bad|clean ...
       1. writes reply0-arm.json
       2. opens the session and reads the tool list
       3. makes the scripted opening call
       4. hands the history to the model (Ollama, 127.0.0.1:11434 only)
       5. on the first response, persist the sent request and response status; then loop
       6. writes answer.json and finalises the same trial receipt

 after the agent has left:
   snapshot(task, workdir) -> {answer, ledger, world}   sealed by ARCI as final_state
   oracle(task, final_state) -> the answer matches the key, or not
```

The two arms of a pair differ in one argument of the arm command, `--arm`. Task, server
command, fault, budgets and rule are shared; in ARCI's schema only an arm's own command and
its environment differ between arms (checked on day 1, task C).

## 2. What day 1 already settled

| Fact | How it was checked | Where |
|---|---|---|
| A scripted agent runs through `arci run` with no model | 78 trials | `boundary-check/runs/` |
| Filesystem server: a good call is a harness error without the relay | run | `bc-fs-direct` |
| Relay rewrites N1, N4, N7 are needed on the real servers | run | `bc-fs-relay`, `bc-git-relay` |
| N2, N3, N5, N6, N8 work | stub server only | `stub_server.py` |
| The arm file reaches the relay; ARCI's record shows the rewritten text | 32 of 32 trials | `check_ledger.py` |
| Picking the server by arm (`--arm-on-server`) | stub server only | same |
| The ledger reaches the oracle through `snapshot` | run | `reply0_check.py` |
| The boundary kills the relay at the end of a clean trial | run; a line written on exit was lost | task C |
| All 72 tasks: bad reply, key, sentence, good calls, matching rule | re-run today at `$FX`, all hold | `tasks/check_tasks.py` |
| Both checkers on the 64 registered replies | run, network denied | `tasks/check/` |
| Registered projections, four retained-task designs | released `arci plan`, 128 fresh rows | `projections/` |

## 3. The relay (`harness/relay.py`, a port of `boundary-check/relay.py`)

Kept from the prototype: N1 strip the client capabilities roots, sampling and elicitation;
N2 answer a server's own request itself (ping with `{}`, anything else with -32601); N3 drop
server notifications; N4 add `isError: false` when the key is missing; N5 turn a JSON-RPC
error with another code into an `isError: true` result; N6 merge the pages of `tools/list`;
N7 show only tools marked `readOnlyHint: true` (order desk: the two named tools
`lookup_order`, `check_stock`) and refuse any other call; N8 drop a stdout line that is not
JSON; N9 give the server a small environment.

Changed for the study:

1. **Arm file.** `reply0-arm.json` holds `{"arm": LABEL, "rules": "naming" | "generic" |
   "none", "server": "shipped" | "edited"}`. The relay reads it when the first client
   message arrives. A missing or unreadable file makes the relay write a ledger line and
   exit, so the trial becomes a harness error; it never falls back to "no rewrite".
2. **Rule sets by name.** `--rules naming=FILE --rules generic=FILE`. A rule is `{tool,
   is_error, text_matches, when: {arg_present, arg_matches}, replace_text}`; `{arg:NAME}`
   and `{parent:NAME}` are filled from the arguments of that call and nothing else. `when`
   checks whether G1 received `start_timestamp`. F2 requires a successful `search_files`,
   complete text `No matches found` and a full pattern match of `^[A-Za-z0-9._-]+$`.
   Both implementations consume this single predicate and sentence from the F2 task record.
   Use tasks/f2_parity.py::relay_result for F2 naming in the production relay.
   This excludes minimatch extglobs, wildcard syntax, slashes and trailing newlines.
3. **What a rule changes.** The text of the text block, and a `structuredContent.content`
   string equal to the old text (the filesystem server repeats a successful text there).
   Never `isError`. It applies to every reply of the trial that fits, as an edit in the
   server would.
4. **Ledger.** One JSON line per event, flushed before the reply is passed on: `start` (the
   server's name, version, actual command and launched package/file digest),
   `arm`, `task` (the `key_id`), `norm` (which of N1 to N9 fired), `call` (number in the
   trial, tool, arguments, `server_reply` and `passed_on` as complete MCP result objects (including flags, blocks and structured content), the rule that
   fired or null), `refused` (a hidden tool was called). No times, no request ids, no trial
   folder path: the ledger is sealed inside `final_state` and must be the same on a repeat.
5. **Server by arm** for criterion (d). `--server shipped=JSON --server edited=JSON`; the
   real server is started only after the arm file is read; no `--rules` in those runs.
6. **No wire log** in registered runs, so a descriptor names no output path.

## 4. The agent (`harness/agent.py`, a port of `examples/ollama_mcp_agent/agent.py`)

Kept: the standard library only; the check that the only address ever called is
`http://127.0.0.1:11434/api/chat`, with no proxy and no redirect; the stdio MCP session
through the config file ARCI hands over; tool definitions built from `tools/list`; the
request body `stream: false, think: false, options: {temperature: 0.7}`; the tool text given
to the model with no error flag; exit code 75 when the model server cannot be reached (ARCI
counts that as ERROR, not as a failed trial).

Changed:

1. **Model.** `--model qwen3.5:4b-mlx-ctx32k` or `gemma4:12b-mlx-ctx32k`. The 32768 context
   is part of those tags, as in runs 2 to 6; the agent sends no context option and the
   wrapper checks the active context after the warm-up.
2. **Prompt.** The system prompt of `tasks/tasks.json` and, as the user message, the task's
   `ask` and nothing else. The task file the agent reads holds `key_id`, `cell`, `ask` and
   the two opening calls. The C0 server needs `order_id` in that shared task file. Construct
   messages from an allowlist: system prompt, registered ask and opening history. Never
   serialize the task object; keys, decoys, seed, arm and server-only fields stay out.
3. **Rewrite switch.** `--arm naming-sentence | reply-as-given | generic-sentence |
   edited-server | server-as-shipped | clean`. The agent turns it into the arm file (written
   to a temporary name, then renamed) before it opens the session. This is the only place an
   arm is chosen.
4. **Scripted opening**, and `--opening none` for the unscripted row (the agent makes no
   opening call, writes no tool message into the history and no sentence is passed on; the
   ledger alone says whether the model's own calls drew a reply fitting the cell's rule).
   After `tools/list` the agent makes the task's opening call itself
   through the session, so ARCI records it as the first call of the trial. `--opening bad`
   uses the registered bad call, `--opening clean` the first good call. It then puts into
   the history, in the shape the loop itself produces: the assistant message `{"role":
   "assistant", "content": "", "tool_calls": [{"function": {"name", "arguments"}}]}` and the
   tool message `{"role": "tool", "tool_name", "content": TEXT}`. The opening uses 1 of 12
   tool calls and 0 of 8 model steps. If the opening tool is not in the tool list the agent
   exits with code 70; the descriptor lists 70 and 75 as infrastructure codes.
5. **Control only (C0).** ARCI's fault empties the result after the relay, so the relay
   cannot replace it. With `--replace-empty-opening` and a sentence arm the agent replaces
   the opening's text, when it is empty, by the control sentence. In every other cell the
   agent changes no text. The candidate arm's text is the empty string, the maintainer's
   decision, and becomes the four characters `null` only if part (ii) of the wiring check
   (section 12) shows that Ollama refuses an empty tool text.
6. **Answer.** The last assistant message without a tool call goes to `answer.json` as
   `{"answer": TEXT}`; the agent exits 0. Out of steps: `{"answer": null}`, exit 0, which
   the oracle fails. A crash is left as a crash.
7. **Receipt.** Join by scheduled trial identity (including ARCI arm, even when both
   labels are clean). At the transport, capture the exact serialized first request bytes,
   digest, tool definitions and messages. As soon as the first response arrives persist
   those bytes and response status atomically, before parsing later steps. Capture later
   sent histories for delivery checks. Finalise the same receipt with step count, calls
   and answer. A timeout after response one must leave first-request evidence intact.
   Export exactly one record per trial; a missing or unanswered first request fails audit.
8. **Protocol.** The agent asks for 2025-11-25 with no client capabilities (the probe's
   setting; task C saw byte-identical tool results under 2026-07-28) and does not check the
   version that comes back (the order-desk bridge answers 2026-07-28).

`harness/offline_model.py` is the stand-in for checks without a model: a `chat` function
with three scripts, `corrected` (makes the good calls, then answers with the key),
`gives-up` (answers "I could not find it.") and `paste` (answers with the whole last reply).
It reads its plan from a file that only the checks write. The agent takes it through
`--offline PLAN`; the wrapper refuses to start a real run whose descriptor holds that flag.

## 5. Ledger, snapshot, oracle (`harness/reply0_oracle.py`)

- `snapshot(task, workdir)` runs in ARCI's grader after the agent has left. It returns
  `{"answer": ..., "ledger": [...], "world": ...}`: `answer.json` (missing means null),
  every line of `ledger.jsonl`, and for the order desk the bridge's `state.json`. A missing
  or broken ledger raises, so the trial is ERROR and not a silent fail.
- `passed(task, final_state)` looks the key up by `task["key_id"]` in
  `harness/answer_key.json` (written by `make_suites.py` from `tasks/tasks.json`; for C0 the
  expected string is `world.order.total_cents`) and returns `reply0_grade.passes(answer,
  expect, decoys)`. Nothing else: no retry count, no ledger content, no arm.
- Delivery is audited after the run (section 9), not inside the oracle. Every assigned trial
  stays in the decision, as in run 6.

## 6. The answer-key check

`tasks/check_tasks.py ENV_DIR OUT_DIR [FX_DIR]` runs with the registered fixture and no
model. Pin the manifest hash and compare the files, git head and clean worktree before
and after. Derive file keys from the requested CSV row and column, JSON field, numbered
item or uniquely matched labelled line; git keys come from read-only git commands. C0
starts the released bridge once per order at seed zero, passes its order_id, checks the
original lookup against the snapshot and grades its total. The run-time key is always
the actual trial's seeded order.total_cents. This rehearsal does not inject a fault.

The grader compares complete normalised answer lines, once each, in any order; a scalar
has one line. The registration specifies every normalisation and the raw length cap. An
alternative or negated contact fails even when it names the correct person. Check the exact
opening reply (including the ENOENT path), flag, key leakage, corrected calls, bare answer
and whole good-reply paste on every task. Pasting extra material or decoys fails. Either
single-branch reply consisting only of the expected name and whitespace legitimately passes.

For F2, `tasks/f2_parity.py` applies the registered relay rule to the shipped MCP result
and generates the in-server edit from the same task record in a temporary package copy.
`check_tasks.py` compares complete results from the two paths for every opening and later
nonmatching calls (including `absent?.txt`, an extglob and a trailing newline). The installed
package is read-only. Repeat through the actual harness paths before sealing.

Pre-freeze extensions, all offline:

- (8) Run the corrected, gives-up and paste stand-ins through both actual arms for all 72
  tasks. Verify the registered bare-key and full-reply outcomes including the git rows.
- (9) Probe actual edited packages and the production relay on opening and later calls.
  Compare all result fields after the same protocol normalisation, including structured
  content and error flags. Unrelated calls must retain the shipped result.
- (10) Keep the key file and task list outside every directory the servers may read.

## 7. The clean row (`harness/clean_row.py`)

`arci run` cannot run fewer than one pair, and refuses a suite of one round. So the clean
row is one plain pair run per task and model (`n_per_arm: 1`), both arms the same command
with `--arm clean --opening clean`: 72 tasks on 4B and 56 on 12B, 128 pair runs, 256 trials,
each sealed by ARCI. C0's clean row has no fault. The script then writes
`clean-row/kept.json`: per model and cell the tasks kept (at least one of the two trials
passed; an errored trial counts as not passed), the rounds that follow (8, 7, 6, 5 tasks
give 15, 18, 20, 24), "not run" below 5, and the seconds per trial. `make_suites.py` reads
that file. Consequence: the suite descriptors exist only after the clean row, so the
registration pins `make_suites.py`, `tasks/tasks.json` and the rule, the digests of the
descriptors go into the dated note of section 13, and the wrapper logs each descriptor's
sha256 before its run starts.

The unscripted row runs the same way, right after the clean row: `--arm clean --opening
none`, every eligible main task of G1, F2 and F1 on both models, 2 trials each, which is 8
tasks by 2 trials by 3 cells = 48 trials a model and 96 in all. It decides nothing. Its one
number, per cell and model, is in how many of its 16 trials the ledger shows a reply that
fits that cell's rule, read from the ledger alone and written into the result. The relay passes through unchanged. Assess rule matches offline.

## 8. Suites, the edited servers, the follow-up (`harness/make_suites.py`, `harness/edits/`)

One suite descriptor per run, in the form of run 6: `suite_id`, `tasks`, `oracle:
reply0_oracle:passed`, the two arms as commands, `mcp_server` (the relay command and
`snapshot: reply0_oracle:snapshot`), one condition, the rule (alpha 1/20, delta 1/10, stakes
1/4 and 1/2, `max_rounds` from the kept tasks, `max_errored_pairs: 4`, `scenario_seeds:
per_round`), budgets (12 tool calls, 120 seconds, grader 20 seconds; the 8 model steps are
the agent's own limit, because this agent calls Ollama directly and ARCI does not see its
model steps), and `prior_runs`.

| Run | Tasks | Baseline arm | Candidate arm | Relay |
|---|---|---|---|---|
| main cell (G1, F2, F1, F0, G2) | main | `naming-sentence` | `reply-as-given` | `--rules naming=` |
| control C0 | 8 orders | `naming-sentence` | `reply-as-given` | no rules; ARCI's fault `empty_result` on `lookup_order`, occurrence 0 |
| criterion (d) | held-out | `edited-server` | `server-as-shipped` | `--server`, no rules |
| generic follow-up | main | `naming-sentence` | `generic-sentence` | both rule sets |
| unscripted row | main | `clean --opening none` | `clean --opening none` | no text rewrites; score rule exposure offline |

Edited servers: `harness/make_edited.py` copies the installed package to
`reply0-env/edited/<cell>/`, applies `harness/edits/<cell>.diff`, and records the sha256 of
every file before and after; exactly one file may differ. The installed package is never
changed. For the filesystem server the edited copy lies **beside** `node_modules`, never
inside it, so neither Node's resolution nor the lockfile sees it.

- G1: `mcp_server_git/server.py`, the `git_log` tool (lines 1651 to 1654): when no commit
  came back and `start_timestamp` was given, return the sentence. Run with the copy first on
  the module path.
- F2: in the successful `search_files` handler of `dist/server.js`, after the unreadable
  directory diagnostic and before building the content blocks, apply exactly section 3's
  predicate and sentence, sourced from `tasks/tasks.json`. Use the section 6 reference
  edit; verify its diff and all fields before freeze.
- F1: `dist/server.js`, the handler of `read_text_file`: catch the error with code ENOENT
  and throw one whose message is the sentence. The handler is shared with the deprecated
  `read_file`; the edit must act for `read_text_file` only, as the relay rule does.

Each edit is more than a changed string (a condition is needed); the diff is published and
check (9) tests the reply. G1 and F2 edits are offline parity checks. Only F1 is eligible
for a held-out suite. Select one confirmation on the first model in 4B, 12B order with
a valid F1 BLOCK and at least five kept held-out tasks. The 12B screen has priority if
4B does not qualify, independent of G1/F2. A completed confirmation consumes the single
attempt even if it fails. Publish measured G1 and F2 on both models after valid C0.

## 9. The audit (`harness/audit.py`): were the fault and the reply delivered as intended

Build the expected trial IDs from the descriptor and schedule through the stopping round,
or both IDs of a plain pair. Join by identity, never by file order. Compare the schedule
against the sealed store, sealed ledger and first-request receipts, including interrupted
runs. Verify seals. Missing, duplicated or extra records invalidate the audit. Export to
`runs/RUN/audit.json`. Every trial stays in the counts.

| # | Required check |
|---|---|
| A1 | Exactly one envelope, ledger and receipt for every scheduled trial; no extras. A trial with no calls still needs a ledger showing startup. |
| A2 | Verify assigned arm, task, seed and actual opening name/arguments. Clean uses the first good call, unscripted has no fabricated history. |
| A3 | Obtain the exact shipped result independently of the ledger and agent, from the pinned fixture transcript or a fresh read-only fixture query (seeded world for C0). Verify server source, every content field and flag; a path prefix is insufficient. |
| A4 | From the registered call, exact result and scheduled arm apply the registered rule independently at every call. Verify ledger input, output and rewrite count. Test later calls against their own arguments; candidate and clean forward unchanged; generic uses its assigned template. |
| A5 | Compare the independently expected result with the sealed ARCI tool record after protocol normalisation. The C0 injection is checked separately below. |
| A6 | Hash the actual sent bytes, decode the first request and check its exact prompt, ask, opening and independently expected text, tool definitions and model options. Verify response receipt; compare later delivered tool history when sent. Never use ledger text as the expectation. |
| A7 | C0 faulted opening: ledger contains the correct original seeded lookup unchanged; ARCI records occurrence zero injected by empty_result with content []; actual first request holds the sentence for baseline, empty text (or the registered wiring fallback) for candidate. Later calls and clean C0 are unmodified. |
| A8 | (d): identify the actual launched package by pinned executable/module digest and arm assignment. Zero relay text rewrites over the entire trial. Independently expected edited/shipped text must agree in ledger, ARCI record and actual model history, respectively. |
| A9 | No crash; at most 5% wall timeouts per arm; count and show call/step budget failures. |
| A10 | Suites only: released arci gate must print “stored decision: MATCH”. Check the fixture for all runs. On plain clean/unscripted pairs verify the schedule, seals and the two independent counts; no gate comparison. |

R1 is the wrapper verification, R2 covers A1–A8, R3 is A9 and R4 uses A10. The counters
independently reconstruct counts and flag planted delivery faults as audit failures.
Before freeze plant a missing ledger/receipt (including a wholly missing scheduled trial),
an omitted baseline rewrite, consistent wrong candidate delivery, ledger-only tampering,
wrong ENOENT path/flag, missing C0 injection, wrong server or rewrite in (d), and a receipt
that disagrees with the sent request. Reseal the test copies. Require audit and both
counters to reject each case, and accept the intact controls. Kill the stand-in after its
first response and verify the first-request evidence survives.

Shown and never deciding: later calls to the same tool (any arguments; corrected arguments),
passes with and without one. Two count scripts must give the same file: `count_a.py` by the
harness author, `count_b.py` by another agent that is given only `harness/INTERFACE.md`.

## 10. The wrapper (`harness/run-reply0.sh`, after `run-6b.sh`)

`sh run-reply0.sh check` starts no trial. `sh run-reply0.sh real RUN` first checks the
registration, digest list and input versions against evidence of the pushed registration
commit (read-only git commands; an unverified local HEAD is insufficient). Verify the local
registered bytes against that commit. Enforce this before **every** live request path,
including wiring, warm-up and retries of the one explicitly amended wiring check. Before
deciding, verify the separately pushed descriptor note. Verify model/version/context,
fixture manifest, ARCI, Python and Node packages, and git 2.55.0 at /opt/homebrew/bin/git;
reject offline descriptors on the live path and enforce the registered run order.
The digest list must explicitly cover every executable study input including all files in
orderdesk/, fixture.py, probe.py, both invoked checker feeders and task-check scripts.
Fail closed on a missing required path even if the remaining listed hashes match.

Before warming, claim the canonical (model, cell, phase) slot by exclusive mkdir or
O_CREAT|O_EXCL. Derive it from the schedule (include task ID for plain pairs), never a
caller-chosen alias. Wiring has its own model slot. The claim survives every exit,
including interruption. Start the wrapper with `exec </dev/null`; every descendant
inherits closed-to-input stdin or a dedicated protocol pipe, never a caller's terminal.
Split wiring from scored-run admission: allow wiring only after push and require its
record before trials. Run one worker under caffeinate. Audit and run both counts afterwards.
Require gate MATCH only for suites. With a stand-in, test pre-push wiring/warm-up refusal, open caller stdin, competing
identical launches and a second launch after interruption. Expect zero unverified requests
and at most one winner. In a network-denying sandbox set REPLY0_NO_SANDBOX=1 to suppress
nested sandbox-exec; outside it the default confinement remains enabled.

Use neutral command paths before sealing. Build the publication tree solely from the
registration's explicit file allowlist; reject unlisted files, escaping paths or links.
Scan all assembled bytes, including logs and sealed stores, for personal paths. A failure
holds publication; never scrub a sealed store. No files from boundary-check/runs or
boundary-check/runs-repeat are published.

## 11. Files to write

| File (under `reply-0/`) | Job | Lines, about | From |
|---|---|---:|---|
| `harness/relay.py` | section 3 | 520 | port, 433 exist |
| `harness/agent.py` | section 4 | 430 | port, 340 exist |
| `harness/offline_model.py` | stand-in model for checks | 110 | pattern of run 6 |
| `harness/reply0_oracle.py` | snapshot and oracle | 120 | 45 exist |
| `tasks/reply0_grade.py` | the matching rule | see §6 | revised |
| `harness/make_suites.py` | descriptors, key file, rule files | 330 | 278 exist as pattern |
| `harness/clean_row.py` | section 7, and the unscripted row | 190 | new |
| `harness/wiring_check.py` | section 12, two requests a model | 90 | new |
| `harness/make_edited.py`, `harness/edits/*.diff` | section 8 | 130 + 45 | new |
| `tasks/check_tasks.py` | checks (8) to (10) added | + 150 | 243 exist |
| `harness/audit.py` | section 9 | 380 | pattern of run 6 |
| `harness/count_a.py`, `harness/count_b.py` | two counts | 200 each | pattern of run 6 |
| `harness/INTERFACE.md` | record formats, for `count_b` and blind tests | 60 | new |
| `harness/run-reply0.sh` | section 10 | 320 | port, 292 exist |
| `harness/tests/` | unit tests and no-model end-to-end tests | 650 | new |
| `reply0-digests.sha256` | sha256 of every file above and of the registration | made by script | new |

About 2,700 new lines, 3,800 in all, about 1,100 of them carried over from files that exist
(the registration says it the same way). Reused without further change: `fixture.py`,
`boundary-check/stub_server.py`, `orderdesk/orderdesk_world.py`, `checkers/`. Changed on day
1, after the review, and re-run: `probe.py` (a `--redact PATH=NAME` option, so no output
file carries a personal directory name), `run_probe.sh` and `tasks/run_checkers.sh` and
`checkers/run_verdicts.sh` (the environment directory is an argument now, not a constant),
`tasks/make_tasks.py` (F2's rule and sentence) and `tasks/check_tasks.py` (the fixture path
is an argument and must be a real path). Day-one hashes are historical. The registration digest list pins the revised inputs.

## 12. Checks before the freeze, all without a model, in this order

1. Unit tests: rules, `when`, arm file, ledger written before the reply; the opening and the
   first request with the stand-in; oracle and matching rule.
2. The stub matrix of task C on the ported relay (7 rows), plus a call to a hidden tool.
3. C0 behind the relay with the released fault: ARCI's record, the ledger and the receipt
   show what section 9 expects.
4. Check (8) for all 72 tasks; check (9) for the three edited servers; check (10).
5. One full rehearsal per server with the stand-in (`corrected` in one arm, `gives-up` in
   the other): BLOCK at round 2, audit clean, both counts equal, `arci gate` MATCH; first
   requests of the two arms equal except for the delivered text. Two negative controls of
   the same rehearsal: with `corrected` in both arms it gives PASS, and with the stand-ins
   swapped it gives no BLOCK. A rehearsal that blocks either way means the harness, not the
   reply, is deciding, and the freeze waits.
6. `ruff` and `basedpyright` clean; then the digest list, the filled registration, commit
   and push by the orchestrator.
7. The wiring check (registration, "Order of runs"): after the push and before the clean
   row, per model two requests with a made-up tool and an ask in no task, (i) a scripted
   call with a non-empty tool text and (ii) one with an empty tool text. It reads only the
   HTTP status and whether a message came back; the words are saved and published and never
   used. (i) failing stops everything until `harness/agent.py` is corrected, the
   registration amended and pushed once with the failed output, and the check repeated once.
   Only (ii) failing makes C0's candidate text the four characters `null`. This is the first
   time the scripted-call shape and an empty tool text meet a live model server, and the
   warm-up request (`Reply with OK.`, no tools) is the only other request before the clean
   row. Only then the clean row, and after it the dated descriptor-digest note.

## 13. The open points, and the decision on each

Every point below was open on the morning of 25 November. The maintainer decided them the
same day, after the hostile review. None is open now.

- **The fixture path. Decided: `$FX` is `/Users/Shared/arci-reply0/fx`.** It was
  `reply0-env/fixture` under the maintainer's home folder, which every ask and many replies
  carry, so the published stores would have carried the home folder's name. `/Users/Shared`
  is a real directory of macOS, outside `/tmp`, `/var` and `/etc` (links on macOS, and the
  server reports resolved paths), and neither it nor `arci-reply0`, `fx`, `fx/files` or
  `fx/repo` is a symbolic link. `fixture.py` built the same tree there and `manifest.json`
  kept its hash `9c0f4a2d…f1a84ea`, so no key, reply or sentence changed. The probe and
  `tasks/check_tasks.py` were re-run against it (72 tasks, all hold), the two checkers were
  re-run on the replies, and both scripts now take the path as an argument.
- **The control's empty text. Decided: the empty string, with one fallback.** It is what
  this path really delivers. If part (ii) of the wiring check (section 12) shows that Ollama
  refuses an empty tool text, and only then, the candidate text becomes the four characters
  `null`, and the result says so.
- **The shape of the scripted call. Decided: the wiring check settles it** before the clean
  row, and (i) failing stops the benchmark until the shape is corrected and the registration
  amended, pushed once with the failed output, and the check repeated once.
- **Strict (c), confirmed.** Both checkers must pass, at least one must have assessed the
  error text, and only a statistical F1 BLOCK passing R1–R4 qualifies. G1/F2 may satisfy
  (b); neither can complete a pass. After valid 4B C0, prioritise F1 on 4B, then 12B if
  needed. Confirm once as in section 8; another statistical BLOCK passing R1–R4 is required.
- **Criterion (a) on 4B only. Decided: yes, the 4B model only.** D-33 names no model; runs
  3, 4 and 6 were on 4B, and in run 2 the 12B model repeated all 120 empty lookups unaided.
  C0 on 12B is shown only.
- **Descriptor digests. Decided: a second, dated note**, pushed after the clean row and
  before the first deciding run, holding each descriptor's sha256 and nothing else. They
  cannot be registered earlier because the kept tasks set the rounds (section 7).
- **Not yet done by anyone:** the relay's refusal of a hidden tool, `empty_result` behind
  the relay, server-by-arm on a real server, any timing with a model. Task C's findings are
  saved: `boundary-check/FINDINGS.md` exists.
- **One thing the move did not reach.** `boundary-check/` still carries the maintainer's
  home path in 130 files: its `runs/` and `runs-repeat/` are sealed ARCI stores and the
  sha256 of each `manifests/*.yaml` is recorded inside them, so rewriting them would break
  the seal or make the record disagree with itself. Nothing under it is in the digest list
  the registration pins. The publication allowlist excludes these historical files.

## 14. Time

Day 2 covers the offline freeze checks, push, wiring and plain pairs. Before suites,
4B needs 144 clean + 48 unscripted = 192 trials; 12B needs 112 + 48 = 160. Eight kept
tasks allow 120 pairs; seven allow 126. Maximum 252 trials/suite. Fourteen suites bound
the budget at 352 + 14 × 252 = 3,880 trials. With six 4B and eight 12B suites, slow rates
of 5 and 20 seconds give ((192 + 6 × 252) × 5 + (160 + 8 × 252) × 20) / 3600 = 14.46
hours before timeout overhead. Up to 12 tolerated timeouts add 24 minutes per suite.
Use the measured clean-row timings for the deadline in the registration.

The 128 released `arci plan` rows in `projections/registered-rows.json` cover four retained
sizes and 32 rate pairs at independent agreement. Relative to 8 × 15, maximum changes
are bounded by 0.047 in verdict probability and 5.96 expected pairs. The per-cell 2.5%
bound gives at most 15% across six main cells. Under the joint null on F1 screens and
held-out sets, two screens and one fresh confirmation bound the false-confirmation path at
2 × 0.025 × 0.025 = 0.125%, conditional on the confirmation bound holding after selection.
The registration gives the subjective forecasts and limits the inference to the tested
model following a scripted missing-file call.
