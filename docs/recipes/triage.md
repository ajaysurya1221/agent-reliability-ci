# Diagnose an agent failure from its recorded run

`arci triage` is included in v0.9.0. It reads an existing native ARCI run store,
re-derives its complete statistical gate, selects up to three representative
candidate failure groups and shows the first recorded difference from each
trial's paired baseline. You do not need to write a trial-selection script or
read `trials.jsonl` to identify the containing tool event.

## First use: the offline retry fixture

Use Python 3.11+ on POSIX and a new or empty `arci-triage-demo` directory.
Installation needs network. The packaged fixture makes no model calls and needs
no API key. Keep `python` and `arci` in the same environment.

```bash
python -m pip install agent-reliability-ci==0.9.0
arci demo --workers 4 --keep arci-triage-demo
arci triage arci-triage-demo/runs/arci-demo-agent_b-reserve-timeout-200
```

The demo performs its existing six statistical, minimization and replay steps.
The last command is expected to exit **1** because the complete candidate-B
experiment is **BLOCK**. The representative comparison identifies the baseline's
next `reserve` call where the candidate proceeds to `confirm`. This fixture was
constructed with a removed retry; the diagnostic position alone does not prove
the cause of an arbitrary failure.

## Use the same command after your next change

```bash
arci triage runs/your-experiment
arci triage runs/your-experiment --format json
arci triage runs/your-experiment --trial YOUR_CANDIDATE_TRIAL_ID
```

The explicit selection can name a passing candidate trial. It compares that
record with its scheduled baseline partner; it does not create a new experiment
or change any denominator. Use `arci trace-check` when you need to select records
from two different compatible native stores.

The default selection groups candidate FAIL records by condition and existing
failure fingerprint. Hard-violation groups come first, including hard violations
in ceiling conditions. Groups in gating BLOCK conditions follow, then other
gating groups and descriptive ceiling groups. Counts and stable identities break
ties. An actual hard-violating trial is selected where applicable, otherwise a
failure with a passing baseline is preferred, followed by scheduled order.
The report shows how many groups were omitted. It is a descriptive sample, not a
new significance test or a causal ranking.

## Keep the statistical exit

| Exit | Meaning |
|---:|---|
| 0 | The complete experiment's gate is PASS and triage is valid. PASS is relative non-inferiority, not absolute reliability. |
| 1 | The complete experiment's gate is BLOCK and triage is valid. |
| 2 | The complete experiment's gate is INCONCLUSIVE and triage is valid. |
| 3 | The gate is ERROR, or inputs/selection/comparison/report consistency are invalid. |

Selected `MATCH` and `DRIFT` are diagnostic labels. MATCH can accompany BLOCK or
INCONCLUSIVE, and DRIFT can accompany PASS. Neither overrides the gate. If the
store changes between initial loading and comparison, triage refuses to combine
the evidence. An invalid diagnosis retains the original gate when available and
separately reports the diagnostic failure.

In a Bash CI step, preserve the exit when saving a report:

```bash
triage_status=0
arci triage "$RUN_DIR" --format json >triage.json || triage_status=$?
cat triage.json
exit "$triage_status"
```

Run any later artifact-upload step with your CI system's always-run condition.
Its success must not replace the triage step's exit. Review the data before
publishing it: identifiers, tool names, pointer keys and hashes can be sensitive.

## Read the context correctly

- A normalized position counts tool starts, tool finishes and agent results,
  followed by one terminal record. Context identifies the containing event and
  its original sequence number without exposing argument/result values.
- A missing **value** does not mean a missing **event**. An event may exist on
  both sides while one pointer names a field absent on one side. JSON null is a
  present value. Terminal and absent-step contexts are explicitly different.
- `tool_finish` occurrences come from their linked starts. Displayed tool names
  are bounded and terminal controls escaped. The unchanged comparison retains
  exact source hashes and difference pointer.
- Only the first difference is shown. The result cannot prove that later steps
  match, that a change is benign, or that drift caused a reliability regression.
- No recorded agent, oracle, command or endpoint is executed. No store or GitHub
  Step Summary is written. Replay remains a separate, explicit operation that
  executes trusted bundle code.

## Machine-readable use

`--format json` emits `arci-triage/1`. `status` describes report validity,
`exit_code` is the process result, and `gate` contains the original re-derived
decision with full counts and look history. `group_counts` tracks total, shown
and omitted failure groups separately from `selected_pairs`, because an explicit
passing selection may belong to no failure group. Each selected pair carries
the existing `arci-trace-check/1` comparison and containing-event context.

Consumers should use these fields rather than infer success from a tool name or
from the fact that a report was produced. Exact schema/CLI behavior is exercised
by the installed-wheel tests. No web service or tracing backend is needed.

Independent agent exercises are QA evidence only. Human adoption and retention
remain unmeasured and are not release requirements.
