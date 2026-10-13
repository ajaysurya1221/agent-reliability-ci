# The `arci.yaml` descriptor

`arci.yaml` describes one experiment. `arci run arci.yaml` loads it, compiles it into the frozen
`Manifest`, seals it with `Manifest.create` (exactly as a Python builder does) and runs it; the run
store is unchanged, so `runs/<experiment_id>/manifest.json` is the sealed manifest JSON. The
descriptor is a thin deserialisation layer: no decision logic lives in it, and every rule the
`Manifest` enforces is enforced by the `Manifest`. The Python builder (`Manifest.create` in your own
script, as in `examples/`) remains the advanced path for anything the file cannot say.

**Pydantic is authoritative.** `arci schema` prints `Descriptor.model_json_schema()` (two-space
indent, sorted keys). The committed copy, [`docs/schema/arci.schema.json`](schema/arci.schema.json),
is pinned under the locked pydantic and a test fails when it is stale. JSON Schema cannot express
the cross-field rules below (one-of pairs, the experiment kind, decision faults); the models
check them and their descriptions state them.

For editor completion, write the schema beside the descriptor and point at it from a comment:

```sh
arci schema --out arci.schema.json
```

```yaml
# yaml-language-server: $schema=./arci.schema.json
```

A `$schema` *key* is an unknown key; only the comment works.

## Keys

Keys are the `Manifest`'s field names. R = required, O = optional.

| Key | Type | Default | Becomes |
|---|---|---|---|
| `experiment_id` | string | R | `experiment_id` (and the run directory name) |
| `task_id` | string | O, the `experiment_id` | `task_id` |
| `task` | JSON object | O, `{}` | `task` |
| `toolset` | `module:function` | O, null; python arms need it | `toolset` |
| `mcp_server` | `{name, argv, env, snapshot}` | O, null; command arms need it | `mcp_server` |
| `decisions` | DecisionSpec mapping | O, null | `decisions` |
| `oracle` | `module:function` | R unless `contract` | `contract.oracle` |
| `contract` | ContractSpec mapping | R unless `oracle` | `contract` |
| `baseline`, `candidate` | `module:function` or arm mapping | R | `baseline`, `candidate` |
| `conditions` | list, at least one | R | `conditions` |
| `alpha` | number in [0.000001, 0.5] | O, `0.05` | `alpha` |
| `delta` | number in (0, 1) | O, `0.10` | `delta` |
| `n_per_arm` | integer in [1, 10000] | O, `200` | `n_per_arm` |
| `interval_method` | `clopper_pearson` or `newcombe` | O, `clopper_pearson` | `interval_method` |
| `looks` | integer list | O, `[]` | `looks` |
| `base_seed` | integer | O, `0` | `base_seed` |
| `budgets` | `{max_tool_calls, max_model_steps, max_seconds, grader_seconds}` | O, 30, 50, 30.0, 20.0 | `budgets` |
| `fixtures_sha256` | string, opaque | O, `""` | `fixtures_sha256` |
| `prior_runs` | string list | O, `[]` | `prior_runs` |

Give exactly one of `oracle` and `contract`; the `contract` mapping carries its own `oracle` plus
`max_tool_calls`, `forbidden_tools`, `required_tools`, `max_calls_per_tool` (a non-empty
`unobservable` is rejected). Non-empty `looks` increase strictly and end at `n_per_arm`.
Unknown keys are errors everywhere. `schema_version`, `record_sha256` and `created_at` are not
keys: the schema and the sealer own the first two and the loader sets `created_at` to `""`, as the
builders do.

## Arms

- A bare string `app.v1:run` is a python agent: `ArmSpec(label="v1.run", agent="app.v1:run",
  candidate_id="")`. The label is the last module segment and the function, so `app.v1:run` and
  `app.v2:run` stay distinguishable in reports.
- A mapping is an `ArmSpec` as is: `label` (required), exactly one of `agent` (`module:function`)
  or `command`, and optional `candidate_id` (default `""`).

References are checked for `module:function` syntax only; nothing is imported at load time.
Both arms are python agents (top-level `toolset`, no `mcp_server`) or both commands.

## Conditions and faults

Each condition has `id` (or its full name `condition_id`) and either `fault` (one mapping) or
`faults` (a list, applied together in order). A clean condition has neither. A fault has:

- `name`: a built-in (`tool_timeout`, `tool_error_once`, `empty_result`,
  `decision_low_confidence`, `decision_unavailable`) or a custom factory `module:function`
  (syntax checked here, imported only in the trial process);
