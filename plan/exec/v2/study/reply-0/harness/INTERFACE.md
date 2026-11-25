# Reply-0 producer and counter interface

Use released ARCI 2.4.1. The registered inputs are UTF-8 JSON. JSONL has one object per line. Compare parsed JSON values, preserving array order, every content field, explicit nulls and exact strings, including newlines. A byte digest is lowercase hexadecimal SHA-256. The fixture root `FX` is the real path `/Users/Shared/arci-reply0/fx`. The registered task-list SHA-256 is `76ee13ca3c4eaa54514ae4c08cef1cc75e93e81c8b43ac4073dee5e267b922a1`. The fixture manifest SHA-256 is `9c0f4a2dcfaf924b46228be3a0d8dfe2248517bf9039302c44103dc63f1a84ea`.

## Inputs and commands

Run from the study directory. `E` contains `py/bin/python`, `node/node_modules` and an empty `home/`. Use real, neutral installation paths for published stores. Export `PYTHONDONTWRITEBYTECODE=1`. With enclosing network denial export `REPLY0_NO_SANDBOX=1`. Otherwise the relay prepends `sandbox-exec -p '(version 1)(allow default)(deny network*)'` to the server argv. Filesystem and git serve only `FX/files` and `FX/repo`. The order desk exposes only two lookups into its seeded world.

```sh
P="$E/py/bin/python"
export PYTHONPATH="$PWD/harness"
"$P" -B harness/make_suites.py "$E" --inputs-only
"$P" -B harness/make_edited.py "$E" --out "$EDITED"
"$P" -B tasks/check_tasks.py "$E" "$CHECK_OUT" /Users/Shared/arci-reply0/fx
"$P" -B -m unittest discover -s harness/tests/core -p 'test_*.py'
"$P" -B harness/tests/core/check_c0.py
```

`tasks/tasks.json` supplies `system_prompt`, `generic_sentence`, and `cells[CELL]`. Each cell has `main[]`, `held_out[]`, `tool`, `sentence`, and server identity. Its rows have unique `id` and `key_id`, `ask`, `bad`, an ordered nonempty `good[]`, `expect[]`, `decoys[]` and a source. Replace literal `{FX}` in the task strings. Every call is `{"name":STRING,"arguments":OBJECT}`.

The generator writes `harness/answer_key.json` indexed by key_id. Each value is `{"expect":[STRING,...],"decoys":[STRING,...],"world_key":null}`. In C0, expect is empty and world_key is `"order.total_cents"`. Key and full task list live outside all served roots. The public task has exactly `key_id, cell, ask, bad, clean`, plus `order_id` for C0. The value of `clean` is the first good call. In a suite descriptor each task also has `id`, which ARCI strips from its runtime task file.

For a suite, read the clean-row input as `kept[MODEL][CELL]["main"|"held_out"]["kept"]`, a list of registered task IDs, retained if either clean trial passed. Select them in registration order. Counts 8, 7, 6 and 5 give 15, 18, 20 and 24 rounds respectively. A smaller set yields no descriptor. The wrapper admits one confirmation on the first qualifying F1 screen in 4B, 12B order with at least five kept held-out rows. Preparing a descriptor does not establish that qualification.

```sh
"$P" -B harness/make_suites.py "$E" --cell F1 --model 4B --phase clean --task-id F1-n1 --out "$OUT/clean.yaml"
"$P" -B harness/make_suites.py "$E" --cell F1 --model 4B --phase main --kept "$KEPT" --out "$OUT/main.yaml"
"$P" -B harness/make_suites.py "$E" --cell F1 --model 4B --phase confirmation --kept "$KEPT" --edited "$EDITED" --out "$OUT/held.yaml"
```

`--phase unscripted` takes one main task from F1/F2/G1. `--phase generic` takes a kept main set. `--prior-run ID` is repeatable. Use 4B for all cells, 12B for C0/G1/F2/F1. Plain rows are one pair per task. Every suite uses one condition, alpha 1/20, delta 1/10, stakes 1/4 and 1/2, per-round seeds and four tolerated errored pairs. Every trial has a 12-call, 120-second budget, 20 seconds for grading and an agent limit of eight chat requests.

