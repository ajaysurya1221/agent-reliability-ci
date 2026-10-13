# 0007: the `arci.yaml` descriptor (v0.8.0)

Decision by the orchestrator (Claude Fable 5.1) after two independent proposals, one by the read-only
consultant (gpt-6-astra, xhigh; `plan/exec/consults/E2-astra.md`) and one written blind by the
orchestrator (`plan/exec/decisions/E2-fable.md`), with three differences settled by a third consult
(`plan/exec/consults/E2-tiebreak.md`) on 2026-10-13. Part of the v0.8.0 onboarding sprint (task 03).

## Problem

An experiment is a sealed JSON `Manifest` built in Python. A newcomer should be able to read and
edit one in a text file, and `arci init` needs something to write, without a second configuration
engine, a second source of defaults, or any decision logic outside the frozen schema.

## Decision

`arci.yaml` is a thin descriptor: a Pydantic model (`extra="forbid"`, frozen) whose keys are the
`Manifest`'s field names, loaded with `yaml.safe_load` (the `contracts.load_contract` precedent),
validated, and compiled into a sealed `Manifest` with `Manifest.create` exactly as the Python builders
do. The run store, the seal and every validator are unchanged; the YAML layer holds no decision logic.

- Keys map 1:1 onto `Manifest` fields with the Manifest's defaults. Aliases: top-level `oracle`
  (shorthand for `contract: {oracle: ...}`; exactly one of `oracle` or `contract`), `id` →
  `condition_id`, `occurrence` → `at_occurrence`, `fault` (one mapping) → `faults` (list). Giving both
  forms of an alias is an error even when they agree. Unknown keys are errors.
- Arms: a bare `module:function` string is a Python arm (`candidate_id` default); a mapping is an
  `ArmSpec` as is (`label`, exactly one of `agent` or `command`, `candidate_id`). Command experiments
  carry `mcp_server` and `decisions` with the frozen models' own defaults; `argv` placeholders stay
  literal strings.
- Faults: `name` required; `bucket` default `falsify`; `tool` default null (any); `occurrence`
  default null (the perturbation's default); `params` default `{}`; names must be in
  `perturb.REGISTRY` or `module:function` syntax (never imported at load).
- Not exposed: `schema_version`, `record_sha256`, `created_at` (the loader sets `""`); exposed:
  `fixtures_sha256` as an opaque optional string so a manifest round-trips.
- `arci run PATH` accepts a sealed `.json` manifest or a `.yaml`/`.yml` descriptor; `--out` defaults
  to `runs`; nothing else about `run` changes.
- `arci schema [--out PATH]` prints `Descriptor.model_json_schema()` (two-space indent, sorted keys,
  final newline); the bytes are committed at `docs/schema/arci.schema.json` with a staleness test.
  Title `ARCI experiment descriptor`; `$id`
  `https://raw.githubusercontent.com/ajaysurya1221/agent-reliability-ci/v0.8.0/docs/schema/arci.schema.json`.
  Editors: `arci schema --out arci.schema.json` then `# yaml-language-server: $schema=./arci.schema.json`
  as the first line; a `$schema` mapping key is an unknown key. Pydantic is authoritative; the schema
  cannot express the cross-field validators.
- Errors: one line, exit 3, through the CLI's existing form:
  `error: CliError: descriptor arci.yaml:conditions[0].fault.name: unknown fault "tool_timout"`.
- The retry demo descriptor seals byte-identically to `arci.demo.experiment.build_manifest(200,
  "agent_b")`; the Python builder remains the advanced path.

### Settled by the tie-break consult (`plan/exec/consults/E2-tiebreak.md`)

TBD-1 `task_id` required vs default · TBD-2 bare-string arm label · TBD-3 YAML 1.1 resolver (filled
in once ruled).

## Not in v0.8.0

A second descriptor format, templates, includes or variables, a `$schema` key, decision logic or
defaults that differ from the `Manifest`, editing a sealed manifest in place.
