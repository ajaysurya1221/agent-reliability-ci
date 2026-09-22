# Rules for coding agents in this repo

Read `src/arci/interfaces.py`, `src/arci/schema.py` and `docs/STATISTICS.md` first.

## Hard rules

1. FROZEN files are listed in `FROZEN.sha256`. Never edit, move or delete them. That covers
   `src/arci/{schema,interfaces,hashing,fingerprint,schedule,contracts}.py`, everything under `tests/acceptance/`,
   `pyproject.toml`, `uv.lock`, `justfile`, `AGENTS.md`, `docs/STATISTICS.md`, `docs/TRUST_MODEL.md`,
   `docs/design/**`. If a frozen file
   looks wrong, stop and say so in your final message. Do not work around it.
2. Edit only the files your brief says you own. Create new files only inside those paths.
3. Do not run git commands that change state (no add, commit, checkout, stash, reset). The
   orchestrator owns git.
4. No network. No new dependencies. Runtime code uses only the stdlib, `pydantic`, `pyyaml`.
5. Use `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/basedpyright`
   directly. Do not call `uv`.
6. The acceptance tests in `tests/acceptance/` are the source of truth for signatures and
   behaviour. Make them pass without touching them. Add your own tests under `tests/unit/<area>/`.
7. Finish with `ruff format`, `ruff check`, `basedpyright` clean on your files (strict mode;
   avoid `# pyright: ignore` unless unavoidable, and explain each one).
8. Your final message: files changed, test command and its last lines, anything you could not do,
   risks. No long logs. Your report is not acceptance evidence; the orchestrator re-runs checks.

## Semantics that tests rely on

- Trial outcome: `PASS` iff the oracle says success AND there is no hard violation. Agent crash,
  uncaught `ToolFault`, timeout, budget exhaustion, oracle-says-no = `FAIL`. Harness fault, grader
  exception, `ReplayMiss` = `ERROR`. Every scheduled trial produces exactly one sealed envelope.