For offline rehearsals append **both** `--offline-baseline /absolute/B.json` and `--offline-candidate /absolute/C.json` to the generator command. Each plan is indexed by key_id. An entry is `{"script":"corrected"|"gives-up"|"paste","good":[CALL,...],"expect":[STRING,...],"world_key":null|"order.total_cents"}`. Corrected and paste first execute all good calls, one per response. Corrected answers with newline-joined expect, or the actual last lookup's total for C0. Paste answers with the entire last good text. Gives-up immediately answers `I could not find it.`. The same transport captures the bytes in every mode. The real-run wrapper must reject any descriptor containing `--offline`.

```sh
# D is an offline descriptor prepared above. Use a new receipt directory for each run.
export REPLY0_RECEIPTS="$OUT/receipts"
"$P" -B -m arci run --workers 1 --out "$OUT/stores" "$D"
"$P" -B -m arci gate "$STORE"
```

The generator uses JSON in `.yaml` descriptors. Both commands run the same `agent.py --mcp-config {mcp_config} --task-file {task_file} --arm LABEL --opening bad|clean|none --model TAG --prompt PROMPT --run-id RUN`. An offline command also has `--offline PLAN`. The runner sets `ARCI_WORKDIR, ARCI_SEED, ARCI_TASK_FILE`. Each command's static environment sets `REPLY0_ARCI_ARM=baseline|candidate`. It distinguishes identical clean commands. Infrastructure codes are 70 (unadvertised opening) and 75 (backend unavailable). The two model tags are `qwen3.5:4b-mlx-ctx32k` and `gemma4:12b-mlx-ctx32k`.

## Arm selection and MCP ledger

The agent atomically writes `ARCI_WORKDIR/reply0-arm.json` before starting the MCP client. The file contains exactly `{"arm":LABEL,"rules":SET,"server":WHICH}`. The relay reads it on the first client message, launches the selected server and records each event in `ledger.jsonl` before forwarding the corresponding reply. A missing or unreadable arm file writes an error record and ends the process. There is no default assignment.

| Phase | Baseline label | Candidate label | Opening and delivery |
|---|---|---|---|
| Main | naming-sentence | reply-as-given | bad, naming vs none, both shipped |
| C0 main | naming-sentence | reply-as-given | bad, both none/shipped, ARCI injects empty_result at lookup_order occurrence 0 |
| Generic | naming-sentence | generic-sentence | bad, naming vs generic, both shipped |
| F1 confirmation | edited-server | server-as-shipped | bad, both none, edited vs shipped |
| Clean | clean | clean | clean, both none/shipped, no fault |
| Unscripted | clean | clean | none, both none/shipped, no fault |

The relay accepts `relay.py --ledger [--env NAME=VALUE]... [--allow-tool NAME]... [--rules naming=FILE] [--rules generic=FILE] -- SERVER_ARGV...`. For server selection replace the final separator and command with `--server shipped=JSON_ARGV --server edited=JSON_ARGV`. A selectable git copy also takes `--module-root edited=DIRECTORY` to put its package first on the server module path. In the registered order desk the explicit allowlist is lookup_order and check_stock. For other cells use the server's readOnlyHint exactly equal to true. Each edited directory contains CELL/package and CELL/digests.json with `cell,patch_sha256,before,after`. Before/after map every package-relative filename to its byte digest. The filesystem package and a node_modules dependency link are siblings. Exactly one handler changes.

Each ledger row has discriminator `record`. There are no clocks or RPC IDs. One completed startup has one arm, task and start. Normalisation rows may intervene. A call's 0-based seq counts forwarded tools/call requests only.

