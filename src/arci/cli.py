"""Command-line interface for running and inspecting ARCI experiments."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NoReturn, cast

from arci.gate import decide
from arci.replay import make_bundle, replay
from arci.report import render_junit, render_markdown
from arci.runner import run_experiment
from arci.schedule import build_schedule
from arci.schema import (
    Divergence,
    Manifest,
    MinimizeResult,
    ReplayBundle,
    ReplayStatus,
    TrialEnvelope,
    TrialSpec,
)
from arci.storage import load_run


class CliError(ValueError):
    """A concise error safe to show to a command-line user."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CliError(message)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _one_line(exc: BaseException) -> str:
    detail = str(exc).splitlines()[0].strip()
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


def _print(text: str) -> None:
    print(text, end="" if text.endswith("\n") else "\n")


def _write(path: str | Path, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def _find_trial(trials: Sequence[TrialEnvelope], trial_id: str) -> TrialEnvelope:
    matches = [trial for trial in trials if trial.trial_id == trial_id]
    if not matches:
        raise CliError(f"trial does not exist: {trial_id}")
    if len(matches) != 1:
        raise CliError(f"trial id is duplicated: {trial_id}")
    return matches[0]


def _find_spec(manifest: Manifest, trial_id: str) -> TrialSpec:
    matches = [spec for spec in build_schedule(manifest) if spec.trial_id == trial_id]
    if not matches:
        raise CliError(f"trial is not in the manifest schedule: {trial_id}")
    if len(matches) != 1:
        raise CliError(f"trial id is duplicated in the manifest schedule: {trial_id}")
    return matches[0]


def _cmd_run(manifest_path: str, out_dir: str, workers: int) -> int:
    manifest = Manifest.model_validate_json(Path(manifest_path).read_text(encoding="utf-8"))
    if not manifest.validate_seal():
        raise CliError("manifest seal is invalid")
    trials = run_experiment(manifest, out_dir, max_workers=workers)
    decision = decide(manifest, trials)
    run_dir = Path(out_dir) / manifest.experiment_id
    _write(run_dir / "decision.json", decision.model_dump_json(indent=2) + "\n")
    _print(render_markdown(manifest, decision, trials))
    return decision.exit_code


def _invalid_store_report(exc: BaseException) -> str:
    return (
        f"# ARCI gate\n\nRun store validation failed: {_one_line(exc)}\n\nVERDICT: ERROR (exit 3)\n"
    )


def _cmd_gate(run_dir: str, junit_path: str | None, markdown_path: str | None) -> int:
    try:
        manifest, trials = load_run(run_dir)
    except Exception as exc:
        _print(_invalid_store_report(exc))
        return 3
    decision = decide(manifest, trials)
    markdown = render_markdown(manifest, decision, trials)
    _write(Path(run_dir) / "decision.json", decision.model_dump_json(indent=2) + "\n")
    _print(markdown)
    if junit_path is not None:
        _write(junit_path, render_junit(manifest, decision, trials))
    if markdown_path is not None:
        _write(markdown_path, markdown)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        _write(summary_path, markdown)
    return decision.exit_code


def _cmd_report(run_dir: str, report_format: str) -> int:
    manifest, trials = load_run(run_dir)
    decision = decide(manifest, trials)
    report = (
        render_markdown(manifest, decision, trials)
        if report_format == "md"
        else render_junit(manifest, decision, trials)
    )
    _print(report)
    return 0


def _cmd_bundle(
    run_dir: str,
    trial_id: str,
    out_path: str,
    root: str | None,
    include: tuple[str, ...],
) -> int:
    manifest, trials = load_run(run_dir)
    trial = _find_trial(trials, trial_id)
    spec = _find_spec(manifest, trial_id)
    bundle = make_bundle(manifest, trial, spec, root=root, include=include)
    _write(out_path, bundle.model_dump_json(indent=2) + "\n")
    print(f"BUNDLE: {out_path}")
    return 0


def _cmd_replay(bundle_path: str) -> int:
    try:
        bundle = ReplayBundle.model_validate_json(Path(bundle_path).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"INVALID: {_one_line(exc)}")
        return 3
    result = replay(bundle)
    print(f"{result.status.value}: {result.detail}")
    return {
        ReplayStatus.REPRODUCED: 0,
        ReplayStatus.NOT_REPRODUCED: 1,
        ReplayStatus.INVALID: 3,
    }[result.status]


def _cmd_diff(run_dir: str, trial_a: str, trial_b: str) -> int:
    first_divergence = cast(
        Callable[[TrialEnvelope, TrialEnvelope], Divergence],
        vars(importlib.import_module("arci.diff"))["first_divergence"],
    )

    _manifest, trials = load_run(run_dir)
    divergence = first_divergence(_find_trial(trials, trial_a), _find_trial(trials, trial_b))
    print(f"common_prefix: {divergence.common_prefix}")
    print(f"left: {divergence.left}")
    print(f"right: {divergence.right}")
    print(f"after_injection: {divergence.after_injection}")
    return 0


def _names(values: Sequence[str]) -> str:
    return ", ".join(values) if values else "none"


def _cmd_minimize(run_dir: str, trial_id: str, out_path: str) -> int:
    minimize_faults = cast(
        Callable[[Manifest, TrialEnvelope, TrialSpec], MinimizeResult],
        vars(importlib.import_module("arci.minimize"))["minimize_faults"],
    )

    manifest, trials = load_run(run_dir)
    trial = _find_trial(trials, trial_id)
    spec = _find_spec(manifest, trial_id)
    result = minimize_faults(manifest, trial, spec)
    _write(out_path, result.bundle.model_dump_json(indent=2) + "\n")
    print(f"kept: {_names(result.kept)}")
    print(f"removed: {_names(result.removed)}")
    print(f"minimality: {result.minimality}")
    print(f"trials_run: {result.trials_run}")
    return 0


def _parser() -> _Parser:
    parser = _Parser(prog="arci")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run a frozen experiment manifest")
    run.add_argument("manifest_json", metavar="MANIFEST_JSON")
    run.add_argument("--out", required=True, metavar="DIR")
    run.add_argument("--workers", type=_positive_int, default=4, metavar="N")

    gate = commands.add_parser("gate", help="recompute the gate for a stored run")
    gate.add_argument("run_dir", metavar="RUN_DIR")
    gate.add_argument("--junit", metavar="PATH")
    gate.add_argument("--markdown", metavar="PATH")

    report = commands.add_parser("report", help="render a stored run")
    report.add_argument("run_dir", metavar="RUN_DIR")
    report.add_argument("--format", choices=("md", "junit"), default="md")

    bundle = commands.add_parser("bundle", help="create a portable failure bundle")
    bundle.add_argument("run_dir", metavar="RUN_DIR")
    bundle.add_argument("trial_id", metavar="TRIAL_ID")
    bundle.add_argument("--out", required=True, metavar="PATH")
    bundle.add_argument("--root", metavar="DIR")
    bundle.add_argument("--include", action="append", default=[], metavar="RELPATH")

    replay_command = commands.add_parser("replay", help="replay a failure bundle")
    replay_command.add_argument("bundle_json", metavar="BUNDLE_JSON")

    diff = commands.add_parser("diff", help="find the first divergence between two trials")
    diff.add_argument("run_dir", metavar="RUN_DIR")
    diff.add_argument("trial_a", metavar="TRIAL_A")
    diff.add_argument("trial_b", metavar="TRIAL_B")

    minimize = commands.add_parser("minimize", help="minimize a failing trial's faults")
    minimize.add_argument("run_dir", metavar="RUN_DIR")
    minimize.add_argument("trial_id", metavar="TRIAL_ID")
    minimize.add_argument("--out", required=True, metavar="PATH")
    return parser


def _dispatch(values: dict[str, object]) -> int:
    command = cast(str, values["command"])
    if command == "run":
        return _cmd_run(
            cast(str, values["manifest_json"]),
            cast(str, values["out"]),
            cast(int, values["workers"]),
        )
    if command == "gate":
        return _cmd_gate(
            cast(str, values["run_dir"]),
            cast(str | None, values["junit"]),
            cast(str | None, values["markdown"]),
        )
    if command == "report":
        return _cmd_report(cast(str, values["run_dir"]), cast(str, values["format"]))
    if command == "bundle":
        return _cmd_bundle(
            cast(str, values["run_dir"]),
            cast(str, values["trial_id"]),
            cast(str, values["out"]),
            cast(str | None, values["root"]),
            tuple(cast(list[str], values["include"])),
        )
    if command == "replay":
        return _cmd_replay(cast(str, values["bundle_json"]))
    if command == "diff":
        return _cmd_diff(
            cast(str, values["run_dir"]),
            cast(str, values["trial_a"]),
            cast(str, values["trial_b"]),
        )
    if command == "minimize":
        return _cmd_minimize(
            cast(str, values["run_dir"]),
            cast(str, values["trial_id"]),
            cast(str, values["out"]),
        )
    raise CliError(f"unknown command: {command}")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and translate user-facing errors to exit code 3."""
    try:
        namespace = _parser().parse_args(argv)
        return _dispatch(cast(dict[str, object], vars(namespace)))
    except CliError as exc:
        print(f"error: {_one_line(exc)}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"error: {_one_line(exc)}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