- Determinism: for the same `TrialSpec`, everything except volatile fields
  (each model's declared `VOLATILE` set in `arci.schema`) must be identical, so `record_sha256` is stable. Call ids are
  `c-0000`, `c-0001`, ... in call order. No wall-clock data, pids, temp paths or tracebacks in
  non-volatile fields. `failure_detail` is one deterministic line.
- Randomness: derive every RNG from the spec seed with string namespaces, e.g.
  `random.Random(f"{seed}:agent")`, `random.Random(f"{seed}:fault:{name}")`.
- The schedule is `arci.schedule.build_schedule(manifest)`; `TrialEnvelope.spec_sha256` is
  `arci.schedule.spec_sha256(spec)`. Never re-derive either.
- Events: `trial_start`, then `model_step` / `tool_start` / `tool_finish` in order, then
  `agent_result` (if the agent returned), then exactly one `trial_end`, which the PARENT
  synthesises if the child died or was killed before sending it. `seq` is 0..n-1 with no gaps.
  `tool_start` payload: `tool`, `call_id`, `occurrence`, `arguments`. `tool_finish` payload:
  `tool`, `call_id`, `ok`, `value`, `error_kind`, `injected_by`. The child writes each event to the
  parent as one JSON line and flushes immediately; the parent is the ONLY writer of files.
- Injected calls count toward `max_tool_calls`. The call that would exceed the budget raises
  `BudgetExceeded` before any `tool_start` is emitted.
- Perturbations: `tool_timeout` and `tool_error_once` short-circuit in `before()` with
  `ok=False` (`error_kind` "timeout" / "error"), which the ToolBox raises to the agent as
  `ToolFault`. `empty_result` rewrites the real result's `value` to `None` in `after()`.
  A fault fires only when `tool` matches (None = any) and `occurrence == at_occurrence`
  (None = 0).
- Failure fingerprints use `arci.fingerprint.fingerprint(kind, detail)`:
  oracle failure: kind `"oracle"`, detail
  `"oracle rejected final state; first_failed_tool=<tool>:<error_kind>"` or `...=none`;
  crash: kind `"crash"`, detail = exception type and message; timeout: kind `"timeout"`;
  budget: kind `"budget"`; hard violation: kind `"invariant:<name>"`.
- The child process must be able to import `"module:function"` targets that live in the repo
  (including `tests.acceptance.fixture_agents`): launch it with `sys.executable` and pass the
  parent's `sys.path` through `PYTHONPATH`. Kill the whole process group on timeout.
- REPLAY mode never executes live tools and never re-applies perturbations: it serves recorded
  results verbatim (including injected ones). Because recorded results do not mutate the
  environment, the trial is graded on `spec.replay_final_state`, and only if the agent consumed the
  recording exactly (every recorded call, in order, nothing left over). A miss OR leftover
  recording => outcome `ERROR`, termination `replay_miss`. The ToolBox must latch a replay miss in a
  flag the agent cannot clear: an agent that catches `Exception` must not turn a miss into an
  ordinary failure.
- A raising toolset factory or an unresolvable agent reference is a harness fault (`ERROR`,
  `harness_error`). A raising or unresolvable oracle is `ERROR`, `grader_error`.
- Bundles are portable: `make_bundle(manifest, trial, spec, *, root=None, include=())` embeds each
  `include` path (relative to `root`) as base64 in `files` and its sha256 in `fixtures`. `replay`
  first checks every embedded file against `fixtures` (mismatch => `INVALID`, nothing executed),
  writes them to a temp dir, and puts that dir FIRST on the child's import path.
- `replay(bundle)`: bad seal (including a nested one) => `INVALID`. `tool_mode` REPLAY serves results from
  `spec.recording` keyed by (tool, sha256 of canonical arguments, occurrence); a miss raises
  `ReplayMiss` => `INVALID`. `tool_mode` RECORD in a bundle means "run live against the seeded
  fixture environment" (used to show a repaired agent no longer fails). `REPRODUCED` iff outcome
  and fingerprint both equal the bundle's expectations.
- The gate counts a success as `outcome is PASS`. See `docs/STATISTICS.md` for the rule.

## Hardening semantics (checkpoint 2; see docs/TRUST_MODEL.md and tests/acceptance/test_hardening.py)

- `run_trial` NEVER raises and ALWAYS returns one sealed envelope, whatever the child writes.
- Latches, all checked in finalisation on EVERY termination path, in this precedence:
  replay mismatch (miss or leftover recording) > harness fault > grader fault > budget > the rest.
  The agent must not be able to clear them by catching exceptions: a caught `BudgetExceeded` still
  ends as FAIL/budget, a caught injector exception still ends as ERROR/harness_error, a caught
  `ReplayMiss` still ends as ERROR/replay_miss. Keep latch state out of the agent's easy reach
  (closure or name-mangled), and send a per-trial random nonce with every protocol line so stray
  writes to fd 1 are recognised as junk rather than accepted as results.
- An exception raised by a perturbation's `before`/`after`, or by boundary validation, is a harness
  fault (ERROR/harness_error), never a `ToolFault`.
- `FaultSpec.name` may be a registered name or a `"module:function"` factory reference
  (`(FaultSpec) -> Perturbation`), resolved in the child.
- Protocol robustness: the parent reads BYTES, splits on newlines with a bounded line length,
  decodes each line separately (`errors="replace"`), and validates every frame: nonce, kind,
  event-specific payload shape, trial id, contiguous `seq`. Valid events received before a bad frame
  are kept. Any invalid frame makes the trial ERROR/harness_error. The reader thread always signals
  completion, even on exceptions.
- The child's final result frame is buffered by the parent and accepted only if the process then
  exits with status 0 before the deadline. Non-zero exit after completion => FAIL/crash. Still
  running at the deadline => FAIL/timeout. The parent emits exactly ONE `trial_end`, itself, after
  termination is settled; the child never emits `trial_end`. Persisted events always equal the
  envelope's events.
- The deadline (`budgets.max_seconds`) is monotonic, starts before the spec is written to the
  child's stdin (write it from a thread), and runs through process exit. No fixed waits.
- Cleanup is unconditional (try/finally): kill the whole process group after EVERY trial, including
  successful ones, close pipes, reap the child.
- An exception from `emit_event` is a harness fault: stop the worker, return ERROR/harness_error.
  `run_experiment` must surface store write failures the same way.
- Values crossing the boundary are deep-copied both ways: what the agent receives, what is
  recorded and what is emitted are three independent copies. Same for replayed results.
- Grading never runs in the caller's process: `python -P -m arci.grade` (a new module you own)
  reads one JSON request on stdin (contract, events, task, final_state), writes one JSON
  `ContractResult`, and is killed at `budgets.grader_seconds`. Timeout, non-zero exit or unparsable
  output => `grader_error` with a fixed deterministic message. The parent never imports oracle,
  agent or toolset modules and never mutates its own `sys.path` / `sys.modules`.
- Children are started with `sys.executable -P` (no implicit cwd on the import path) and a
  `PYTHONPATH` that is: bundle payload dir first (replay only), then the parent's `sys.path`.
- Bundle payload keys must be relative POSIX paths with no `..` segment and no leading `/`;
  otherwise `replay` returns INVALID before writing anything. The temp dir is always removed.
- `arci.stats.clopper_pearson_tail(successes, n, tail)` inverts each side at `tail` directly and is
  accurate to 1e-9 absolute for tail >= 2.5e-7 and n <= 10000 (use log-space survival sums for the
  small tail; closed forms at x=0 and x=n). `clopper_pearson(x, n, confidence)` delegates with
  `tail = (1 - confidence) / 2`. The gate passes `tail = alpha / (4K)` directly and never recovers
  it from a rounded confidence.

## Second hardening round (final review; tests/acceptance/test_hardening2.py)

- `run_trial` has a last-resort guard: ANY exception escaping its own logic becomes a sealed
  ERROR/harness_error envelope. It also validates the contract itself
  (`arci.contracts.validate_contract`); a rejected contract is ERROR/harness_error.
- Values crossing the boundary must be canonical JSON (finite numbers, UTF-8 encodable text; check
  with `arci.hashing.canonical_json`). If the AGENT passes a bad value (tool arguments or
  `note_model_step` payload) the ToolBox raises `ValueError` to the agent before emitting anything:
  uncaught, that is FAIL/crash. If the ENVIRONMENT or an injector produces a bad value it is a
  harness fault. The parent re-validates every frame, so nothing unsealable is ever accepted.
- Everything the harness does around a tool call (building the call, `before`, validating the
  hook's return type, the live call's bookkeeping, `after`, validating its return type, deep copies,
  recording, event emission) is inside the harness-fault guard, and the guard catches
  `BaseException` from injectors (including `SystemExit` and `KeyboardInterrupt`). A hook returning
  the wrong type is a harness fault.
- Latches are reported to the parent IMMEDIATELY as authenticated protocol frames
  (`{"latch": "harness_error" | "budget" | "replay_miss", "detail": ...}`), flushed at the moment
  they trip, and held in parent-owned state. Precedence when finalising, whatever happens later
  (hang, hard exit, crash): replay mismatch > harness fault > grader fault > budget > timeout/crash.
- `trial_end` is emitted by the parent with an EMPTY payload. The verdict lives only in the
  envelope, so a sink failure while delivering `trial_end` cannot make persisted events disagree
  with the sealed envelope: events already handed to the sink are never rewritten.
- The grader (and the worker) are awaited on PROCESS EXIT, never on pipe EOF: read what is available
  and return once the process has exited; at the deadline kill the group, close the pipes, reap, and
  do not drain further. A detached descendant holding stdout must not delay either path.
- REPLAY mode never constructs perturbations.
- The protocol queue between the reader thread and the supervisor is bounded (backpressure on the
  child), and the supervisor still enforces the deadline while the reader is blocked.
- `arci.gate.decide` never raises: any exception while validating or computing (including an
  unsupported `alpha`, `delta`, `n_per_arm` on a typed copy, or an unsupported tail for K conditions)
  yields a sealed `ERROR` decision with a short reason.

## Third hardening round (release re-check; tests/acceptance/test_hardening3.py)

- An injector (or its factory) raising ANYTHING is a harness fault, including the boundary's own
  exception types (`ToolFault`, `BudgetExceeded`, `ReplayMiss`). Latch `harness_error` around each
  `before`/`after`/factory invocation for every `BaseException` BEFORE anything propagates to the
  agent. Injected faults reach the agent only through a returned `ToolResult`.
- Diagnostics are formatted by ONE safe helper used by worker, toolbox and runner: it never raises
  (an exception whose `__str__` raises gets a fixed fallback such as `"<unprintable ExcType>"`),
  it returns one line, and it replaces anything not UTF-8 encodable, so a latch frame or an
  envelope can always be sent and sealed.
- Child stdout (worker AND grader) is drained concurrently while the supervisor watches process
  exit and the deadline. Never wait for exit before reading: a response larger than the pipe buffer
  must not deadlock. Never wait for EOF after exit or after the deadline.
- `decide` must survive absurd typed values (`10**400`, `inf`, `nan`) in `alpha`, `delta`,
  `n_per_arm`: the ERROR decision's own fields fall back to finite, sealable defaults.

## v0.2: command agents behind the MCP boundary (docs/design/0002-out-of-process-boundary.md; tests/acceptance/test_mcp.py)

- A `TrialSpec` is a python trial (`agent` + `toolset`) or a command trial (`command` +
  `mcp_server`). `run_trial`, `make_bundle`, `replay`, `minimize_faults`, `run_experiment` accept
  both through the SAME signatures. Python trials must keep behaving exactly as before.
- Process layout for a command trial (both children are supervised by the parent with the existing
  deadline, process-group kill, nonce-authenticated frame reader, latch precedence, single parent-
  emitted empty-payload `trial_end`, and last-resort guard):
  1. a trial directory with a SHORT path (unix socket paths are limited to about 100 bytes; create
     it under `/tmp` with `tempfile.mkdtemp(prefix="arci-", dir="/tmp")`), always removed;
  2. `sys.executable -P -m arci.mcp_boundary`: harness-owned. Reads its config (spec, nonce, socket
     path, workdir) as ONE JSON document on stdin. In RECORD/LIVE mode it starts the real server
     (`mcp_server.argv`, placeholders `{workdir}`, `{seed}` and `{task_file}` expanded,
     `mcp_server.env` merged, `ARCI_WORKDIR`, `ARCI_SEED` and `ARCI_TASK_FILE` set; the task file
     is `<trial dir>/task.json`, written by the parent before the boundary starts), listens on the socket, accepts exactly one connection,
     relays newline-delimited JSON-RPC both ways, and intercepts `tools/call`. It writes the same
     authenticated frames the v0.1 worker writes (events, latches, final result with `recording`)
     to ITS stdout. It prints a ready frame once the socket is listening; the parent starts the
     agent only after that.
  3. the agent: `command.argv` with `{mcp_config}`, `{task_file}`, `{workdir}`, `{seed}` expanded,
     `command.env` merged, plus `ARCI_MCP_CONFIG`, `ARCI_TASK_FILE`, `ARCI_WORKDIR`, `ARCI_SEED`.
     cwd is the trial directory. `task_file` holds the task JSON. `mcp_config` is
     `{"mcpServers": {<mcp_server.name>: {"command": sys.executable,
     "args": ["-P", "-m", "arci.mcp_shim", "--socket", <path>], "env": {}}}}`.
     Its stdout/stderr are captured and discarded (bounded), never parsed.
  4. `arci.mcp_shim`: relays bytes stdin->socket and socket->stdout, exits when either side closes.
     No logic, no imports beyond the stdlib.
- Expanded paths never enter sealed records: events carry tool name, arguments, result; never the
  workdir, socket path, pids or JSON-RPC ids. `spec_sha256` is over the UNEXPANDED spec.
- Tool events: only `tools/call` produces `tool_start`/`tool_finish`. `tool_start` payload as
  before (`tool`, `call_id` c-0000.., `occurrence`, `arguments`). `tool_finish.value` is the MCP
  result object verbatim (for a JSON-RPC error: `{"error": <error object>}`); `ok` is
  `not isError` and no JSON-RPC error; `error_kind` is `"mcp_error"` for a
  JSON-RPC error, the perturbation's kind for an injected one, else null.
- Supported subset and fault mapping are in the design note. A `resultType` other than
  `"complete"` (or absent), a server-initiated request (sampling, elicitation), or a second
  `tools/call` while one is in flight latches `harness_error` with a fixed detail string. A server
  that cannot be started, or exits before the agent is done with it, is `harness_error`.
- Perturbations reuse `arci.perturb` through `ToolCall`/`ToolResult`; `before()` short-circuits into
  an `isError: true` result whose single text content is `"arci injected <error_kind>"`; `after()`
  may rewrite `value` (for `empty_result`: `content` becomes `[]`).
- Budget: the call that would exceed `max_tool_calls` gets an `isError: true` result
  `"arci: tool budget exceeded"`, is NOT forwarded, emits no tool events, and trips the `budget`
  latch. `usage.tool_calls` counts forwarded and injected calls.
- Outcome for command trials: agent exit 0 => `agent_claimed_success` True, termination
  `completed` (then graded); non-zero exit => FAIL/crash; deadline => FAIL/timeout; latches keep
  their precedence. `final_state` comes from `mcp_server.snapshot(task, workdir)`, executed inside
  the existing grader subprocess BEFORE the oracle, with the same deadline; a raising, hanging or
  non-dict snapshot is a grader fault. The trial directory must still exist while grading.
- Recording for replay: every server response the agent received, in order. `tools/call` exchanges
  as `RecordedCall` (tool, arguments_sha256, occurrence, result with `value` = the MCP result).
  Non-tool exchanges (`initialize`, `tools/list`, `ping`) are recorded too, as `RecordedCall` with
  `tool` = `"rpc:<method>"`, `arguments_sha256` over the canonical params, their own occurrence
  counters, and `value` = the JSON-RPC `result`. REPLAY mode never starts the server, serves all of
  these from the recording by (tool, arguments_sha256, occurrence), rewrites only the JSON-RPC
  `id`, and enforces exact consumption (miss or leftover => `replay_miss`).
- Determinism: for a scripted client the envelope must be identical across runs. Do not record
  timing, ids or anything derived from the trial directory.

## v0.2 hardening (pre-release review; tests/acceptance/test_mcp_hardening.py)

- Exit/result race (seen as 18 of 72 trials `boundary exited before returning` on a loaded
  machine): observing that a child exited is NOT evidence that its frames have been consumed.
  After exit, drain everything already written to the pipe (non-blocking reads until it would
  block or EOF, and the reader thread's queue) BEFORE deciding that a result is missing. Do not wait
  for EOF (a detached descendant may hold the pipe). Apply this to the boundary, the worker and the
  grader paths alike. No outcome may depend on scheduling luck.
- Classification in the command path, in both directions:
  - the AGENT's protocol mistakes are the agent's problem: malformed JSON-RPC from the client, a
    `tools/call` whose `arguments` is not an object, an unknown tool, reuse of an id that is still
    outstanding. The boundary answers with a JSON-RPC error (-32600 / -32602 / -32601), forwards
    nothing, emits no tool events, trips NO latch, and carries on. A client that disconnects early
    is not a harness fault either;
  - the ENVIRONMENT's mistakes are harness faults: a server response that is not valid JSON-RPC
    2.0 (version, id type, exactly one of result/error), a `tools/call` result whose `content` is
    not an array or whose `isError` is not a boolean, a JSON-RPC error with code -32603 (internal
    error) or any code outside {-32600, -32601, -32602}, non-JSON on the server's stdout, a server
    that exits early;
  - the BOUNDARY's own abnormal exit (non-zero, or before a final frame) is a harness fault and
    outranks the agent's crash or timeout. A deadline that passes before the boundary was ready is
    a harness fault too.
- The boundary allocates its OWN upstream request ids and maps them back, so client ids (string or
  integer, reused after completion or not) never collide with each other or with injected replies.
- Replay consumption is enforced by the PARENT: the boundary streams an authenticated progress
  frame each time a recorded exchange is consumed, and the parent finalises `replay_miss` on EVERY
  termination path (including deadline kills) unless the consumed count equals the recording
  length. Unverified consumption is never REPRODUCED.
- No synchronous write may block the loop that reads: use non-blocking I/O with bounded per-
  destination output queues (or a writer thread per destination), keep draining every direction,
  and keep enforcing the deadline and latches under backpressure. Two pipelined 300 KB requests with
  700 KB responses must complete.
- The recording is streamed to the parent as it is made, one authenticated frame per exchange
  (chunk anything larger than the frame limit), and assembled by the parent. The final frame
  carries no recording. There is no limit on a trial's total recording size other than memory.
- The bridge (`arci.mcp_toolset_server`): an exception RAISED by a tool is `isError: true` with a
  diagnostic formatted by the shared safe formatter AND scrubbed with
  `arci.fingerprint.normalise` (no run-specific paths or numbers in recorded text). A tool that
  RETURNS something that is not canonical JSON is a broken environment: answer with JSON-RPC error
  -32603, which the boundary treats as a harness fault. Snapshot write failures are -32603 too.
- The Ollama example: both URL openers reject redirects; `main` returns non-zero when the step
  limit is exhausted without a final answer.
- Infrastructure failures: if a command agent exits with a status listed in
  `command.infra_exit_codes` (default `(75,)`, EX_TEMPFAIL) the trial is ERROR/harness_error with
  failure_detail `"agent reported an infrastructure failure (exit <code>)"`, ranked like any other
  harness fault. Any other non-zero exit stays FAIL/crash. The Ollama example returns 75 when the
  model backend is unreachable, times out, or the model is missing, and 1 for its own bugs.

## v0.4: group-sequential looks (docs/STATISTICS.md "Sequential looks"; tests/acceptance/test_sequential.py)

- `Manifest.looks` (validated in the frozen schema) is the plan; `looks == ()` means `(n_per_arm,)`
  and MUST reproduce today's fixed-design results exactly (same bounds, same verdict, same
  `per_arm_confidence`), with `history` of length 1 and `stopped_at_look == 1`.
- `decide` (pure, never raises): L = number of looks; K = gating conditions; per-look tail
  `alpha/(4KL)` (Clopper-Pearson) or Wilson confidence `1 - alpha/(KL)` (Newcombe). For j = 1..L:
  take, per declared condition, the trials whose pair index is `< N_j`; compute every condition
  exactly as today (ArmStats, bounds, hard violations, ceiling => descriptive) and the experiment
  verdict for that look; record a `LookDecision` (its `trials_sha256` is over the trials through
  that look). Stop at the first look whose verdict is PASS or BLOCK; that is `stopped_at_look` and
  the decision's `conditions`/`verdict`. If none is decisive, the last look decides
  (INCONCLUSIVE). THEN validate the store against the stopping look: the trial set must be exactly
  the schedule's trials with pair index `< N_stop` for every condition (both arms, all conditions
  including ceiling ones), all seals valid, identities matching, no extra trials; otherwise the
  decision is ERROR with reason `"trial set does not match the stopping look"`. A store whose
  trials end at some `N_j` where looks 1..j were all INCONCLUSIVE and j < L is ERROR (`"stopped
  without a decision"`); a store that is not a whole-pair prefix at a declared look is ERROR. Any
  trial ERROR, seal failure or manifest problem is ERROR as before (`stopped_at_look = 0`).