- `bucket`: `falsify` (default), `benign` or `ceiling`;
- `tool`: the tool to target, default null (any tool);
- `occurrence` (or `at_occurrence`): zero-based call count, default null (the fault's default);
- `params`: default `{}`.

An alias and its full key (`id`/`condition_id`, `fault`/`faults`, `occurrence`/`at_occurrence`,
`oracle`/`contract`) may never both be given, even with equal values. Decision faults need
`decisions` and `tool: decision:systemone`; `decision_low_confidence` takes only
`confidence_max` (a number in [0, 1]) and `decision_unavailable` takes no params.

## Command experiments

Both arms are `command: {argv, env, infra_exit_codes}` (defaults `env: {}`,
`infra_exit_codes: [75]`), with `mcp_server: {name, argv, env, snapshot}` (defaults
`name: env`, `env: {}`) and no `toolset`. `decisions` (`upstream`, `fixture`, `base_url`, `model`,
`max_decisions`, `request_seconds`, `max_body_bytes`, `max_requests_per_minute`) needs a `fixture`
exactly when `upstream: fixture`. Placeholders `{mcp_config}`, `{task_file}`, `{workdir}`,
`{seed}` stay literal strings (quote them in YAML) and are expanded only at launch. YAML has no
`sys.executable`: write an absolute interpreter path or `python` resolved on `PATH`.

## How the file is parsed

The descriptor loader reads one YAML document with its own SafeLoader subclass (the global
`yaml.SafeLoader` and `contracts.load_contract`, which keeps plain `yaml.safe_load`, are
untouched). It departs from YAML 1.1 coercion so that values stay what they look like:

- booleans are only `true` and `false`; `yes`, `no`, `on`, `off`, `True` stay strings;
- integers are decimal (`010` is 10, not octal 8), `0x1f`, `0o10` (8) or `0b101`; `1_000` and
  `1:30` stay strings;
- dates and timestamps (`2026-10-13`) stay strings;
- null (`null`, `~`, empty), floats (with a `.`) and merge keys follow YAML 1.1.

Quote any string that could still read as a number or null (`"1.0"`, `"null"`); `arci init`
quotes every string it writes. Values in `task` and `params` must be JSON.
Other YAML that ARCI reads (a contract file through `load_contract`) and other YAML tools keep
YAML 1.1, where `yes`/`no`/`on`/`off` are booleans and `010` is 8: quoting keeps a file portable.

## Errors

A descriptor that does not load stops `arci run` before any trial: exit 3, empty stdout, one
line on stderr naming the file, the source path (with the keys you wrote, aliases included, and
zero-based indices) and the problem. When several things are wrong, the first by source path is
reported.

```text
error: CliError: descriptor arci.yaml:n_per_arn: unknown key "n_per_arn"
error: CliError: descriptor arci.yaml:baseline: invalid reference "pkg/run"; expected module:function
error: CliError: descriptor arci.yaml:conditions[0].fault.name: unknown fault "tool_timout"; expected one of ...
```

Library callers get `arci.descriptor.DescriptorError` (a `ValueError`) from
`compile_descriptor(path)`.

## Example: the retry demo

This file seals to the same `record_sha256` as `arci.demo.experiment.build_manifest(200, "agent_b")`.

```yaml
# yaml-language-server: $schema=./arci.schema.json
experiment_id: arci-demo-agent_b-reserve-timeout-200
task_id: confirm-inventory-order
task: {order_id: order-7, sku: widget, quantity: 2, stock: 10}
toolset: arci.demo.world:make_world
oracle: arci.demo.world:oracle
baseline: {label: agent_a, agent: "arci.demo.agents:agent_a", candidate_id: baseline-a}
candidate: {label: agent_b, agent: "arci.demo.agents:agent_b", candidate_id: candidate-agent_b}
conditions:
  - id: reserve-timeout
    fault: {name: tool_timeout, tool: reserve, occurrence: 0}
alpha: 0.05
delta: 0.10
n_per_arm: 200
base_seed: 12000
budgets: {max_tool_calls: 10, max_model_steps: 10, max_seconds: 15.0}
```

## Example: a command agent (the offline guardrail experiment)

The translation of `examples/guardrail_agent/experiment.py:build_manifest()`. Its `task` lists
182 commands; two are shown. Replace `/abs/.venv/bin/python` with your interpreter.

```yaml
experiment_id: guardrail-fixture-b-ask-provider_down-50
task_id: guardrail-shell-command-ask
task:
  population: ask
  commands:
    - {"id": "read-003", "command": "head -n 20 app/main.py"}
    - {"id": "read-004", "command": "tail -n 50 logs/app.log"}
oracle: examples.guardrail_agent.world:oracle
baseline:
  label: a
  candidate_id: guard-a
  command:
    argv: [/abs/.venv/bin/python, -P, -m, examples.guardrail_agent.agent,
           --mcp-config, "{mcp_config}", --task-file, "{task_file}", --variant, a]
    infra_exit_codes: []
candidate:
  label: b
  candidate_id: guard-b
  command:
    argv: [/abs/.venv/bin/python, -P, -m, examples.guardrail_agent.agent,
           --mcp-config, "{mcp_config}", --task-file, "{task_file}", --variant, b]
    infra_exit_codes: []
mcp_server:
  name: guardrail
  argv: [/abs/.venv/bin/python, -P, -m, arci.mcp_toolset_server,
         --toolset, "examples.guardrail_agent.world:make_world",
         --workdir, "{workdir}", --seed, "{seed}", --task-file, "{task_file}"]
  snapshot: arci.mcp_toolset_server:snapshot
decisions: {upstream: fixture, fixture: "examples.guardrail_agent.decisions:fixture", model: jev-1.13.0}
conditions:
  - id: provider_down
    fault: {name: decision_unavailable, tool: "decision:systemone"}
n_per_arm: 50
base_seed: 31000
budgets: {max_tool_calls: 4, max_model_steps: 10, max_seconds: 30.0, grader_seconds: 10.0}
```