| record | Other fields |
|---|---|
| arm | arm, rules, server, as in the arm file |
| task | key_id string |
| start | argv (actual argument array, with trial folder and task-file arguments represented by literal `{workdir}`, `{task_file}`), module_root (PYTHONPATH string or null), sha256 (object), protocolVersion and serverInfo from initialize |
| norm | code (N1 through N9), detail (string). N7 filtering and N9 carry names (string array). Several norms may apply per call. |
| call | seq integer, tool string, arguments object, server_reply and passed_on complete objects, rule null or `naming:0` / `generic:0` (0-based rule index) |
| refused | tool, arguments. Relay returns JSON-RPC -32601 without forwarding. |
| error | reason string. Invalid startup. |

Start.sha256 always includes `executable`. For filesystem it also includes `index.js` and `server.js`. For git it includes every immediate Python module under its selected `mcp_server_git/` package with that prefix. For the order desk it includes `arci/mcp_toolset_server.py` and `orderdesk_world.py`. Stub keys include its script basename. Verify these bytes against the pinned environment and published edit manifests. Use argv and module_root to identify the actual launch. A server may report the same name/version in both arms.

A server_reply is the original result **before** normalisation, including absence of fields. A JSON-RPC error is represented by `{"error":ERROR_OBJECT}`. N1 removes roots, sampling and elicitation capabilities. N2 answers a server ping with an empty object and other server requests with -32601. N3 drops server notifications. N4 inserts isError=false when absent. N5 maps a tools/call JSON-RPC error outside -32600/-32601/-32602 to `{"isError":true,"content":[{"type":"text","text":ERROR_MESSAGE}]}`. N6 fetches all tools/list pages. N7 filters or refuses. N8 drops non-object/non-JSON stdout. N9 supplies the small server environment. Apply N4/N5 before the assigned text rule. Compare ARCI to the complete passed_on object, subject to the C0 exception.

One rule file per cell and set under `harness/rules/CELL-SET.json` contains an ordered array of objects with `tool,is_error,text_matches,when,replace_text`. Independently derive it from the registered cell's tool, reply_is_error, reply_pattern, optional sentence_when (default {}), and sentence or top-level generic_sentence. At every call require the named tool, identical error flag, and a single text block. Apply regex search to that text. F2 additionally requires full matches on the whole text and pattern argument. The guards `when.arg_present[]` require non-null values, and `when.arg_matches` maps names to regexes that must fully match string values. Substitute `{arg:NAME}` or `{parent:NAME}` from this call only, using POSIX dirname. Change the text field of that block and, if equal to the original string, structuredContent.content. Preserve every other field. With no match, pass the complete normalised object unchanged. Unscripted exposure uses exactly this predicate on the raw call/result, independent of the arm's rules setting.

## Receipt, answer and grade

Export exactly one JSON file per trial into the run's REPLY0_RECEIPTS directory. Filename is `SHA256(json.dumps([RUN,key_id,seed,arci_arm],separators=(",",":")).encode("utf-8")) + ".json"` with Python's default ASCII escaping. RUN is the descriptor experiment_id for a plain pair, suite_id for a suite. Match on all four fields. The first send creates the file exclusively. Updates use a temporary sibling, flush, fsync and atomic replace.

```json
{"run":"check-C0-c1-corrected","key_id":"C0-c1","seed":0,"arci_arm":"baseline","arm":"naming-sentence","opening":"bad","steps":1,"calls":[{"name":"lookup_order","arguments":{"order_id":"ORD-103"}}],"answer":null,"complete":false,"exchanges":[{"request_b64":"Li4u","sha256":"ab5df625bc76dbd4e163bed2dd888df828f90159bb93556525c31821b6541d46","status":200,"response_b64":"Li4u","done_reason":"stop"}]}
```

The example encodes three placeholder dots in each byte field. Each exchange represents one attempted request. Decode standard base64 and verify SHA-256 against the **decoded request bytes**. The producer serialises once with UTF-8 `json.dumps(payload,ensure_ascii=False,allow_nan=False)`. The same bytes go to the transport. Status and response_b64 start null and are persisted immediately on response, before JSON parsing. A killed agent can leave complete=false, including after a successful first response. A missing or unanswered first request fails delivery audit. Steps is the number of attempted exchanges. Calls is an ordered list including the scripted opening. In a partial receipt it is current through the last persisted update. For completed trials compare all calls and answer to the other records.