- `run_experiment`: build the FULL schedule once (never rebuild with a smaller n_per_arm). Run it
  in stages: stage j = the trials of every condition with pair index in `[N_{j-1}, N_j)`, submitted
  to the executor together; wait for all of them; write them to the store; call `decide` on the
  trials so far; stop if the verdict is PASS or BLOCK (or ERROR). Return the trials run. The
  runner must import `arci.gate` lazily inside the function.
- `bench/selfcheck.py`: `sequential_characteristics(p_a, p_b, looks, *, alpha=0.05, delta=0.10,
  k=1, method="clopper_pearson", rho=0.0) -> dict` with keys `PASS`, `BLOCK`, `INCONCLUSIVE`,
  `expected_trials` (both arms, i.e. 2 x expected pairs) by EXACT enumeration over sequential
  paths: keep a dict of surviving probability mass keyed by cumulative `(x_a, x_b)`; advance one
  pair at a time through the four paired outcomes (independent arms when rho == 0; the bench's
  shared-uniform mixture with weight rho otherwise); at each registered look absorb the mass of
  states whose verdict (from the per-look `_verdict_table` at that N) is PASS or BLOCK. At most
  (N+1)^2 states. `looks=(n,)` must equal `operating_characteristics` to 1e-9. Add `--looks
  50,100,200` to the CLI: prints the table for both scenarios sets, and a boundary sweep as for the
  fixed design (worst false-PASS on/below the boundary and false-BLOCK on/above, <= alpha or exit
  non-zero). Keep the whole bench under two minutes.
