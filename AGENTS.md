# Rules for coding agents in this repo

Read `src/arci/interfaces.py`, `src/arci/schema.py` and `docs/STATISTICS.md` first.

## Hard rules

1. FROZEN files are listed in `FROZEN.sha256`. Never edit, move or delete them. That covers
   `src/arci/{schema,interfaces,hashing,fingerprint,schedule,contracts}.py`, everything under `tests/acceptance/`,
   `pyproject.toml`, `uv.lock`, `justfile`, `AGENTS.md`, `docs/STATISTICS.md`, `docs/TRUST_MODEL.md`. If a frozen file
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