Decode the first body. Its exact keys are `model,messages,tools,stream,think,options`. Stream and think are false. Options is exactly `{"temperature":0.7}`. There is no seed or context override. Build tools in advertised order from independently retrieved normalised tools/list. Each entry is `{"type":"function","function":{"name":NAME,"description":DESCRIPTION,"parameters":INPUT_SCHEMA}}`, defaulting description to the name for a non-string and missing inputSchema to `{"type":"object"}`. The agent requests MCP 2025-11-25 with capabilities {}.

Messages begin with `{"role":"system","content":system_prompt}` then `{"role":"user","content":ask}`. For a scripted opening append `{"role":"assistant","content":"","tool_calls":[{"function":CALL}]}` and `{"role":"tool","tool_name":NAME,"content":TEXT}`. Unscripted starts with only the first two. TEXT joins the text fields of text blocks with a single newline, preserving internal and trailing whitespace. Flags and structuredContent are absent from messages. A protocol error instead yields `MCP RPC error: ` plus the Python representation of the error object. Later requests append the prior response's exact message and one tool message per function call in order.

Both C0 arms record and forward the original seeded lookup. In the faulted pair ARCI retains the result object, replaces content with [] and marks injected_by=empty_result. The first request presents the control sentence on baseline and the empty string on candidate. Only the registered wiring fallback allows `"null"` on candidate (`--empty-fallback-null`). Both faulted commands take `--replace-empty-opening SENTENCE`. Later lookups, clean C0 and every non-control use the delivered text. Validate the original lookup by independently running the released order-desk bridge with **this trial's seed and order_id**.

The last message without tool_calls must supply string content. A malformed response is an infrastructure error. Exhausting eight steps writes null. The agent writes `answer.json` as `{"answer":STRING_OR_NULL}` and finalises its receipt. Snapshot returns exactly `{"answer":STRING_OR_NULL,"ledger":[ROW,...],"world":OBJECT_OR_NULL}`. Missing answer yields null. A missing/broken ledger raises a grader error. C0 world is the bridge's state.json with order_id, order (sku, total_cents, refunded_cents, notes), stock. Other cells have null world.

Score the answer only. C0 expect is the decimal string of world.order.total_cents. Others use the key entry. Reject non-string answers and strings longer than 600 raw Unicode characters. Strip leading/trailing whitespace, splitlines, normalise each full line and sort. Normalise with NFKC, casefold, split/join whitespace with single spaces, strip surrounding characters from the set ASCII space, straight or curly single/double quotes, backtick, ()[]{}. Remove one terminal period, then strip wrappers again. Remove commas only for full regex `[0-9]{1,3}(?:,[0-9]{3})+`. Require a nonempty expected list, equality of sorted normalised lines including multiplicity, and zero intersection with normalised decoys. Extra prose, blank internal lines and duplicate answers fail. Of the 72 full final good replies, only the two G2-b4 variants already consist of the bare answer.

## Independent audit and counts