- Report/CLI: the Markdown report gains a "Looks" table (look, pairs, verdict, bounds per
  condition) when there is more than one look, and states the stopping look.

## v0.5: the decision boundary (tests/acceptance/test_decisions.py, test_decisions_sdk.py, test_hero_decisions.py)

Read `docs/design/0003-decision-boundary.md` and `docs/design/jev-research-2026-09-22.md` first.
A "decision" is one HTTP request from the agent to a System One endpoint (`POST /v1/systemone`,
TypeSafe's Jev API). The boundary process serves that endpoint on loopback for command agents.

- Configuration: `Manifest.decisions: DecisionSpec | None` (frozen in `arci.schema`), bound into
  every `TrialSpec` by the schedule, so it is inside `spec_sha256`. Command agents only.
- Listener: when `spec.decisions` is set, the boundary binds a TCP socket on `127.0.0.1`, port 0,
  BEFORE emitting `ready`, and the `ready` frame carries `"decision_port": <int>`. The parent then
  sets, LAST (after merging `spec.command.env`, so the harness always wins),
  `TYPESAFE_BASE_URL=http://127.0.0.1:<port>` and `TYPESAFE_API_KEY=<decision token>` in the
  agent's environment. The token is `secrets.token_hex(16)` generated by the parent, passed to the
  boundary in its config as `"decision_token"`, and unrelated to the protocol nonce. It never
  appears in any event, record or frame.
- Lifetime: with decisions configured, MCP EOF (the shim closing the socket) no longer stops the
  boundary. The boundary runs until the parent stops it; the parent signals it as soon as the agent
  has exited (no half-deadline grace), and the existing "own signal is not a fault" rule applies.
  A decision that arrives after the MCP session closed is served and recorded normally.
- HTTP/1.1, one request per connection: parse the request line, headers and a `Content-Length`
  body inside the existing selector loop (non-blocking reads, bounded by `max_body_bytes`); reply
  with `Connection: close` and a JSON body. Chunked bodies get 411. Only `POST /v1/systemone` and
  `GET /v1/models` exist; anything else is 404. Local rejections are served deterministically,
  NOT recorded, NOT budgeted, emit no events and set no latch: 401 (bearer != token), 404, 411,
  413 (body over `max_body_bytes`), 422 (body not a JSON object; `state` not str/object/array;
  `model` not a str; `questions` not a non-empty object; a question whose `type` is not
  noul/choice/score, whose `criteria` has the wrong shape, a choice with 0 or >255 options, a
  score with <2 or >10 levels). Extra top-level keys are allowed and forwarded. The 422 body is
  `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`.
- Serial: a second decision connection accepted while one is open, or a decision while a
  `tools/call` is in flight (or the reverse), is a harness fault: "concurrent decision requests
  are unsupported" (the offending request is answered 500 `{"detail": "arci: ..."}`).
- Admitted POST = one tool call under the reserved name `arci.schema.DECISION_TOOL`
  (`decision:systemone`): `ToolCall(call_id=f"c-{n:04d}", tool=DECISION_TOOL, arguments=<the body
  exactly as received>, occurrence=<count of prior admitted POSTs>)`, using the SAME call counter
  and budget as MCP tool calls (`budgets.max_tool_calls`) plus `decisions.max_decisions`. Over
  either budget: latch `budget`, answer 403 `{"detail": "arci: decision budget exceeded"}`, emit
  no `tool_start`. Otherwise emit `tool_start`, run before-perturbations, upstream, after-
  perturbations, record, emit `tool_finish`, answer. The `ToolResult` is `ok = (status == 200)`,
  `value = {"status": int, "headers": {<allowlisted lower-case names>: str}, "body": <JSON>}`,
  `error_kind = f"http_{status}"` when not ok, `injected_by` when a perturbation produced or
  rewrote it. The header allowlist is `retry-after` only. Deep-copy in both directions.
- Upstream `fixture`: import `spec.decisions.fixture` in the boundary (trusted code) and call it
  with (the received body with `model` replaced by `spec.decisions.model`, `spec.seed`,
  occurrence) in a worker thread; the loop keeps serving and enforces `request_seconds`. Raising,
  exceeding the time limit, or returning an invalid body is a harness fault (ERROR); the agent gets
  500. Upstream `http`: `POST {base_url}/v1/systemone` with `Authorization: Bearer
  $TYPESAFE_API_KEY` taken from the BOUNDARY's own environment (a missing key is a harness fault
  at the first decision), body = received body with `model` pinned, timeout `request_seconds`,
  no proxy, no redirects, no retries. Upstream 200 -> validate; 422 -> pass through as a not-ok
  result with the upstream body; 401/403, 429, any 5xx, connection or timeout errors, or a
  non-JSON body -> harness fault. `GET /v1/models` is forwarded the same way (fixture upstream
  answers `{"models": [{"name": <pinned>, "description": "arci fixture", "release_date":
  "2026-09-15"}]}`); it is recorded under `decision:models` with arguments `{}` like an `rpc:`
  exchange (no tool events, no budget).
