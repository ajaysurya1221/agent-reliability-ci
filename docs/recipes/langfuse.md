# Compare two versions with Langfuse

The fixture used Langfuse Python SDK 5.2.0 on Python 3.13.12. It ran 20 word
checks with `run_experiment` and saved the returned items. Tracing was off,
and the client pointed at a local address where no server was listening. The
checks used no model. This recipe was not tested against a live Langfuse server.

Keep the task list you pass to the experiment. When the task crashed on
`task-w07`, Langfuse left that item out of the results. When the evaluator
crashed on `task-w13`, the item came back with no evaluation. The helper writes
an error for each. A named score of true or 1 passes. False or 0 fails.
Any other value gives an error. An unexpected or duplicate task id stops the
export, as do two scores with the requested name on one item.

In `run_experiment.py`, use `sys.argv[1]` to select the version (`pass`
or `fail` in the fixture). ARCI supplies the output filename in `sys.argv[2]`.
If you adapt the fixture script, replace the code that creates an output
directory and writes results into it. The helper writes one JSON line for
each input in `cases`, including inputs missing from `res.item_results`.
Use the same task id for each input on both sides.

Add this to `run_experiment.py` after `res = client.run_experiment(...)` returns.

```python
import sys
from pathlib import Path

from langfuse_rows import write_jsonl


def task_id(item):
    return item["metadata"]["task_id"]


write_jsonl(
    Path(sys.argv[2]), [task_id(case) for case in cases], res.item_results,
    "contains_word", task_id,
)
```

Save this complete block as `langfuse_rows.py` beside `run_experiment.py`.

```python
"""Export one Langfuse experiment as ARCI task outcomes."""

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol, TypeVar

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class Evaluation(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def value(self) -> object: ...


class ItemResult(Protocol[T_co]):
    @property
    def item(self) -> T_co: ...
    @property
    def evaluations(self) -> Iterable[Evaluation]: ...


def langfuse_rows(
    expected_ids: Iterable[str],
    item_results: Iterable[ItemResult[T]],
    evaluation: str,
    task_id: Callable[[T], str],
) -> list[dict[str, str]]:
    outcomes: dict[str, str] = {}
    for key in expected_ids:
        if key in outcomes:
            raise ValueError(f"duplicate expected task id: {key}")
        outcomes[key] = "error"

    seen: set[str] = set()
    for result in item_results:
        key = task_id(result.item)
        if key not in outcomes:
            raise ValueError(f"unexpected task id: {key}")
        if key in seen:
            raise ValueError(f"duplicate task id: {key}")
        seen.add(key)
        scores = [e.value for e in result.evaluations if e.name == evaluation]
        if len(scores) > 1:
            raise ValueError(f"duplicate evaluation {evaluation} for {key}")
        if scores and isinstance(value := scores[0], (int, float)):
            if value == 1:
                outcomes[key] = "pass"
            elif value == 0:
                outcomes[key] = "fail"
    return [{"task_id": key, "outcome": outcome} for key, outcome in outcomes.items()]


def write_jsonl(
    path: Path,
    expected_ids: Iterable[str],
    item_results: Iterable[ItemResult[T]],
    evaluation: str,
    task_id: Callable[[T], str],
) -> None:
    rows = langfuse_rows(expected_ids, item_results, evaluation, task_id)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
```

Run this command in the directory containing `run_experiment.py`. Each launch
should run the experiment afresh.

```sh
arci check-change --format jsonl \
  --baseline 'python run_experiment.py pass {out}' \
  --candidate 'python run_experiment.py fail {out}' \
  --out-dir langfuse-comparison
```

MLflow also compares paired runs, and promptfoo reports per-test pass-rate
ranges for repeats. See [check-change](check-change.md) for ARCI's verdicts.

[Fixture script](../../tests/unit/integrations/real/langfuse/run_experiment.py.txt) · [Fixture notes](../../tests/unit/integrations/real/README.md)
