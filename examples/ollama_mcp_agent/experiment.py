"""Run the retry-prompt experiment against a local Ollama model."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from arci.gate import decide
from arci.report import render_markdown
from arci.runner import run_experiment
from arci.schema import (
    ArmSpec,
    Bucket,
    Budgets,
    CommandSpec,
    Condition,
    ContractSpec,
    FaultSpec,
    Manifest,
    McpServerSpec,
)

OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"


def _agent_command(variant: str, model: str) -> CommandSpec:
    return CommandSpec(
        argv=(
            sys.executable,
            "-P",
            "-m",
            "examples.ollama_mcp_agent.agent",
            "--mcp-config",
            "{mcp_config}",
            "--task-file",
            "{task_file}",
            "--prompt-variant",
            variant,
            "--model",
            model,
        )
    )


def build_manifest(
    n_per_arm: int = 30,
    candidate_variant: str = "b",
    model: str = "qwen3.5:4b-mlx",
) -> Manifest:
    if candidate_variant not in {"a", "b"}:
        raise ValueError("candidate_variant must be 'a' or 'b'")
    return Manifest.create(
        experiment_id=f"ollama-retry-{candidate_variant}-{n_per_arm}",
        task_id="confirm-inventory-order",
        task={
            "order_id": "order-7",
            "sku": "widget",
            "quantity": 2,
            "stock": 10,
        },
        mcp_server=McpServerSpec(
            name="inventory",
            argv=(
                sys.executable,
                "-P",
                "-m",
                "arci.mcp_toolset_server",
                "--toolset",
                "examples.retry_agent.world:make_world",
                "--workdir",
                "{workdir}",
                "--seed",
                "{seed}",
            ),
            snapshot="arci.mcp_toolset_server:snapshot",
        ),
        contract=ContractSpec(oracle="examples.retry_agent.world:oracle"),
        baseline=ArmSpec(
            label="prompt-a",
            command=_agent_command("a", model),
            candidate_id=f"ollama-{model}-prompt-a",
        ),
        candidate=ArmSpec(
            label=f"prompt-{candidate_variant}",
            command=_agent_command(candidate_variant, model),
            candidate_id=f"ollama-{model}-prompt-{candidate_variant}",
        ),
        conditions=(
            Condition(
                condition_id="reserve-timeout",
                faults=(
                    FaultSpec(
                        name="tool_timeout",
                        bucket=Bucket.FALSIFY,
                        tool="reserve",
                        at_occurrence=0,
                    ),
                ),
            ),
        ),
        n_per_arm=n_per_arm,
        base_seed=12_000,
        budgets=Budgets(max_tool_calls=12, max_seconds=180, grader_seconds=20),
    )


def check_ollama(model: str) -> None:
    request = urllib.request.Request(OLLAMA_TAGS_URL, method="GET")
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=5.0) as response:
            value: Any = json.loads(response.read())
    except Exception as exc:
        raise RuntimeError("Ollama is not answering at http://127.0.0.1:11434") from exc
    if not isinstance(value, dict) or not isinstance(value.get("models"), list):
        raise RuntimeError("Ollama returned an invalid model list")
    names: set[str] = set()
    for item in value["models"]:
        if isinstance(item, dict):
            for key in ("name", "model"):
                name = item.get(key)
                if isinstance(name, str):
                    names.add(name)
    if model not in names:
        raise RuntimeError(f"Ollama model is not installed: {model}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--out", required=True)
    parser.add_argument("--candidate-variant", choices=("a", "b"), default="b")
    parser.add_argument("--model", default="qwen3.5:4b-mlx")
    return parser


def _one_line(exc: BaseException) -> str:
    detail = str(exc).replace("\r", " ").replace("\n", " ").strip()
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    model = cast(str, args.model)
    try:
        check_ollama(model)
        manifest = build_manifest(
            n_per_arm=cast(int, args.n),
            candidate_variant=cast(str, args.candidate_variant),
            model=model,
        )
        trials = run_experiment(
            manifest,
            Path(cast(str, args.out)),
            max_workers=cast(int, args.workers),
        )
        decision = decide(manifest, trials)
        run_dir = Path(cast(str, args.out)) / manifest.experiment_id
        (run_dir / "decision.json").write_text(
            decision.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        print(render_markdown(manifest, decision, trials), end="")
        return decision.exit_code
    except Exception as exc:
        print(f"error: {_one_line(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
