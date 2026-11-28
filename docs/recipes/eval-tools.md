# Use ARCI with your evaluation tool

Your tool runs the tests. ARCI reads the results and gives a verdict on the change.

| Tool | Version tested | Route | How it was tested | What to watch for |
| --- | --- | --- | --- | --- |
| [promptfoo](promptfoo.md) | 0.125.1 and 0.126.0 | Convert saved JSON for a descriptive verdict, or use check-change for fresh runs. | Both versions ran word checks with a scripted provider. A local HTTP stub tested cache hits in 0.126.0. | For fresh runs, use `--no-cache` and leave repeats off. For repeated runs, promptfoo's own `repeatStability` reports per-test pass-rate ranges. |
| [DeepEval](deepeval.md) | 4.3.6 | Pass pytest JUnit XML to check-change. | Pytest ran 20 word checks with the `ContainsWord` metric. | Give each input a stable pytest id. An exception in the test body counts as a failure. |
| [Opik](opik.md) | 2.3.7 | Pass pytest JUnit XML to check-change. | Pytest ran word checks with `@opik.llm_unit()` and a Python assertion. | Experiment logging contacts the cloud by default. Turn off logging and tracing for a local run. |
| [MLflow](mlflow.md) | 3.18.0 | Export `result_df` to JSONL for check-change. | `mlflow.genai.evaluate` ran 20 items with a Python scorer and local SQLite. | Check for prediction and scorer errors before using the score. MLflow also offers an experimental paired comparison, `mlflow.genai.compare_evaluations`. |
| [Langfuse](langfuse.md) | 5.2.0 | Export `item_results` to JSONL for check-change. | The Python SDK ran 20 word checks with `run_experiment`, tracing off and no live server. | Keep the input ids. A task that raises can disappear from the results. An evaluator that raises can leave an empty score list. |
