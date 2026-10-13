# 0008: `arci init`, the scaffold for a first experiment (v0.8.0)

Decision by the orchestrator (Claude Fable 5.1) after two independent proposals, one by the
read-only consultant (gpt-6-astra, xhigh; `plan/exec/consults/E1-astra.md`) and one written blind by
the orchestrator (`plan/exec/decisions/E1-fable.md`), with the differences settled by a third consult
(`plan/exec/consults/E1-tiebreak.md`) on 2026-10-13. Part of the v0.8.0 onboarding sprint (task 04).

## Problem

Today a first experiment is a Python manifest builder copied from an example. The memo's path to a
first verdict needs one non-interactive command that takes the experiment name and four references
(baseline, candidate, toolset, oracle), validates them at once, and writes a runnable descriptor.

## Decision

```text
arci init EXPERIMENT_ID --baseline REF --candidate REF --toolset REF --oracle REF
          [--task JSON | --task-file PATH] [--fault NAME[:TOOL[:OCC]]]...
          [--n N] [--out PATH] [--force]
```

- `EXPERIMENT_ID` matches `[A-Za-z0-9][A-Za-z0-9._-]*` (it names the run-store directory). The task
  id is the experiment id.
- The four references are Python `module:function` targets (the frozen `AgentRef` form). Command
  agents are hand-written YAML (see the MCP recipe), not scaffolded.
- `--task` is a JSON object; `--task-file` reads one from a UTF-8 file; the two are mutually
  exclusive; neither means `{}`. String values are written quoted so YAML 1.1 cannot coerce them.
- `--fault NAME[:TOOL[:OCC]]` is repeatable. Omitted TOOL means any tool; omitted OCC means 0. All
  faults compose ONE condition, `faults`, in the order given, bucket `falsify`, so K stays 1 and the
  planner applies. No `--fault` gives one fault-free condition `clean`.
- `--n` defaults to **8**. Under the default rule two perfect arms cannot PASS below N=42 and a
  total collapse cannot BLOCK below N=8, so 5 (the memo's suggestion) can only ever say
  INCONCLUSIVE or ERROR; 8 is the smallest design in which a collapse still decides, and it is still
  labelled a smoke design. Everything else keeps the `Manifest` defaults (alpha 0.05, delta 0.10,
  budgets, base seed 0, Clopper-Pearson, one look).
- `--out` defaults to `arci.yaml`; an existing regular file is replaced only with `--force`; a
  directory or symlink is never replaced. The file is staged beside the destination, re-loaded through
  the descriptor loader, seal-checked, and published atomically.
- `arci run` accepts the descriptor directly and its `--out` now defaults to `runs`, so the
  first-screen command `arci run arci.yaml` holds.

### Validation, in order, stopping at the first failure

In the CLI process, before any user code: argument syntax, the id pattern, reference syntax, task
JSON, fault syntax, output collision. Then ONE child process, `sys.executable -P` with the runner's
`PYTHONPATH` rule (ADR 0006), 30 s deadline, process group killed on timeout, user output captured
separately: import and resolve baseline, candidate, toolset and oracle in that order (import error,
missing attribute and not-callable are distinguished); instantiate the toolset once with the task
and seed 0 and read its `.tools` mapping and `.snapshot`; check every explicit fault TOOL against
those keys. Agents, oracle, tools and snapshot are never called. The parent never imports a
reference (AGENT_SEMANTICS).

Errors are one line on stderr, exit 3, nothing written, in the CLI's existing
`error: CliError: init: ...` form, for example `--baseline app.v1:run: module not importable; check
module and dependencies`, `--fault tool_timeout:reserve:0: tool reserve absent from --toolset
tests.world:make_world; choose an advertised tool`, `output arci.yaml exists; use --force to replace it`.

### Settled by the tie-break consult

TBD-A success stdout · TBD-B header comment · TBD-C arm labels and candidate_id · TBD-D accepted
fault names · TBD-E task id flag (see `plan/exec/consults/E1-tiebreak.md`; filled in below once ruled).

## Not in v0.8.0

Command-agent scaffolding, interactive prompts, templates, `--alpha/--delta/--looks/--interval-method`
flags, git-sha discovery for `candidate_id`, editing an existing descriptor, running trials from
`init`, any outcome-dependent extension.
