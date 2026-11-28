# Real outputs of five evaluation tools

Produced on 2026-11-28 on macOS (Apple silicon) by the tools themselves, each installed at a
pinned version in its own environment (Python wheels only, `npm install --ignore-scripts`), and
run under a macOS sandbox profile that refused every network connection except to this machine.
No account, no API key and no model were used: the agents and checks are small scripts.
`scrub.py.txt` then replaced local paths (`/work`, `/tools`, `/home`), the host name (`host`) and
the user name (`user`); nothing else was changed. Generator inputs are kept beside the outputs
with a `.txt` suffix so that pytest, ruff and the type checker do not pick them up; a nested
input is renamed with `-` (for example `vars/more.csv` is `vars-more.csv.txt`).

| Directory | Tool and version | How it was produced |
|---|---|---|
| `promptfoo/` | promptfoo 0.126.0 (results `version: 3`), Node 24.18.0 | `generate.sh.txt`: `promptfoo eval -c CONFIG [--repeat N] [--no-cache] --no-table --no-progress-bar --no-share -o OUT.json`, with `PROMPTFOO_PASS_RATE_THRESHOLD=0` and telemetry off; the cache files use an `http` provider against `stub_server.py.txt` on 127.0.0.1 and a fresh cache directory |
| `deepeval/` | DeepEval 4.3.6, pytest 9.2.0, Python 3.13.12 | `generate_pytest_tools.sh.txt`: `deepeval test run test_agent.py --junitxml=OUT` with `AGENT_MODE=pass` or `fail`, and `test_shapes.py`; a code-only metric (`ContainsWord`) |
| `opik/` | Opik 2.3.7, pytest 9.2.0, Python 3.13.12 | the same script: `pytest test_agent.py --junitxml=OUT` with `@opik.llm_unit()` and `OPIK_PYTEST_EXPERIMENT_ENABLED=false`; `logging-on.xml` is the same run with that variable unset |
| `mlflow/` | MLflow 3.18.0, Python 3.13.12 | `python evaluate_agent.py pass|fail OUT`: `mlflow.genai.evaluate` on 20 items, local SQLite store, a code scorer; `result_df-*.json` is `EvaluationResult.result_df` without the `trace` column |
| `langfuse/` | Langfuse Python SDK 5.2.0, Python 3.13.12 | `python run_experiment.py pass|fail OUT`: `Langfuse.run_experiment` on 20 items with tracing off and the client pointed at a local address where no server listens; `item_results-*.json` is what it returned |

## What the files showed

promptfoo
- The tool version is in the top-level `metadata.promptfooVersion`; the run id is `evalId`;
  `results.timestamp` is the run's time.
- A row's test is `testCase` (`description`, `vars`). `testCase.vars` already includes
  `defaultTest.vars` (`tone` in `shapes.json`). A variable read from a file keeps its full
  `file://` path, so it changes with the folder the run starts from.
- Tests from a CSV file get generated descriptions (`Row #1`, `Row #2`), in file order.
- `success` is the pass flag; `failureReason` is 0 for a pass, 1 for a failed assertion and 2
  for an error raised by the provider. An assertion that throws is a failed assertion (1), not
  an error.
- The key `description + " #" + sha256(canonical {description, vars})[:16]` gives the same ids
  for these configs in 0.125.1 (`../../outcomes/real/promptfoo/`) and in 0.126.0, across both
  arms and every repeat. Two tests with the same description and vars give the same key
  (`same-twice` in `shapes.json`).
- With `--repeat N`, `testIdx` numbers rows, `repeatIndex` (from 0) is the repetition and
  `repeatGroupId` the test. `results.repeatStability` is present.
- One file can hold several cells: `two-prompts.json` has `promptIdx` 0 and 1 with one provider
  label; `two-providers.json` has two provider labels.
- Cache: with the cache on, the second run sent no request to the stub (`cache-warm.json`):
  every row has `response.cached: true`, `results.stats.cacheHits` is 2, and the prompt metrics
  carry `testCacheHitCount`. `stats.cacheHits` is absent when there were no hits. Rows from a
  `file://` provider carry no `cached` field. With `PROMPTFOO_CACHE_ENABLED=false` the run sent
  fresh requests. With `--repeat 2` both runs sent fresh requests (8 in total for 4 rows each).
- The recount of `success` and `failureReason` equals `results.stats` in every file.

DeepEval
- `deepeval test run ... --junitxml=OUT` passes the option to pytest and writes a normal pytest
  JUnit file (`<testsuites>`, a `timestamp` on the suite). Exit status is pytest's: 0 all
  passed, 1 a test failed.
- Ids are `module::test[param-id]`. With explicit `ids=[...]` they are equal across runs
  (`e2e-*.xml`, `named-run2.xml`); without, they are positional (`test_positional[golden0]`).
- A failed metric is `<failure>`; `pytest.skip` is `<skipped>`; an exception in the test body is
  `<failure>` too, so a crash and a wrong answer look the same.

Opik
- With `OPIK_PYTEST_EXPERIMENT_ENABLED=false`, `@opik.llm_unit()` changes nothing in the JUnit
  file; the outcome is the test's own `assert`. Same id, status and skip behaviour as DeepEval.
- With the variable unset (`logging-on.xml`), Opik tried to send the results to its cloud
  address; the sandbox refused, the test outcomes were unchanged, and the run took about 22
  seconds of retries instead of about one.

MLflow
- `result_df` columns: `trace_id`, `<scorer>/value`, `<scorer>/error_message`, `<expectation
  name>/value`, `state`, `request` (the inputs), `response` and trace details.
- When `predict_fn` raised (`w07`), the row has `state: ERROR`, and the scorer still ran on the
  empty answer: `contains_word/value` is `false`. Only `state` shows the crash.
- When the scorer raised (`w13`), `contains_word/value` is null and `contains_word/error_message`
  holds the message.
- Traces record the operating-system user name (`mlflow.user`, `source_id`); scrubbed here.

Langfuse
- `run_experiment` runs without a server when tracing is off; `trace_id` is all zeros.
- The item whose task raised (`w07`) is missing from `item_results` (19 of 20); the SDK logs
  "Item 6 failed" and nothing else records it.
- The item whose evaluator raised (`w13`) is present with an empty `evaluations` list.
