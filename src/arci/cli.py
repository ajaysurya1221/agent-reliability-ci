"""Command-line interface for running and inspecting ARCI experiments."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, NoReturn, Protocol, cast

from pydantic import JsonValue

from arci.gate import decide
from arci.mcp_boundary import (
    UpstreamResult,
    request_decision_upstream,
    upstream_diagnostic,
    validate_decision_response,
    validate_models_response,
)
from arci.planning import (
    DEFAULT_N_GRID,
    INTERVAL_METHOD,
    plan,
    plan_to_json,
    render_plan_markdown,
)
from arci.reliability import validate_ks
from arci.replay import make_bundle, replay
from arci.report import render_junit, render_markdown
from arci.runner import run_experiment
from arci.schedule import build_schedule
from arci.schema import (
    DecisionSpec,
    Divergence,
    Manifest,
    MinimizeResult,
    ReplayBundle,
    ReplayStatus,
    TrialEnvelope,
    TrialSpec,
    Verdict,
)
from arci.storage import load_run


class CliError(ValueError):
    """A concise error safe to show to a command-line user."""


class _FirstDivergence(Protocol):
    def __call__(
        self,
        a: TrialEnvelope,
        b: TrialEnvelope,
        *,
        mode: Literal["boundary", "all"] = "boundary",
    ) -> Divergence: ...


class _UpstreamClient(Protocol):
    def __call__(
        self,
        method: str,
        endpoint: str,
        body: dict[str, JsonValue] | None,
        spec: DecisionSpec,
        *,
        api_key: str | None = None,
    ) -> UpstreamResult: ...


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


def _preflight_failure(message: str) -> int:
    _print(message)
    return 3


def _preflight_exception(prefix: str, exc: BaseException) -> int:
    return _preflight_failure(f"{prefix}: {upstream_diagnostic(exc)}")


def _scrub_preflight_value(value: JsonValue, api_key: str) -> JsonValue:
    """Recursively remove the upstream credential from serialised preflight values."""
    if isinstance(value, str):
        return value.replace(api_key, "<redacted>")
    if isinstance(value, list):
        return [_scrub_preflight_value(item, api_key) for item in value]
    if isinstance(value, dict):
        return {
            key.replace(api_key, "<redacted>"): _scrub_preflight_value(item, api_key)
            for key, item in value.items()
        }
    return value


def _scrub_preflight_text(value: object, api_key: str) -> str:
    return str(value).replace(api_key, "<redacted>")


def _cmd_preflight(
    manifest_path: str,
    *,
    allow_unlisted_model: bool = False,
    upstream: _UpstreamClient = request_decision_upstream,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    manifest = Manifest.model_validate_json(Path(manifest_path).read_text(encoding="utf-8"))
    if not manifest.validate_seal():
        return _preflight_failure("manifest seal is invalid")
    spec = manifest.decisions
    if spec is None or spec.upstream != "http":
        return _preflight_failure("nothing to preflight: no http upstream")
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        return _preflight_failure("TYPESAFE_API_KEY is not set")
    try:
        models_result = upstream("GET", "/v1/models", None, spec, api_key=api_key)
        if models_result.error is not None or models_result.status != 200:
            return _preflight_failure("preflight models request failed")
        models = validate_models_response(models_result.body)
    except BaseException as exc:
        return _preflight_exception("preflight models request failed", exc)
    available = sorted(
        cast(str, model["name"]) for model in cast(list[dict[str, JsonValue]], models["models"])
    )
    if spec.model not in available:
        listed = ", ".join(_scrub_preflight_text(model, api_key) for model in available) or "none"
        if not allow_unlisted_model:
            _print(f"pinned model unavailable; account models: {listed}")
            _print(
                "the list may carry only aliases while versioned ids stay accepted; "
                "--allow-unlisted-model verifies the pin with the one smoke request instead"
            )
            return 2
        # The vendor's list carries aliases (`jev-latest`); versioned ids are accepted whether
        # or not they are listed. The smoke request below is the real check: its validated
        # response must report exactly the pinned id, or preflight fails with exit 3.
        _print(
            f"pinned model not listed; account models: {listed}; verifying with the smoke request"
        )
    smoke = cast(
        dict[str, JsonValue],
        {
            "state": "preflight",
            "model": spec.model,
            # The live service requires each question to carry `instructions` or `criteria`
            # (a bare `{"type": "noul"}` is a 400); the fixtures never cared.
            "questions": {
                "ready": {"type": "noul", "instructions": "The endpoint is ready to answer"},
                "route": {
                    "type": "choice",
                    "instructions": "Is the endpoint ready?",
                    "criteria": {"yes": "Ready", "no": "Not ready"},
                },
                "quality": {
                    "type": "score",
                    "instructions": "How ready is the endpoint?",
                    "criteria": ["Low", "High"],
                },
            },
        },
    )
    started = clock()
    try:
        result = upstream("POST", "/v1/systemone", smoke, spec, api_key=api_key)
        latency_ms = max(0.0, (clock() - started) * 1000.0)
        if result.error is not None or result.status != 200:
            return _preflight_failure("preflight smoke request failed")
        body = validate_decision_response(result.body, smoke, spec.model)
    except BaseException as exc:
        return _preflight_exception("preflight smoke request failed", exc)
    usage = cast(dict[str, JsonValue], body["usage"])
    request_id = result.headers.get("x-typesafe-request-id", "")
    endpoint = f"{spec.base_url.rstrip('/')}/v1/systemone"
    _print(f"model: {_scrub_preflight_text(body['model'], api_key)}")
    _print(f"request id: {_scrub_preflight_text(request_id or 'none', api_key)}")
    _print(f"usage: input_tokens={usage['input_tokens']} output_tokens={usage['output_tokens']}")
    _print(f"latency: {latency_ms:.1f} ms")
    receipt = cast(
        JsonValue,
        {
            "preflight": {
                "manifest_sha256": manifest.record_sha256,
                "endpoint": endpoint,
                "model": body["model"],
                "usage": {
                    "input_tokens": usage["input_tokens"],
                    "output_tokens": usage["output_tokens"],
                },
                "request_id": request_id,
                "latency_ms": round(latency_ms, 1),
            }
        },
    )
    scrubbed_receipt = _scrub_preflight_value(receipt, api_key)
    _print(json.dumps(scrubbed_receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0


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


def _cmd_report(run_dir: str, report_format: str, pass_k: str | None = None) -> int:
    ks = () if pass_k is None else validate_ks(_int_list(pass_k, "--pass-k"))
    if ks and report_format != "md":
        raise CliError("--pass-k is reported in the md format only")
    manifest, trials = load_run(run_dir)
    decision = decide(manifest, trials)
    report = (
        render_markdown(manifest, decision, trials, pass_k=ks)
        if report_format == "md"
        else render_junit(manifest, decision, trials)
    )
    _print(report)
    return 0


def _int_list(text: str, flag: str) -> tuple[int, ...]:
    try:
        return tuple(int(value) for value in text.split(","))
    except ValueError:
        raise CliError(f"{flag} must be comma-separated integers") from None


def _cmd_plan(
    *,
    baseline_rate: float,
    candidate_rate: float,
    alpha: float,
    delta: float,
    n_grid: str,
    target_verdict: str,
    target_probability: float,
    output_format: str,
    interval_method: str,
    conditions: int,
    looks: str | None,
) -> int:
    result = plan(
        baseline_rate=baseline_rate,
        candidate_rate=candidate_rate,
        target_verdict=Verdict(target_verdict),
        target_probability=target_probability,
        alpha=alpha,
        delta=delta,
        n_grid=_int_list(n_grid, "--n-grid"),
        interval_method=interval_method,
        conditions=conditions,
        looks=() if looks is None else _int_list(looks, "--looks"),
    )
    if output_format == "json":
        _print(json.dumps(plan_to_json(result), indent=2))
    else:
        _print(render_plan_markdown(result))
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


def _cmd_diff(run_dir: str, trial_a: str, trial_b: str, all_steps: bool) -> int:
    first_divergence = cast(
        _FirstDivergence,
        vars(importlib.import_module("arci.diff"))["first_divergence"],
    )

    _manifest, trials = load_run(run_dir)
    mode: Literal["boundary", "all"] = "all" if all_steps else "boundary"
    divergence = first_divergence(
        _find_trial(trials, trial_a), _find_trial(trials, trial_b), mode=mode
    )
    print(f"mode: {mode}")
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

    preflight = commands.add_parser("preflight", help="check an HTTP decision upstream")
    preflight.add_argument("manifest_json", metavar="MANIFEST")
    preflight.add_argument(
        "--allow-unlisted-model",
        action="store_true",
        help="accept a pinned model missing from GET /v1/models if the smoke request reports it",
    )

    gate = commands.add_parser("gate", help="recompute the gate for a stored run")
    gate.add_argument("run_dir", metavar="RUN_DIR")
    gate.add_argument("--junit", metavar="PATH")
    gate.add_argument("--markdown", metavar="PATH")

    report = commands.add_parser("report", help="render a stored run")
    report.add_argument("run_dir", metavar="RUN_DIR")
    report.add_argument("--format", choices=("md", "junit"), default="md")
    report.add_argument(
        "--pass-k",
        metavar="K,K,...",
        help="opt-in descriptive pass^k per arm and condition (md only; never changes the verdict)",
    )

    plan_command = commands.add_parser(
        "plan",
        help="plan N per arm: exact verdict probabilities under stated assumptions",
        description=(
            "Planning under assumptions, not observed power: for each N per arm, the exact "
            "probability of PASS, BLOCK and INCONCLUSIVE under the gate's fixed-sample "
            "Clopper-Pearson rule, with independent binomial arms at the given true rates. "
            "Domain: clopper_pearson, K=1, one look, N <= 400; other designs are refused."
        ),
    )
    plan_command.add_argument("--baseline-rate", type=float, required=True, metavar="P")
    plan_command.add_argument("--candidate-rate", type=float, required=True, metavar="P")
    plan_command.add_argument("--alpha", type=float, default=0.05)
    plan_command.add_argument("--delta", type=float, default=0.10)
    plan_command.add_argument(
        "--n-grid", default=",".join(map(str, DEFAULT_N_GRID)), metavar="N,N,..."
    )
    plan_command.add_argument(
        "--target-verdict", choices=("PASS", "BLOCK", "INCONCLUSIVE"), required=True
    )
    plan_command.add_argument("--target-probability", type=float, default=0.80, metavar="P")
    plan_command.add_argument(
        "--format", dest="plan_format", choices=("json", "markdown"), default="markdown"
    )
    plan_command.add_argument(
        "--interval-method",
        default=INTERVAL_METHOD,
        metavar="METHOD",
        help="only clopper_pearson is supported",
    )
    plan_command.add_argument(
        "--conditions", type=int, default=1, metavar="K", help="only K=1 is supported"
    )
    plan_command.add_argument(
        "--looks", metavar="N,N,...", help="refused: the planner covers one fixed-sample look"
    )

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
    diff.add_argument("--all-steps", action="store_true")

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
    if command == "preflight":
        return _cmd_preflight(
            cast(str, values["manifest_json"]),
            allow_unlisted_model=cast(bool, values["allow_unlisted_model"]),
        )
    if command == "gate":
        return _cmd_gate(
            cast(str, values["run_dir"]),
            cast(str | None, values["junit"]),
            cast(str | None, values["markdown"]),
        )
    if command == "report":
        return _cmd_report(
            cast(str, values["run_dir"]),
            cast(str, values["format"]),
            cast(str | None, values["pass_k"]),
        )
    if command == "plan":
        return _cmd_plan(
            baseline_rate=cast(float, values["baseline_rate"]),
            candidate_rate=cast(float, values["candidate_rate"]),
            alpha=cast(float, values["alpha"]),
            delta=cast(float, values["delta"]),
            n_grid=cast(str, values["n_grid"]),
            target_verdict=cast(str, values["target_verdict"]),
            target_probability=cast(float, values["target_probability"]),
            output_format=cast(str, values["plan_format"]),
            interval_method=cast(str, values["interval_method"]),
            conditions=cast(int, values["conditions"]),
            looks=cast(str | None, values["looks"]),
        )
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
            cast(bool, values["all_steps"]),
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
