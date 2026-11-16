# R5 build complete

Baseline receives the empty-lookup explanation; candidate retains run 2's setup.
No Ollama or real model was started. No network, installs, git mutations, memory lookup,
or access beneath ~/.claude or ~/.codex was used.

## Files created

- `agent.py`, `arci.yaml`, `tasks.jsonl`.
- Byte-identical copies: `tools.py`, `check.py`, `configuration.py`, `offline_model.py`, `register.py`.
- `tests/test_middleware.py` (independently written from the fixed interface),
  `tests/test_end_to_end.py`, `tests/code_retry_demo.py`, `tests/test_code_retry_demo.py`.
- `_offline/`: retained verification outputs listed below. Nothing was deleted.

The complete [agent diff](agent.diff) changes only the docstring, required audit imports,
new constant/middleware, and middleware selection. Prompt, retry configuration,
ReturnToolErrors, fault_exceptions and everything after settings remain identical.
The recursive folder diff has only the five categories allowed by the brief.
[Scope checks](scope-check.txt) confirm five exact copies, eight task bodies in original
order, exact descriptor values and all 54 frozen hashes.

## Commands and last lines

Use the supplied run3-env `python` and sibling `arci`. Before help, both plans and the
single register invocation, the environment was:

```sh
ARCI_QUICKSTART_BASELINE='ollama:qwen3.5:4b-mlx-ctx32k'
ARCI_QUICKSTART_CANDIDATE='ollama:qwen3.5:4b-mlx-ctx32k'
ARCI_QUICKSTART_TEMPERATURE=0.7
PYTHONDONTWRITEBYTECODE=1
```

| Command | Exit | Last line / result |
|---|---:|---|
| `arci plan arci.yaml --help` | 0 | `--looks N,N,... refused: the planner covers one fixed-sample look` (help text) |
| `arci plan arci.yaml` before registration | 0 | `floors only: no model supplied` |
| `python register.py` (exactly once) | 0 | `Registered model settings; start a new run with arci run arci.yaml` |
| `arci plan arci.yaml` after registration | 0 | `floors only: no model supplied` |
| `python -m pytest -p no:cacheprovider tests/test_middleware.py tests/test_end_to_end.py tests/test_code_retry_demo.py` | 1 | `No module named pytest` |
| `python tests/test_middleware.py` | 0 | `9 middleware tests passed` |
| `python tests/test_end_to_end.py` | 0 | `1 end-to-end test passed` (16 offline trials) |
| `python tests/test_code_retry_demo.py` | 0 | `2 code-retry tests passed` (2 offline trials) |
| `.venv/bin/ruff format --no-cache <study>` | 0 | `10 files left unchanged` |
| `.venv/bin/ruff check --no-cache <study>` | 0 | `All checks passed!` |
| `.venv/bin/basedpyright --pythonpath <run3-env>/bin/python <study>` | 0 | `0 errors, 0 warnings, 0 notes` |

Every Python command used `PYTHONDONTWRITEBYTECODE=1`. See [exact final commands and tails](final-checks.txt).
Registration compared the entire parsed YAML before and after: equal. Rule, arms,
condition and prior_runs all survived. All eight tasks now register the same 4B model
in both arms, temperature 0.7, reasoning disabled. Planning output is retained in
`plan-help.txt`, `plan-before.txt`, `plan-after.txt`; registration output is in `registration.txt`.

## Offline proof and retained stores

The integration test uses released ARCI `run_trial`, real child workers, `make_adapter`,
the built-in empty_result injector and `ExperimentStore`. A test-only scripted model
records each actual input before interpreting it. It uses the study's settings and tools,
substituting only the model; production agent entrypoints are unchanged below settings.
These are one-pair legacy manifests for plumbing checks, not the registered v2 suite,
not a statistical verdict, and not evidence of model benefit. No `arci run` was invoked.

Latest message proof: 8 baseline inputs equal EMPTY_LOOKUP_TEXT, 8 candidate inputs equal
`null`; 16 sealed trials retain injected_by=empty_result and the raw null result.
Exactly 8 baseline audit lines match the observed tool_call_ids; candidate audit files
are absent. Both text-arm policies issue their second lookup after another model step.

Latest code retry proof: both demonstration trials contain exactly 2 recorded lookup_order
calls with the same arguments, separated only by tool_finish, with no model step between.
The next model input contains the recovered order. This middleware is never imported by agent.py.

- `test_code_retry_demo-4l8iji8c/`: 2 offline trials; manifests, sealed trials, events, actual model inputs, baseline audits where applicable, and summary.
- `test_code_retry_demo-b5fq4etx/`: 2 offline trials; manifests, sealed trials, events, actual model inputs, baseline audits where applicable, and summary.
- `test_end_to_end-4508h1ef/`: 16 offline trials; manifests, sealed trials, events, actual model inputs, baseline audits where applicable, and summary.
- `test_end_to_end-g5zavg2u/`: 16 offline trials; manifests, sealed trials, events, actual model inputs, baseline audits where applicable, and summary.

Two proof executions are retained (initial and final verification): 36 scripted trials total.
`middleware-audit-*` holds unit-test append evidence and empty write-failure directories.
Final verification did not delete earlier artifacts.

## Limits and risks

Pytest is unavailable; the brief's plain-assert main() fallback ran all 12 tests.
No type-check suppressions were added. No unresolved doubt remains about delivery through
the tested adapter: actual model inputs and original injected-fault records were inspected.
Real-model response quality and live-run duration remain untested, as required by R5.
This report is a work record; the orchestrator must independently rerun acceptance checks.
