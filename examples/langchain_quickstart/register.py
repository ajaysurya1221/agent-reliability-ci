"""Register the current public model settings before a new experiment; no model calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from configuration import resolve_settings


def register(root: Path) -> None:
    settings = resolve_settings()
    descriptor = root / "arci.yaml"
    data: dict[str, Any] = yaml.safe_load(descriptor.read_text())
    tasks_path = root / data["tasks"]
    tasks = [json.loads(line) for line in tasks_path.read_text().splitlines() if line.strip()]
    for task in tasks:
        task["quickstart_settings"] = settings
    data.setdefault("rule", {})["scenario_seeds"] = (
        "fixed" if settings["baseline"] == "offline:scripted" else "per_round"
    )
    tasks_path.write_text("".join(json.dumps(task) + "\n" for task in tasks))
    descriptor.write_text(yaml.safe_dump(data, sort_keys=False))


if __name__ == "__main__":
    register(Path(__file__).resolve().parent)
    print("Registered model settings; start a new run with arci run arci.yaml")