1. In `STORE=OUT/stores/EXPERIMENT_ID` read manifest.json, trials.jsonl, events.jsonl and decision.json. Suite experiment_id is suite_id@rule_sha256. Verify the pinned descriptor and compiled manifest, then every record seal using the released model's validate_seal(). Use `arci.schedule.build_schedule` for plain manifests (`arci/0.5`), or `arci.suite_schedule.build_suite_round` for each round 1 through decision.stopped_at_round (`arci-suite/1`). Check the first decisive round and the cap. Compare expected and observed multisets in both directions. At interruption a wholly missing scheduled trial is still missing. An incomplete store cannot substantiate a valid result.
2. Join trial envelopes by experiment_id/trial_id. A plain trial_id is `CELL:00000:baseline|candidate`. Suite IDs are `rNNNNNN:TASK_ID:CELL:baseline|candidate`. Match task_id, pair_id, arm, variant, seed and released `arci.schedule.spec_sha256(spec)`. Join receipt by the scheduled run, key_id, integer seed and side. A label alone is ambiguous. Reject duplicate JSONL IDs, extra/missing receipts, missing ledger or startup, and mismatches. The sealed final_state contains the ledger. Compare separately exported events grouped by trial_id and seq to the envelope's events. Drop no trial from counts.
3. A tool_start payload holds call_id, tool, arguments, occurrence (prior calls to this tool). Join its tool_finish by call_id. Finish holds tool, ok, value (complete MCP result), error_kind and injected_by. Match envelope.recording entries by tool, occurrence and arguments_sha256 (released arci.hashing.hash_record(arguments)). Their result also holds the complete value and flags. Exclude `rpc:` entries when counting tool calls. Use the independent fixture for every original reply by repeating a read-only query of the pinned shipped server or using the verified exact opening object in the checker's tasks.check.json (replace literal `$FX` with FX). Determine the expected edit from the scheduled call and registered rule. For confirmation, the edited server's expected reply already contains that text and every relay rule is null. Verify all fields, source digest and zero rewrites. For C0 check the three distinct deliveries above.
4. Compare actual sent histories, byte digests, statuses and decoded responses to those independent expectations on **all** arms. Count a retry once per trial with a later call to the scripted opening's tool. Count a corrected retry once if a later call matches one of the task's registered good calls with that same tool and exact arguments. Report successes with and without each. For unscripted trials report exposure (any call that matches the registered rule) and denominator, with no fabricated opening. For each arm report total, PASS, FAIL, ERROR, terminations, 120-second timeouts, tool budget exits, and completed eight-step exhaustions (null answer after a final response requesting tools). Show by task, cell and model. A crash or more than 5 percent wall timeouts on either arm invalidates the run's interpretation. Keep failures and errors in the denominator.
5. Pair by pair_id. If either side errored increment errored. Otherwise increment minus, zero or plus according to candidate PASS indicator minus baseline PASS indicator. Compare these counts to suite decision.history at round boundaries. Four errored pairs are tolerated. For suites require released `arci gate STORE` to print `stored decision: MATCH`. For a plain pair verify both envelopes and both counts. Verify fixture file hashes, git head and clean worktree before and after. A delivery mismatch fails the audit even when all stored seals verify.

A blind test can clone evidence, change one independently checkable fact and reseal the copies using released ARCI record constructors. Include a missing scheduled trial, missing receipt, missing ledger, omitted rewrite, consistent wrong candidate text, wrong ENOENT path or flag, wrong C0 injection, wrong edited source, a rewrite in confirmation, and a receipt contradicting the sent body. Each should fail the corresponding independent comparison. Setting `REPLY0_CHECK_TRANSPORT=stdio` runs the matrix with the released boundary's serial handlers over anonymous pipes and produces component recordings. A sealed run uses the default transport. The checker's `standins.check.json` states which one ran.


### Counter interchange

For the two downstream counters, use `count_{a,b}.py STORE --receipts DIR --check-dir CHECK_OUT`. Emit a single UTF-8 JSON object on stdout, serialised with Python `sort_keys=True, ensure_ascii=False, separators=(",",":"), allow_nan=False` and one terminal newline. Send diagnostics to stderr. Return zero for a verified count, nonzero for an invalid or unverifiable input. A finding does not delete any scheduled observation. Consumers can display partial counts separately from the verified output.

The root fields are `experiment_id,model,cell,phase,pairs,arms`. Model is the full tag and phase is `main|clean|unscripted|confirmation|generic`. Use the registered commands and opening to identify the phase. The control uses main. Pairs is an object with integer fields `minus,zero,plus,errored`. Arms maps baseline and candidate to `{"label":LABEL,"all":COUNTS,"by_task":{TASK_ID:COUNTS,...}}`. Every COUNTS object has the same fields, including zeroes:

