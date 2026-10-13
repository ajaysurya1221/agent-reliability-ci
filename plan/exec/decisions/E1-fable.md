# E1 — `arci init` contract: Fable's position (written blind, before reading E1-astra)

Written 2026-10-13 (see the commit timestamp) without opening `plan/exec/consults/E1-astra.md`.

## 1. Signature

```
arci init EXPERIMENT_ID --baseline REF --candidate REF --toolset REF --oracle REF
          [--task JSON | --task-file PATH] [--task-id ID]
          [--fault SPEC ...] [--n N] [--out PATH] [--force]
```

- `EXPERIMENT_ID` positional, `^[A-Za-z0-9][A-Za-z0-9._-]*$` (it names the run-store directory).
- `--baseline`, `--candidate`, `--toolset`, `--oracle`: `module:function` refs (the frozen `AgentRef`
  pattern). Python agents only.
- `--task JSON` (inline JSON object) or `--task-file PATH` (JSON object), mutually exclusive,
  default `{}`. `--task-id` default = `EXPERIMENT_ID`.
- `--fault SPEC`, repeatable, `NAME[:TOOL[:OCCURRENCE]]` (`tool_timeout:reserve:0`); one condition
  per `--fault`, `condition_id = NAME-TOOL` (or `NAME` when no tool), bucket `falsify`. No `--fault`
  → one condition `clean` with no faults (the Manifest needs at least one condition).
- `--n` default **8**; `--out` default `arci.yaml`; `--force` to overwrite.
- Not exposed: alpha, delta, looks, interval_method, budgets, base_seed, prior_runs (edit the file).

## 2. Default smoke N = 8, not 5

Under the default rule (alpha 0.05, delta 0.10, K=1) PASS is impossible below N=42 and BLOCK is
impossible below N=8 (at N=7, 7/7 vs 0/7 gives an upper bound of about -0.07, above -0.10; at N=8
it is about -0.16). A run that can only ever say INCONCLUSIVE or ERROR is not a first verdict, it
is a syntax check. N=8 is the smallest design where a total collapse can still BLOCK, costs 16
trials (seconds), and is still labelled SMOKE. The memo's 5 is "a reasonable starting
implementation choice", not a requirement; the one-line justification above is what the file says.

## 3. Validation before writing

In-process (pure syntax, no imports): experiment id pattern; the four refs match `AgentRef`;
`--task` parses to a JSON object; `--fault` syntax; output collision.

In a child `sys.executable -P -c <script>` with `PYTHONPATH = runner._pythonpath()` (same rule as
the workers, so what init accepts is what `arci run` will import), 30 s timeout, JSON result on
stdout: import each module, `getattr`, `callable`; call ONLY the toolset factory
(`factory(task, base_seed)`) and read `.tools` keys; check every fault tool is in those keys; check
every fault name is in `perturb.REGISTRY` or is an importable `module:function`. Agents and the
oracle are imported, never called.

Errors: one line on stderr, exit 3, nothing written. Format `error: init: <detail>`:
- `cannot import 'app.v1' for --baseline: ModuleNotFoundError: No module named 'app'`
- `'app.v1' has no attribute 'run' (--baseline)`
- `'app.v1:run' is not callable (--baseline)`
- `fault 'tool_timeout' names tool 'reserve' but the toolset provides: confirm, get_stock`
- `unknown fault 'foo' (built in: empty_result, tool_error_once, tool_timeout; or module:function)`
- `arci.yaml exists; pass --force to overwrite`
- `--task must be a JSON object` / `--fault must be NAME[:TOOL[:OCCURRENCE]]`
- `toolset 'tests.world:make_world' raised: <one line>` / `ref check timed out after 30 s`

## 4. Success output

stdout, two lines, exit 0:
```
wrote arci.yaml  (smoke design: n_per_arm=8, expect INCONCLUSIVE)
next: arci run arci.yaml
```
The written file is re-loaded through the descriptor loader before exit; a failure there is a bug
and exits 3 with `error: init: generated descriptor did not validate: <detail>`.

## 5. Header comment

```yaml
# arci experiment descriptor. Schema: docs/schema/arci.schema.json (`arci schema` prints it).
# SMOKE DESIGN: n_per_arm 8 is for first contact with the real gate, not evidence.
# Under the default rule PASS is impossible below N=42 and BLOCK below N=8: expect INCONCLUSIVE.
# Before a confirmatory run, plan N:
#   arci plan --baseline-rate 0.95 --candidate-rate 0.75 --target-verdict BLOCK
# Changing anything below makes a new experiment; `arci run` seals it before the first trial.
```

## 6. Parsing rules

`--task` must be a JSON object; strings stay strings (the writer quotes every string value so
YAML 1.1 cannot coerce them). `--fault` splits on `:` into at most three parts; OCCURRENCE is a
non-negative int; TOOL omitted = any tool (`tool: null`). Multiple faults → multiple conditions
(K > 1); the smoke notice then uses its fixed sentence because the planner covers K=1 only.

## 7. Out of scope

Command agents (`mcp_server`, `command` arms: hand-write the YAML, documented in the MCP recipe),
interactive prompts, templates, `--alpha/--delta/--looks/--interval-method`, git-sha discovery for
`candidate_id` (it is set to the ref string), editing an existing file.
