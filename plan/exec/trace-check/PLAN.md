# Trace comparison implementation plan

Approved by the operator on 2026-11-03 in the Codex chat: implement the two-day
trace comparison plan, including a reviewed GitHub PR, conditional merge and
verification of main. No release, tag, dependency, outreach or frozen amendment.
Starting commit: `68cc861c222c180d1e2b2f103e141fc9047c4e9f`.

## Outcome

`arci trace-check BASE_RUN BASE_TRIAL CAND_RUN CAND_TRIAL [--format text|json]`
compares one selected observed tool/result trace and terminal state from each of
two native stores. Results are MATCH/0, DRIFT/1, INVALID/3. A diagnostic result is
not a statistical verdict, authentication or replay verification. Preserve the
independent oracle, statistical gate, exact replay consumption and historical data.

## Global constraints

- All 53 FROZEN.sha256 entries and the manifest itself remain byte-identical.
- No changes to schema, interfaces, runner, gate, stats, replay, storage, legacy
  diff, frozen acceptance tests, docs/design, historical reports or result stores.
- No dependencies, runtime network, user module imports or agent/oracle execution
  in trace-check. It writes no files, including GITHUB_STEP_SUMMARY.
- Workers own only their assigned files; the orchestrator owns Git and integration.
  Two code lanes maximum. Use the worktree's installed .venv tools, never uv.
- No source-checkout package leaks into installed-wheel tests; PYTHONPATH is cleared.
- Public docs call the feature unreleased/main-only; v0.8.0 remains unchanged.

## Comparison contract

Load each store with load_run, derive decide(manifest, trials), reject ERROR, and
resolve the unique selected trial against build_schedule. Do not call the writing
gate CLI. Require equal canonical task payload, seed, ordered selected faults,
contract, budgets, execution kind, declared environment, full DecisionSpec, and
opaque fixture identity. IDs/labels, agent identity and statistical design may
differ. Equal empty fixture identities carry a declaration-only limitation.

Validate selected events only: nonempty list; first/only trial_start and final/only
trial_end; matching trial_id; contiguous seq; payload types; nonnegative non-bool
occurrence; unique start call IDs; each finish links once to an earlier start of
the same tool; derived unfinished calls equal incomplete_calls before normalization.
Permit valid unfinished calls, zero-tool trials, command trials without agent_result,
Python result followed by process failure, and completed events with empty recording.
No event/recording parity check, oracle rerun or second replay validator.

Projection: ordered {kind,payload} of tool_start, tool_finish, agent_result. Omit
wrapper identity/timing and only top-level call_id on tool events. Preserve all
nested user data. Append terminal outcome, termination, agent_claimed_success,
contract, failure_fingerprint, failure_detail, final_state. Ignore model annotations
and non-tool RPC discovery recordings. Compare canonical bytes, including when
locating a difference: bool/int/float and missing/null stay distinct. Short display
hashes never decide equality. Report only full hashes and paths, no payload dumps.

## Locked integration interface

New arci.trace_check exports:

```python
def check_traces(
    baseline_run: Path | str,
    baseline_trial_id: str,
    candidate_run: Path | str,
    candidate_trial_id: str,
) -> TraceCheckResult: ...

def render_trace_check(
    result: TraceCheckResult, *, output_format: Literal["text", "json"] = "text"
) -> str: ...
```

TraceCheckResult has status (MATCH/DRIFT/INVALID) and exit_code (0/1/3).
JSON keys: schema_version (arci-trace-check/1), status, reason, baseline,
candidate, first_difference, limitations. Each available source identifies
experiment_id, trial_id, manifest_sha256, trial_sha256, decision_sha256,
trial_outcome, gate_verdict, gate_exit_code. Unavailable sources are null.
first_difference is null for MATCH/INVALID; otherwise contains step (zero-based
normalized step), path (JSON Pointer within that step), baseline_kind,
candidate_kind, baseline_sha256 and candidate_sha256. Missing sides have null
hash/kind. Canonical whole-subtree hashes distinguish missing from literal null.
reason and limitations are safe fixed messages, not raw exception/input payloads.
Text presents source outcomes/gate verdicts separately from diagnostic status.

## Ownership and dependencies

| Task | Owner | Files | Depends on |
|---|---|---|---|
| 1 brief/baseline | integrator | plan/exec/trace-check/** | approval |
| 2 core | Lane A | src/arci/trace_check.py; tests/unit/trace_check/** | 1 |
| 3 CLI/package | Lane B | src/arci/cli.py; tests/unit/cli/test_trace_check.py; .github/scripts/wheel_smoke.sh; .github/scripts/trace_check_smoke.py | 1 interface; 2 integration |
| 4 documentation | integrator | README.md below first screen; docs/ROADMAP.md; CHANGELOG.md; docs/recipes/trace-check.md | 1; validate against 2/3 |
| 5 review/delivery | integrator/reviewer | plan/exec/trace-check/**; fixes by owner | 2/3/4 |

## Acceptance and delivery

Tests cover normalized equality, exact tool/argument/result/order/terminal drift,
typed first-difference location, short-hash collision, all legitimate failure
forms above, invalid seals/schedules/events/scenarios, no source writes or code
execution, and unchanged existing behavior. Recipe must retain statistical
BLOCK/INCONCLUSIVE/ERROR even if trace MATCH; exact-path CI is opt-in/prespecified.
Installed-wheel smoke asserts real MATCH/0, DRIFT/1 and INVALID/3, JSON and no
source writes outside the checkout on Linux/macOS Python 3.11/3.14.

Merge bar: independent task and branch review; ruff format/check; strict
basedpyright; full pytest; frozen hashes; default report/figure/schema checks;
historical reproduction; all hosted CI at final candidate SHA. Open draft PR from
sprint/trace-check to main. Merge commit only after gates; verify resulting main
CI. Code/base changes invalidate prior acceptance. No bypass of permission denial.

## Time and adoption

Budget starts 2026-11-03T12:40:01Z. Day-one integration cut is 8 working hours;
feature freeze at 12 working hours; final deadline at 16 working hours. No need
to consume the entire budget if all gates pass sooner. If all three valid CLI
statuses do not work at the first cut, hold. Frozen/runner/statistical changes
require separate scope; unresolved final gates leave PR unmerged.

Deliver one human pilot worksheet: user-arranged consenting non-author, own
sanitized supported fixture, missing retry identified, benign drift and statistical
verdict interpreted correctly within 30 minutes; log assistance and source hashes.
Independent repeat use within seven days is later retention evidence. No available
participant means adoption unmeasured, never replaced by AI/maintainer evidence.
