# Compare recorded tool behavior across runs

**Availability: v1.0.0.** Install `agent-reliability-ci==1.0.0`.
The PyPI package and Action tag **v0.8.0 do not contain `trace-check`**.
The commands below use only packaged fixtures after installation; no model or API
key is needed. Use Bash, POSIX, and the same environment for `python` and `arci`.

`arci trace-check BASE_RUN BASE_TRIAL CAND_RUN CAND_TRIAL [--format text|json]`
reads two native ARCI run stores and identifies the first difference in their
selected normalized traces. It does not execute agents or oracles, write to either
store, or write `GITHUB_STEP_SUMMARY`.

| Diagnostic | Exit | Meaning |
|---|---:|---|
| `MATCH` | 0 | The selected normalized recorded views are identical. |
| `DRIFT` | 1 | Those views differ. Inspect the first difference. |
| `INVALID` | 3 | A store, selected trace, or scenario comparison is unsupported or invalid. |

These are separate from the statistical `PASS`, `BLOCK`, `INCONCLUSIVE`, and
`ERROR` verdicts. `MATCH` establishes neither reliability nor authenticity, safety,
or successful replay. `DRIFT` can be an intentional behavior change; it does not
prove a regression or its cause. Declare any exact-path CI requirement before
observing candidate results, especially when model behavior is nondeterministic.

For automatic paired-failure selection within one store, start with
[`arci triage`](triage.md). The command below retains explicit cross-store selection.

## 1. Create two offline stores

Use a new or empty `trace-demo` directory. This runs the existing six-step demo,
including its statistical and replay checks, and retains the stores:

```bash
arci demo --workers 4 --keep trace-demo
export BASE_RUN="$PWD/trace-demo/runs/arci-demo-agent_a-reserve-timeout-200"
export CAND_RUN="$PWD/trace-demo/runs/arci-demo-agent_b-reserve-timeout-200"
```

Select a seed where removing the retry caused a failure. This script reads the
stores; it neither edits records nor selects a new statistical experiment. All
trials remain in their original gate denominators.

```bash
read -r BASE_TRIAL SAME_TRIAL CAND_TRIAL < <(python - <<'PY'
import os
from arci.schema import Outcome
from arci.storage import load_run

_, base = load_run(os.environ["BASE_RUN"])
_, candidate = load_run(os.environ["CAND_RUN"])
base_by_pair = {t.pair_id: t for t in base if t.arm == "baseline"}
same_by_pair = {t.pair_id: t for t in candidate if t.arm == "baseline"}
failing = sorted(
    (t for t in candidate if t.arm == "candidate" and t.outcome == Outcome.FAIL
     and same_by_pair[t.pair_id].outcome == Outcome.PASS),
    key=lambda t: t.pair_id,
)
trial = failing[0]
print(base_by_pair[trial.pair_id].trial_id,
      same_by_pair[trial.pair_id].trial_id, trial.trial_id)
PY
)
export BASE_TRIAL SAME_TRIAL CAND_TRIAL
test -n "$BASE_TRIAL" && test -n "$SAME_TRIAL" && test -n "$CAND_TRIAL"
```

## 2. Compare the same agent, then the missing retry

The first command compares agent A's recorded behavior across two different
experiments. Expect `MATCH` and exit 0, even though the second experiment's gate
is `BLOCK` because its candidate B is worse. The second command compares A with
B at the same seed. Expect `DRIFT` and exit 1 at the retry/next-call difference.

```bash
arci trace-check "$BASE_RUN" "$BASE_TRIAL" "$CAND_RUN" "$SAME_TRIAL"
trace_status=0
arci trace-check "$BASE_RUN" "$BASE_TRIAL" "$CAND_RUN" "$CAND_TRIAL" \
  --format json >trace-drift.json || trace_status=$?
test "$trace_status" -eq 1
cat trace-drift.json
```

The JSON format is `arci-trace-check/1`. `baseline` and `candidate` identify the
selected records with full manifest/trial hashes, original trial outcomes, and
the freshly re-derived decision hash, verdict and exit code. A missing or invalid
source may be `null`. `first_difference` is `null` for `MATCH`/`INVALID`; for
`DRIFT` it gives the zero-based normalized step, a JSON Pointer within that step,
event kinds, and full hashes of the differing values. A missing side has a null
kind/hash, distinct from a recorded JSON null. Payloads are not dumped by default.
`<missing>` in text, or a null kind/hash in JSON, means the **pointed value** is
absent; its containing event may still exist.