```json
{"trials":0,"passed":0,"failed":0,"errored":0,"by_termination":{},"wall_timeouts":0,"call_budget":0,"step_exhausted":0,"same_tool":{"yes":{"trials":0,"passed":0},"no":{"trials":0,"passed":0}},"corrected_same_tool":{"yes":{"trials":0,"passed":0},"no":{"trials":0,"passed":0}},"unscripted_exposed":0,"unscripted_trials":0}
```

Use observed termination strings only in by_termination. Increment wall_timeouts for termination timeout and call_budget for budget (the command uses no boundary model steps). Count step_exhausted only on completed receipts ending at eight steps whose last assistant message requested tools and whose final answer is null. Count yes/no retry groups for scripted trials only. Use the ledger's later forwarded calls after seq zero. Count unscripted trials and exposures only when opening=none. For clean rows the first good call defines the opening tool. An empty denominator is retained as zero. Count all successes from sealed outcome=PASS and independently verify the answer grade whenever the oracle ran.

## Round 3 additions

**Opening evidence.** Every checker row carries the full shipped `original_result` and its registered `bad_call`. The checker transcript has SHA-256 `80aff1c9fb3f14d094e20a17594bda672183bd4c93e071c8802263ea2ba5d64a`. The audit requires all registered task IDs exactly once. At a scripted non-C0 bad opening the shipped reply must equal that row and satisfy the registered predicate. The edited F1 arm must return the corresponding registered edit before the relay. C0 rows record the seed-zero reference. Live C0 verification queries the bridge for the scheduled pair's own seed.

**Requests and outcomes.** The trial transport takes `(step, body, capture)`. It passes the final immutable bytes to `capture` at the body write. The stand-in independently hashes the bytes it parses and returns `received_sha256` beside `message`. The offline audit checks this against each successful HTTP exchange. Live receipts attest to the client's HTTP body write. A final assistant message requires string `content`. Invalid backend responses retain the raw response in the partial receipt and return infrastructure exit 75. A valid empty string remains an answer.

**Count A.** Its command verifies the schedule, seals, checker transcript, original and delivered replies, sent history, offline receiver digest, response shape, answer and observed contract violations through `audit.verify`. Count A itself tallies the verified observations and compares pair counts to the stopping history. Count B supplies the independent delivery and grade implementation.

**Live admission.** Use the repository at `/Users/Shared/arci-reply0/checkout` and `REPLY0_ENV=/Users/Shared/arci-reply0/env`. All model and cell slots use `/Users/Shared/arci-reply0/claims`. Test processes can set `REPLY0_CLAIMS` before importing the launcher. A live run rejects any override. The orchestrator writes `push-receipt.txt` in the claims directory from the remote's answer. Its single line is `<40-lowercase-hex commit> refs/heads/v2/phase0`. The registration commit must be reachable from the origin tracking ref. The registration, digest list and each repository input must equal that commit's blobs. The later descriptor note retains its own push check.

**Claim lifetime.** An exclusive study lock covers admission, wiring or warm-up, execution and post-run verification across both models. Each admitted trial slot also has an exclusively locked `claim.json`. Before warm-up the launcher writes the private `schedule.json` with the registration and descriptor digests, the released scheduled trial identities and a hash of a random capability. Only the runner inherits `REPLY0_LAUNCH_TOKEN`; every live trial send checks it, both digests, the active lock, the receipt directory and the trial binding. The two lock waits each allow 30 seconds. Each audit or count subprocess group has 1,800 seconds. Expiry exits nonzero and retains the consumed slot and partial files.

**Wiring and publication.** Both successful wiring responses select the empty string. HTTP 400 or 422 with a response explicitly rejecting empty text selects `null` after a successful nonempty probe. An inconclusive empty probe holds the run. The scanner reads the operator's home, login and Git identities at runtime, checks raw and decoded JSON strings, and decodes nested payloads and base64 bodies. Rejected files stay in their original sealed location. The offline checker selects the registered Node binary from the environment or PATH by SHA-256 and keeps its generated candidate digest list in its proof directory.
