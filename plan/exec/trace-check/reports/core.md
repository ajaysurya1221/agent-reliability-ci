# Trace-check core implementation report

Scope: `src/arci/trace_check.py`, `tests/unit/trace_check/test_core.py`, and this report.
The integrator owns Git, full-suite validation and independent review. No Git mutation,
network call, dependency change, frozen edit, user-module execution or runtime/gate/diff
change was performed in this lane.

## Behavior

- Exports the locked `check_traces` and `render_trace_check` API. Diagnostic statuses and
  exit codes are MATCH/0, DRIFT/1 and INVALID/3. JSON follows `arci-trace-check/1`.
- Reads each native store through `load_run`, derives the existing statistical decision,
  rejects ERROR, and resolves the selected trial through `build_schedule`.
- Compares declared task, seed, ordered faults, contract, budgets, execution kind,
  environment, full decision specification and opaque fixture identity using canonical
  bytes. IDs, labels, agent identity and statistical design may differ.
- Validates only selected events: boundaries, identity and sequence, payload types,
  unique starts, single linked finishes and canonical equality of unfinished calls before
  call-ID normalization. Supports multiple outstanding calls, failed partial traces,
  command traces without an agent result, a Python result followed by crash, and empty
  recordings despite completed tool events. No recording/event parity requirement.
- Keeps tool starts/finishes and agent results in order, removes wrapper metadata and
  top-level tool call IDs only, then appends terminal fields. Nested user metadata stays.
- Uses canonical bytes for both equality and recursive difference location. Full subtree
  SHA-256 values identify the changed data without printing it. A missing located subtree
  has a null kind and hash, distinguishing it from a JSON null value.
- Emits source trial outcomes and statistical decisions separately. Fixed limitations
  state the diagnostic, declaration, integrity and replay boundaries. Empty fixture
  identities add the declaration-only limitation. No files or step summaries are written.

## Test-first evidence

1. Before implementing the core, ran:
   `.venv/bin/pytest tests/unit/trace_check/test_core.py -x`
   Result: **1 failed in 0.08s**. The first real stored-fixture comparison failed because
   `arci.trace_check` did not yet exist. This was an intentional test failure, not a
   collection error.
2. After initial implementation, the same test file yielded **69 passed in 0.17s**.
3. Integration feedback requested missing-subtree kind semantics, matching trial-start
   fields, an empty terminal event payload and a singular optional agent result. Added or
   tightened tests first and ran:
   `.venv/bin/pytest tests/unit/trace_check/test_core.py -k 'start_payload_must or trial_end_payload_must or multiple_agent or missing_null'`
   Result: **6 failed, 68 deselected in 0.14s**, each on its intended assertion.
4. After those fixes, the file yielded **74 passed in 0.24s**. Additional regression
   coverage exercises the already-implemented generic comparison and validation paths.

## Final owned-path verification

Commands:

```text
.venv/bin/ruff format src/arci/trace_check.py tests/unit/trace_check
.venv/bin/ruff check src/arci/trace_check.py tests/unit/trace_check
.venv/bin/basedpyright src/arci/trace_check.py tests/unit/trace_check
.venv/bin/pytest tests/unit/trace_check
```

Final results: **All checks passed!**; **0 errors, 0 warnings, 0 notes**;
**93 passed in 0.24s**. No type-check ignores were added.

The tests include bool/int/float inequality in comparison and location; a real eight-hex
SHA-256 collision (`69235`, `95303`); missing/null and JSON Pointer escaping; nested user
metadata; order/tool/argument/result/terminal differences; invalid seals, schedule,
selection, events and scenario declarations; inconsistent unfinished calls; preservation
of source bytes and modification times; no step-summary writes; and MATCH with statistical
BLOCK or INCONCLUSIVE. Fixtures name unavailable user modules and executables, so successful
comparison does not rely on importing or executing them.

## Limits and handoff

This lane's test report is not independent acceptance evidence. The integrator must rerun
full-suite, frozen-file, installed-wheel, historical and hosted checks and conduct independent
review. The feature intentionally does not authenticate recorded execution, rerun an oracle,
validate replay consumption or infer statistical reliability from an exact trace match.
