"""Orchestrator-only real-log entry point. This spike is tested on synthetic roots."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from time import perf_counter
from typing import NoReturn

from daytable import build_daytable
from decide import SPECS, decide_days
from readers import discover_claude, discover_codex, read_claude, read_codex
from records import EFFORTS, JSON, MODEL

NAMES = EFFORTS | frozenset(
    {
        "claude",
        "codex",
        "REAL DROP",
        "NO DROP",
        "CANNOT TELL",
        "too_few_days",
        "self_check",
        "detected",
        "within_margin",
        "uncertain",
        "missing",
        "error",
        "invalid_output",
        "discovery_error",
        "invalid_arguments",
    }
)
DECIMAL = re.compile(r"-?\d+(?:\.\d+)?\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def validate_output(value: JSON) -> None:
    """Walk keys as well as leaves. Model syntax is allowed only in a model field."""

    def walk(item: JSON, key: str = "") -> None:
        if isinstance(item, dict):
            for name, child in item.items():
                if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                    raise ValueError("invalid_output")
                walk(child, name)
        elif isinstance(item, list):
            for child in item:
                walk(child, key)
        elif isinstance(item, str):
            if item in NAMES or DECIMAL.fullmatch(item):
                return
            if DATE.fullmatch(item):
                try:
                    date.fromisoformat(item)
                    return
                except ValueError:
                    pass
            if key == "model" and MODEL.fullmatch(item):
                return
            raise ValueError("invalid_output")
        elif isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("invalid_output")
        elif item is not None and type(item) not in (int, bool):
            raise ValueError("invalid_output")

    walk(value)


def decimal(value: Fraction | None) -> str:
    if value is None:
        return "missing"
    with localcontext() as context:
        context.prec = 24
        return format(Decimal(value.numerator) / Decimal(value.denominator), "f")


def collect(
    claude_root: Path, claude_prefix: str, codex_root: Path, codex_cwd: Path | None
) -> dict[str, JSON]:
    report: dict[str, JSON] = {}
    for tool in ("claude", "codex"):
        start = perf_counter()
        result = (
            read_claude(discover_claude(claude_root, claude_prefix))
            if tool == "claude"
            else read_codex(discover_codex(codex_root, codex_cwd))
        )
        elapsed = perf_counter() - start
        counts = result.counters
        groups: list[JSON] = []
        for (provider, model, effort), days in build_daytable(result.records).items():
            cutoff = max(d.date for d in days) - timedelta(days=14)
            decision = decide_days(days, cutoff, provider)
            log_values = [math.log(d.m1) for d in days if d.m1 is not None and d.m1 > 0]
            measures: dict[str, JSON] = {}
            for name, measure in decision.measures.items():
                measures[name] = {
                    "verdict": measure.verdict,
                    "before_days": measure.before_days,
                    "after_days": measure.after_days,
                    "p_drop": decimal(measure.p_drop),
                    "p_no_drop": decimal(measure.p_no_drop),
                    "p_self": decimal(measure.p_self),
                }
            groups.append(
                {
                    "tool": provider,
                    "model": model,
                    "effort": effort,
                    "cutoff": cutoff.isoformat(),
                    "days": [
                        {
                            "date": d.date.isoformat(),
                            "responses": d.responses,
                            "known_reasoning": d.known_reasoning,
                            "edits": d.edits,
                            "m1": decimal(d.m1),
                            "m2": decimal(d.m2),
                            "m3": decimal(d.m3),
                            "m4": decimal(d.m4),
                        }
                        for d in days
                    ],
                    "usable_days": {
                        name: sum(getattr(d, name) is not None for d in days) for name in SPECS
                    },
                    "log_sd": f"{statistics.stdev(log_values):.8f}"
                    if len(log_values) >= 2
                    else "missing",
                    "decision": {
                        "verdict": decision.verdict,
                        "reason": decision.reason,
                        "self_check_fired": decision.self_check_fired,
                        "measures": measures,
                    },
                }
            )
        shares: dict[str, JSON] = {
            key: decimal(Fraction(counts.responses - missing, counts.responses))
            if counts.responses
            else "missing"
            for key, missing in (
                ("model", counts.lacking_model),
                ("timestamp", counts.lacking_timestamp),
                ("reasoning", counts.lacking_reasoning),
            )
        }
        shares["complete"] = (
            decimal(Fraction(counts.complete_responses, counts.responses))
            if counts.responses
            else "missing"
        )
        report[tool] = {
            "counters": {key: int(value) for key, value in asdict(counts).items()},
            "parse_seconds": f"{elapsed:.8f}",
            "coverage": shares,
            "groups": groups,
        }
    validate_output(report)
    return report


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError("invalid_arguments")


def main(argv: list[str] | None = None) -> int:
    try:
        parser = _Parser(add_help=False)
        parser.add_argument("--claude-root", type=Path, required=True)
        parser.add_argument("--claude-prefix", default="")
        parser.add_argument("--codex-root", type=Path, required=True)
        parser.add_argument("--codex-cwd", type=Path)
        parser.add_argument("--out", type=Path, required=True)
        args = parser.parse_args(argv)
        claude_root: Path = args.claude_root
        codex_root: Path = args.codex_root
        claude_prefix: str = args.claude_prefix
        codex_cwd: Path | None = args.codex_cwd
        output: Path = args.out
        report = collect(claude_root, claude_prefix, codex_root, codex_cwd)
        validate_output(report)
        encoded = json.dumps(report, indent=2, allow_nan=False)
        output.write_text(encoded + "\n", encoding="utf-8")
        print(encoded)
        return 0
    except Exception:
        # Never stringify an exception: OS errors can contain paths and JSON errors input.
        print('{"error": "error"}')
        return 1


if __name__ == "__main__":
    sys.exit(main())
