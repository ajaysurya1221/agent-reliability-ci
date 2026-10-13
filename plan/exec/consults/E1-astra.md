**1. Adopt this `arci init` signature**

```text
arci init EXPERIMENT_ID --baseline REF --candidate REF --toolset REF --oracle REF
          [--task JSON | --task-file PATH] [--fault NAME[:TOOL[:OCC]]]...
          [--n N] [--out PATH] [--force]
```

Use the existing `_Parser`. Exact argument contract:

| Argument | Type/action; default | Help text |
|---|---|---|
| `EXPERIMENT_ID` | `str`; required | Experiment identifier and run-directory name |
| `--baseline REF` | `str`; required | Baseline Python agent, module:function |
| `--candidate REF` | `str`; required | Candidate Python agent, module:function |
| `--toolset REF` | `str`; required | Toolset factory, module:function |
| `--oracle REF` | `str`; required | Independent success check, module:function |
| `--task JSON` | `str`; `None` | Task as a JSON object; default: {} |
| `--task-file PATH` | `str`; `None` | Read the task JSON object from a UTF-8 file |
| `--fault SPEC` | `str`, `append`; `[]` | Inject NAME[:TOOL[:OCC]]; repeat to combine faults |
| `--n N` | `int`; `8` | Trials per arm, 1–10000; default: 8 (smoke) |
| `--out PATH` | `str`; `"arci.yaml"` | Output YAML descriptor; default: arci.yaml |
| `--force` | `store_true`; `False` | Replace an existing regular output file |
| `-h`, `--help` | `help`; no stored value | show this help message and exit |

**2. Default smoke size: eight trials per arm**

Choose **8 over the memo’s 5** because six additional trials allow a total collapse to BLOCK. Correct the prompt’s statistical premise: at default alpha/delta, Clopper–Pearson, K=1 and one look, **42 is the first PASS for two perfect arms**, not the first possible PASS. Read-only enumeration with [planning.verdict_table](/Users/ajay/Developer/agent-reliability-ci/src/arci/planning.py:266) found PASS first at N=6 (0/6 versus 6/6; lower bound −0.036508), statistical BLOCK first at N=8 (8/8 versus 0/8; upper bound −0.156495), and exclusively INCONCLUSIVE at N=5. T05 must use these qualified claims; hard-invariant BLOCK overrides remain possible at any N.

**3. Validation and errors**

In-process, before importing user code: parse arguments; require experiment IDs matching `[A-Za-z0-9][A-Za-z0-9._-]*`; validate JSON, faults, N and reference syntax; require `.yaml`/`.yml`, an existing parent directory, and no output collision without `--force`. Reject symlink/directory outputs even with force. Validate through T03’s Descriptor→Manifest conversion and `validate_contract`.

In one child, launch `sys.executable -P` with [runner._pythonpath](/Users/ajay/Developer/agent-reliability-ci/src/arci/runner.py:119). ADR 0006 appends cwd only when absent, preserving existing precedence. Resolve baseline, candidate, toolset, oracle in that order using [contracts.resolve](/Users/ajay/Developer/agent-reliability-ci/src/arci/contracts.py:24); distinguish import-stage exceptions from missing attributes and non-callability. Instantiate the toolset once with task and seed 0; require a string-to-callable `.tools` mapping and callable `.snapshot`; validate explicit fault targets in argument order. Do not invoke agents, oracle, tools or snapshot.

Apply a 30-second child deadline and process-group cleanup. Capture user output separately from structured validation results. The parent never imports user references.

Stop at the first failure. Each line below receives the exact prefix `error: CliError: init: `; dynamic values are JSON-quoted with control characters escaped:

```text
{flag} {ref}: module not importable; check module and dependencies
{flag} {ref}: attribute missing; check the name after ':'
{flag} {ref}: not callable; reference a function
--fault {spec}: tool {tool} absent from --toolset {ref}; choose an advertised tool
output {path} exists; use --force to replace it
{source}: invalid task JSON; supply one object without duplicate keys or non-finite numbers
--fault {spec}: invalid fault; expected supported NAME[:TOOL[:nonnegative OCC]]
```

Remaining failures use `invalid arguments: {detail}`, `invalid descriptor: {detail}`, `toolset validation failed: {detail}`, `reference validation failed: {detail}`, or `output failed: {detail}`; detail is escaped onto one line.

After validation, stage YAML beside the destination, re-load through T03, and verify the seal. Publish atomically, enforcing no-clobber unless forced; re-load the destination before success.

**4. Success output and exit codes**

Default stdout is exactly:

```text
arci run arci.yaml
```

Include one terminating newline; stderr is empty. Custom output prints the same command with the path shell-quoted, prefixed `./` if it starts with `-`. No additional files or messages.

Init/help exit 0; errors exit 3 with empty stdout. Set `arci run --out` to `str`, default `"runs"`, help `"Run-store directory; default: runs"`. Preserve run’s verdict exits and final stdout verdict; T05 notices remain stderr-only.

**5. Exact YAML header**

```yaml
# smoke design: expect INCONCLUSIVE; run arci plan before a confirmatory N
# Default: 8 trials per arm; this scaffold does not establish confirmatory power.
# Plan before trials: arci plan --help
# Never extend this experiment based on its verdict.
```

**6. Task, faults and generated semantics**

Task options are mutually exclusive; neither means `{}`. Parse strict JSON and embed the object, never its source filename.

Supported fault names: `tool_timeout`, `tool_error_once`, `empty_result`. Missing TOOL means any tool; missing OCC means 0. Allow `NAME::OCC`; reject empty explicit OCC, extra separators and negative/noninteger occurrences.

Repeated faults compose one condition, `faults`, in supplied order; none creates `clean` with no faults. Buckets are `falsify`, params `{}`. Thus K remains 1.

Set task ID to experiment ID, arm labels to `baseline`/`candidate`, and an oracle-only contract. Preserve [Manifest defaults](/Users/ajay/Developer/agent-reliability-ci/src/arci/schema.py:368), including budgets and seed, except N.

**7. Scope**

No command-agent scaffolding, interactive prompts, templates, custom fault factories, extra README, automatic trials or outcome-dependent extension. No frozen-file changes.