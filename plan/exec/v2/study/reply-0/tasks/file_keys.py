"""Read the single fixture value selected by the registered file question."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

# One selector per distinct question, shared by the cells that ask it.
SELECTORS: dict[str, dict[str, str]] = {
    "n1": {"line": r"2\. (.+)"},
    "n2": {"line": r"3\. (.+)"},
    "n3": {"line": r"([^,]+), transport, extension [0-9]+"},
    "n4": {"line": r"([^,]+), accounts, extension [0-9]+"},
    "n5": {"line": r"Action: .+ books the lorry, reference ([\w-]+)\."},
    "n6": {"line": r"Action: (\w+) updates the price list\."},
    "n7": {"line": r"- pick list: (.+)"},
    "n8": {"line": r"- bay: (.+)"},
    "d1": {"where": "sku", "equals": "SKU-1003", "field": "name"},
    "d2": {"where": "sku", "equals": "SKU-1002", "field": "name"},
    "d3": {"where": "order_id", "equals": "ORD-503", "field": "status"},
    "d4": {"where": "order_id", "equals": "ORD-502", "field": "status"},
    "d5": {"line": r"([^,]+), brackets and plugs, .+"},
    "d6": {"line": r"([^,]+), oak and pine, .+"},
    "d7": {"field": "currency"},
    "d8": {"where": "sku", "equals": "SKU-1003", "field": "quantity"},
}


def file_key(path: Path, selector: dict[str, str]) -> str:
    with path.open(encoding="utf-8", newline="") as stream:
        if "where" in selector:
            values = [
                row[selector["field"]]
                for row in csv.DictReader(stream)
                if row[selector["where"]] == selector["equals"]
            ]
        elif "line" in selector:
            pattern = re.compile(selector["line"])
            values = [m[1] for line in stream.read().splitlines() if (m := pattern.fullmatch(line))]
        else:
            value = json.load(stream)[selector["field"]]
            if not isinstance(value, str):
                raise ValueError(f"{path}: expected a string field")
            return value
    if len(values) != 1:
        raise ValueError(f"{path}: {selector} selects {len(values)} rows")
    return values[0]