To name the changed behavior, inspect the selected trial's `events` in
`trials.jsonl` at the reported normalized step. Count only `tool_start`,
`tool_finish`, and `agent_result` events, from zero; the final step is the terminal
record assembled from the trial's outcome and final-state fields. Read the tool
name and the indicated field on each side. The first pointer can name an argument
key even when the tool itself changed, because fields are compared in sorted key
order. Default hashes locate the difference without exposing raw values; targeted
record inspection is still needed to interpret those values. Reading a recorded
command or endpoint declaration does not require executing or contacting it.
For a terminal step, `/payload/outcome` refers to the selected trial's `outcome`,
and the other terminal fields follow the same mapping.

## 3. Keep statistical and trace exits independent in CI

For a predeclared exact-path requirement, save this block as a separate Bash step
with the four variables exported. It runs both checks and preserves a nonzero
statistical exit before considering the trace exit. The explicit `arci gate`
command writes the usual decision/summary; `trace-check` remains read-only.

```bash
# CI gate composition (run in a separate shell)
gate_status=0
arci gate "$CAND_RUN" || gate_status=$?
trace_status=0
arci trace-check "$BASE_RUN" "$BASE_TRIAL" "$CAND_RUN" "$CAND_TRIAL" --format json >trace-check.json || trace_status=$?
if [ "$gate_status" -ne 0 ]; then
  exit "$gate_status"
fi
exit "$trace_status"
```

`MATCH + BLOCK` exits 1; `MATCH + INCONCLUSIVE` exits 2. Neither is green. A gate
`ERROR` exits 3 even if a diagnostic unexpectedly returns 0. Do not repeatedly
run or enlarge an experiment until the gate passes; use a predeclared design.
For exploratory diagnosis, retain the diagnostic output without making exact
matching an additional CI requirement.

## Comparison boundary

- **Scenario:** task payload, selected seed, ordered fault specifications,
  contract, budgets, Python/command execution kind, declared toolset/MCP-server configuration,
  full decision configuration, and declared fixture identity must agree. Pinned
  decision models/providers cannot change. Experiment IDs, labels, agent identity,
  and statistical designs may differ. Agent command arguments/environment belong
  to the variable agent identity; ambient process state is not authenticated.
  No compatibility override is provided.
- **View:** ordered `tool_start`, `tool_finish`, and optional `agent_result`
  payloads, followed by the terminal outcome, termination, claimed success,
  contract result, failure fingerprint/detail, and final state. Event-wrapper
  identity/timing and only top-level tool-event `call_id` are removed. Nested user
  data, including timestamps and call IDs, is retained. Annotations and non-tool
  MCP discovery recordings are excluded.
- **Equality:** canonical JSON bytes, including type distinctions such as
  `true`, `1`, and `1.0`. Full hashes describe differences; shortened display
  hashes never determine equality. Zero-tool traces and supported timeout/crash
  records can be compared. Structural validation is not replay validation.
- **Trust:** seals check integrity, not who produced a record. Equal fixture
  declarations do not authenticate code bytes. Empty fixture identities are
  accepted with an explicit declaration-only limitation. No oracle is rerun.

## Optional human adoption pilot: unmeasured

This optional future measurement is not a release requirement.
The operator may arrange one consenting non-author developer and a sanitized,
supported fixture. No outreach is part of this change. Allow **30 minutes** for
the participant to find a planted missing retry/tool call, explain why benign
drift alone is not a proven regression, and interpret the independent statistical
verdict. Use a benign change to a preserved field, not merely wrapper timing.
Record every attempted task and assistance; a maintainer or automated run is not
adoption evidence.

| Receipt field | Record |
|---|---|
| Participant consent, date, ARCI commit and installed location | Pending |
| Sanitized fixture identity; manifest/trial hashes from both sources | Pending |
| Planted change identified; elapsed minutes; assistance | Pending |
| Benign drift interpretation; gate interpretation; errors | Pending |
| Within seven days: independent second change, retained or dropped, reason | Pending |

Retain the original stores and completed receipt. The seven-day repeat is later
retention evidence, not a two-day engineering promise. Without a participant,
adoption remains **unmeasured**.