- Response validation (before AND after perturbation): object with `model == pinned`,
  `usage.input_tokens`/`output_tokens` ints, `answers` whose keys equal the requested question
  names; each answer's `type` equals its question's; choice: `choice` is one of the criteria
  keys, `probabilities` keys equal the criteria keys, finite, non-negative, summing to 1 within
  1e-6, `choice` has the maximal probability, `confidence` finite in [0, 1]; noul: `noul` finite
  in [0, 1]; score: `probabilities` and `legend` keys are "0".."L-1" for L levels, probabilities
  as above, `score` finite, `confidence` finite in [0, 1]. Everything must be canonical JSON.
- Perturbations (registered in `arci.perturb`; params validated by the schema):
  `decision_low_confidence` (after; fires when `call.occurrence == at_occurrence`, default 0):
  for every choice answer with n >= 2 options let c = (n * max_p - 1) / (n - 1); if c > cap
  (`confidence_max`, default 0.4) set t = 1 - cap / c and p' = (1 - t) * p + t / n for every
  option (ranking and `choice` unchanged, sum stays 1), and `confidence` = cap; if c <= cap leave
  the answer alone. Nouls and scores are never touched. Set `injected_by` whenever the fault
  matched, even if nothing changed. `decision_unavailable` (before; fires for every POST with
  `occurrence >= at_occurrence`, default 0): no upstream call; result ok=False, status 529, body
  `{"detail": "arci injected unavailable"}`, `error_kind="http_529"`. Generic perturbations
  (`tool_timeout`, `tool_error_once`, `empty_result`, module factories) NEVER see decision calls,
  even with `tool=None`; decision perturbations never see MCP calls.
- Replay: the same (tool, arguments sha256, occurrence) matching, same `replay_progress` frames,
  same exact-consumption rule; the recorded `value` is served back as the HTTP response
  (`status`, allowlisted headers, body). No upstream, no fixture import, no perturbations.
  `decision:models` entries replay the same way.
- Reserved names: an MCP `tools/list` result advertising a tool whose name starts with `rpc:` or
  `decision:` is a harness fault; `tools/call` on such a name is a client error (-32601).
- `arci.diff.step_signature` for a `tool_start` whose tool starts with `decision:` prints
  `tool=... occurrence=... arguments#<_value_digest(arguments)>` (never the state); the
  `tool_finish` signature is unchanged (status is inside `value#digest`; add `status=` too).
- Events, seals, fingerprints, minimiser, bundles, the gate: unchanged. `first_failed_tool` in an
  oracle fingerprint may therefore read `decision:systemone:http_529`.
