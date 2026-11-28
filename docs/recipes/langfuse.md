# Compare two versions with Langfuse

Langfuse Python SDK 5.2.0 on Python 3.13.12 was
tested with the SDK's `run_experiment` with tracing off and no server; not tested against a live Langfuse.
The client pointed at a local address where no server listened. The fixture ran
20 word checks and saved the returned item results. It used no model.

Keep the task list you pass to the experiment. When the task raised on
`task-w07`, Langfuse left that item out of the results. When the evaluator
raised on `task-w13`, the item came back with no evaluation. The helper writes
an error for each. A named score of true or 1 passes. False or 0 fails.
Any other value gives an error. An unexpected or duplicate task id stops the
export, as do two scores with the requested name on one item.

Let `run_experiment.py` take a version and an output file. Here `pass` and
`fail` select the two fixture versions. If you adapt the fixture script,
replace its output-directory setup and JSON dump. ARCI needs one JSONL file at
the supplied path. Copy the helper below into
`langfuse_rows.py` beside your script. After `res = client.run_experiment(...)`,
pass the ids of the input cases and the items the SDK returned. Use the same
key on both sides.

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

Run this in the script's directory. Each launch should run the experiment afresh.

```sh
arci check-change --format jsonl \
  --baseline 'python run_experiment.py pass {out}' \
  --candidate 'python run_experiment.py fail {out}' \
  --out-dir langfuse-comparison
```

MLflow also compares paired runs, and promptfoo reports per-test pass-rate
ranges for repeats. See [check-change](check-change.md) for ARCI's verdicts.

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

[Fixture script](../../tests/unit/integrations/real/langfuse/run_experiment.py.txt) · [Fixture notes](../../tests/unit/integrations/real/README.md)
