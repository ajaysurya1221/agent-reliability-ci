# Compare two versions with MLflow

MLflow 3.18.0 was tested on Python 3.13.12. The fixture ran
`mlflow.genai.evaluate` on 20 items with a local SQLite store and a Python
scorer. It saved `result_df` without the `trace` column. The checks used no model.

MLflow offers an experimental paired comparison of two runs,
`mlflow.genai.compare_evaluations`. With ARCI, you choose a margin of allowed
loss in pass probability. ARCI fixes the rule before fresh paired runs, launches
both versions, and reads the evidence after each round. At the round cap it can
say “cannot tell” (`INCONCLUSIVE`). Another tool, promptfoo, reports per-test
pass-rate ranges for repeats.

In `evaluate_agent.py`, use `sys.argv[1]` to select the version (`pass`
or `fail` in the fixture). ARCI supplies the output filename in `sys.argv[2]`.
If you adapt the fixture script, remove the code that creates a directory at
that path and writes results into it. Keep the SQLite database in a separate
directory. The helper writes one JSON line per task to the supplied file.

Use the same scorer and the same task id for each input on both sides.
Add this to `evaluate_agent.py` after `res = mlflow.genai.evaluate(...)` returns.

```python
import sys
from pathlib import Path

from mlflow_rows import write_jsonl


def word_id(request: object) -> str:
    if isinstance(request, dict) and isinstance(word := request.get("word"), str):
        return word
    raise ValueError("expected a word in the request")


write_jsonl(Path(sys.argv[2]), res.result_df.to_dict("records"), "contains_word", word_id)
```

When prediction crashed on `w07`, the scorer still returned false for the
empty answer. The helper checks `state` before the score. On `w13` the scorer
raised and set its error message. Both rows become errors. A missing, null or
NaN message means there was no scorer error. Boolean scores and the strings
`"yes"` and `"no"` give pass or fail. Other values, including the numbers
1 and 0, give an error. Duplicate task ids stop the export.

Save this complete block as `mlflow_rows.py` beside `evaluate_agent.py`.

```python
"""Export one MLflow evaluation as ARCI task outcomes."""

import json
import math
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path


def mlflow_rows(
    records: Iterable[Mapping[str, object]], scorer: str, task_id: Callable[[object], str]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in records:
        key = task_id(record["request"])
        if key in seen:
            raise ValueError(f"duplicate task id: {key}")
        seen.add(key)

        message = record.get(f"{scorer}/error_message")
        no_error = message is None or (isinstance(message, float) and math.isnan(message))
        value = record.get(f"{scorer}/value")
        outcome = "error"
        state = record.get("state")
        if isinstance(state, str) and state == "OK" and no_error:
            if value is True or (isinstance(value, str) and value == "yes"):
                outcome = "pass"
            elif value is False or (isinstance(value, str) and value == "no"):
                outcome = "fail"
        rows.append({"task_id": key, "outcome": outcome})
    return rows


def write_jsonl(
    path: Path,
    records: Iterable[Mapping[str, object]],
    scorer: str,
    task_id: Callable[[object], str],
) -> None:
    rows = mlflow_rows(records, scorer, task_id)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
```

Run this command in the directory containing `evaluate_agent.py`.

```sh
arci check-change --format jsonl \
  --baseline 'python evaluate_agent.py pass {out}' \
  --candidate 'python evaluate_agent.py fail {out}' \
  --out-dir mlflow-comparison
```

[Fixture script](../../tests/unit/integrations/real/mlflow/evaluate_agent.py.txt) · [Fixture notes](../../tests/unit/integrations/real/README.md)
