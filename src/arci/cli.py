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

from arci.demo.run import check_keep, default_workers, run_demo

# --- descriptor ---
from arci.descriptor import (
    DescriptorError,
    compile_descriptor,
    is_descriptor_path,
    render_schema,
)

# --- end descriptor ---
from arci.gate import decide

# --- init ---
from arci.init import (
    DEFAULT_N_PER_ARM,
    DEFAULT_OUT,
    INIT_FAULTS,
    InitError,
    parse_request,
    run_init,
)

# --- end init ---
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


# --- descriptor ---
def _run_manifest(path: str) -> Manifest:
    """`arci.yaml`/`.yml` is compiled and sealed; anything else is sealed JSON, seal checked."""
    if is_descriptor_path(path):
        try:
            return compile_descriptor(path)
        except DescriptorError as exc:
            raise CliError(str(exc)) from None
    manifest = Manifest.model_validate_json(Path(path).read_text(encoding="utf-8"))
    if not manifest.validate_seal():
        raise CliError("manifest seal is invalid")
    return manifest


def _cmd_schema(out_path: str | None) -> int:
    """Print the descriptor's JSON Schema, or write the identical bytes to `out_path`."""
    text = render_schema()
    if out_path is None:
        sys.stdout.write(text)
    else:
        Path(out_path).write_bytes(text.encode("utf-8"))
    return 0


# --- end descriptor ---


# --- init ---
def _cmd_init(values: dict[str, object]) -> int:
    """`arci init`: one stdout line (the next command), empty stderr, exit 0; or exit 3."""
    try:
        request = parse_request(
            experiment_id=cast(str, values["experiment_id"]),
            baseline=cast(str, values["baseline"]),
            candidate=cast(str, values["candidate"]),
            toolset=cast(str, values["toolset"]),
            oracle=cast(str, values["oracle"]),
            task=cast(str | None, values["task"]),
            task_file=cast(str | None, values["task_file"]),
            faults=tuple(cast(list[str], values["fault"])),
            n=cast(str, values["n"]),
            out=cast(str, values["init_out"]),
            force=cast(bool, values["force"]),
        )
        print(run_init(request))
    except InitError as exc:
        raise CliError(f"init: {exc}") from None
    return 0


# --- end init ---


# --- smoke ---
# The smoke notice imports its gate and planner names locally, so that this block stays the only
# place in this module the notice touches.
SMOKE_N_BELOW = 100
_SMOKE_PLAN = (
    "Plan a confirmatory N: arci plan --baseline-rate P --candidate-rate P --target-verdict BLOCK"
)


def _gating_conditions(manifest: Manifest) -> int:
    """K as the gate counts it: conditions with no ceiling fault."""
    from arci.schema import Bucket

    return sum(
        not any(fault.bucket is Bucket.CEILING for fault in condition.faults)
        for condition in manifest.conditions
    )


def _smallest_n(alpha: float, delta: float, *, collapse: bool) -> int | None:
    """The smallest N <= the planner's bound at which the gate's own functions give the verdict.

    Two perfect arms (N/N vs N/N) for PASS; a total collapse (N/N vs 0/N) for BLOCK. One gating
    condition, one look, Clopper-Pearson at the gate's per-arm tail alpha/4: the planner's domain.
    Every N is checked, from 1 up; nothing is assumed about monotonicity.
    """
    from arci.gate import classify
    from arci.planning import MAX_N_PER_ARM, per_arm_tail
    from arci.stats import clopper_pearson_tail, difference_bounds

    tail = per_arm_tail(alpha)
    target = Verdict.BLOCK if collapse else Verdict.PASS
    for n in range(1, MAX_N_PER_ARM + 1):
        bounds = difference_bounds(
            baseline=clopper_pearson_tail(n, n, tail),
            candidate=clopper_pearson_tail(0 if collapse else n, n, tail),
        )
        if classify(*bounds, delta) is target:
            return n
    return None


def _cannot(outcome: str, verdict: str, n: int | None) -> str:
    from arci.planning import MAX_N_PER_ARM

    if n is None:
        return f"{outcome} cannot {verdict} at any N up to {MAX_N_PER_ARM}"
    return f"{outcome} cannot {verdict} below N={n}"


def smoke_notice(manifest: Manifest) -> str | None:
    """The one stderr line `arci run` prints before a smoke design runs, or None.

    It fires when some gating condition has n_per_arm < 100. Inside the planner's domain
    (clopper_pearson, K=1, one look) the thresholds are this manifest's own alpha and delta under
    its fixed-sample Clopper-Pearson rule; otherwise they are given for reference only, under
    Clopper-Pearson with alpha 0.05, delta 0.1, K=1 and one look, and the line says so.
    """
    k = _gating_conditions(manifest)
    n = manifest.n_per_arm
    if k == 0 or n >= SMOKE_N_BELOW:
        return None
    in_domain = (
        manifest.interval_method == INTERVAL_METHOD and k == 1 and manifest.looks in ((), (n,))
    )
    alpha, delta = (manifest.alpha, manifest.delta) if in_domain else (0.05, 0.10)
    rule = (
        "under this design's fixed-sample Clopper\u2013Pearson rule"
        if in_domain
        else f"for reference only, under Clopper\u2013Pearson with alpha {alpha:g}, "
        f"delta {delta:g}, K=1 and one look,"
    )
    return (
        f"SMOKE DESIGN: n_per_arm={n} (alpha {manifest.alpha:g}, delta {manifest.delta:g}, "
        f"K={k}): {rule} "
        f"{_cannot('two perfect arms', 'PASS', _smallest_n(alpha, delta, collapse=False))} and "
        f"{_cannot('a total collapse', 'BLOCK', _smallest_n(alpha, delta, collapse=True))}; "
        f"expect INCONCLUSIVE. {_SMOKE_PLAN}"
    )


def smoke_followup(manifest: Manifest) -> str:
    """The second stderr line, after an INCONCLUSIVE verdict on a design that got the notice."""
    return (
        f"INCONCLUSIVE at n_per_arm={manifest.n_per_arm} is the expected smoke result; "
        "choose a confirmatory N with arci plan before re-running."
    )


# --- end smoke ---


def _cmd_run(manifest_path: str, out_dir: str, workers: int) -> int:
    # --- descriptor ---
    manifest = _run_manifest(manifest_path)
    # --- end descriptor ---
    # --- smoke ---
    notice = smoke_notice(manifest)
    if notice is not None:
        print(notice, file=sys.stderr, flush=True)
    # --- end smoke ---
    trials = run_experiment(manifest, out_dir, max_workers=workers)
    decision = decide(manifest, trials)
    run_dir = Path(out_dir) / manifest.experiment_id
    _write(run_dir / "decision.json", decision.model_dump_json(indent=2) + "\n")
    _print(render_markdown(manifest, decision, trials))
    # --- smoke ---
    if notice is not None and decision.verdict is Verdict.INCONCLUSIVE:
        print(smoke_followup(manifest), file=sys.stderr)
    # --- end smoke ---
    print(f"run store: {run_dir.resolve()}", file=sys.stderr)
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

    # --- descriptor ---
    run = commands.add_parser(
        "run",
        help="run an arci.yaml descriptor or a frozen manifest",
        description=(
            "Run an experiment. A .yaml/.yml path is an arci.yaml descriptor, compiled and "
            "sealed before any trial; any other path is a sealed manifest JSON, seal checked."
        ),
    )
    run.add_argument("manifest_json", metavar="PATH", help="arci.yaml descriptor or manifest JSON")
    run.add_argument("--out", default="runs", metavar="DIR", help="run store (default: runs)")
    # --- end descriptor ---
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

    # --- demo ---
    demo = commands.add_parser(
        "demo",
        help="run the packaged six-step retry story (no clone, no model call)",
        description=(
            "The retry story end to end through the real run, diff, minimize and replay: "
            "agent B drops a retry and is BLOCKed at N=200 per arm, the failure shrinks to "
            "one fault and replays offline, and the repaired agent C passes. Every count is "
            "computed fresh; exit 0 when all six steps hold, 1 when one does not."
        ),
    )
    demo.add_argument(
        "--workers",
        type=_positive_int,
        default=default_workers(),
        metavar="N",
        help="parallel trials (default: min(8, CPU count))",
    )
    demo.add_argument(
        "--keep",
        metavar="DIR",
        help="write the run stores to DIR (empty or new) instead of a kept temporary directory",
    )
    # --- end demo ---
    # --- descriptor ---
    schema = commands.add_parser(
        "schema",
        help="print the arci.yaml JSON Schema",
        description=(
            "Print the JSON Schema of the arci.yaml descriptor, generated from the pydantic "
            "models (which stay authoritative: the schema cannot express cross-field rules)."
        ),
    )
    schema.add_argument("--out", metavar="PATH", help="write the schema to PATH instead")
    # --- end descriptor ---
    # --- init ---
    init = commands.add_parser(
        "init",
        help="write a runnable arci.yaml for a first experiment",
        description=(
            "Write an arci.yaml smoke design from four module:function references, checked at "
            "once in a child process (imported and resolved; the toolset is built once with "
            "the task and seed 0; nothing else is called). Prints the next command."
        ),
    )
    init.add_argument("experiment_id", metavar="EXPERIMENT_ID", help="also the task id")
    init.add_argument("--baseline", required=True, metavar="REF", help="module:function agent")
    init.add_argument("--candidate", required=True, metavar="REF", help="module:function agent")
    init.add_argument(
        "--toolset", required=True, metavar="REF", help="module:function (task, seed) factory"
    )
    init.add_argument(
        "--oracle", required=True, metavar="REF", help="module:function (task, state) -> bool"
    )
    init.add_argument("--task", metavar="JSON", help="the task, a JSON object (default {})")
    init.add_argument("--task-file", metavar="PATH", help="read the task JSON from a UTF-8 file")
    init.add_argument(
        "--fault",
        action="append",
        default=[],
        metavar="NAME[:TOOL[:OCC]]",
        help=(
            f"repeatable; one of {', '.join(INIT_FAULTS)}; TOOL omitted means any tool, OCC "
            "omitted means 0; all faults form one condition, 'faults' (none: 'clean')"
        ),
    )
    init.add_argument(
        "--n",
        default=str(DEFAULT_N_PER_ARM),
        metavar="N",
        help=f"trials per arm (default {DEFAULT_N_PER_ARM}: a smoke design)",
    )
    init.add_argument(
        "--out", dest="init_out", default=DEFAULT_OUT, metavar="PATH", help="default arci.yaml"
    )
    init.add_argument(
        "--force", action="store_true", help="replace an existing regular file at --out"
    )
    # --- end init ---
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
    # --- demo ---
    if command == "demo":
        keep = cast(str | None, values["keep"])
        if keep is not None:
            try:
                check_keep(Path(keep))
            except ValueError as exc:
                raise CliError(str(exc)) from None
        return run_demo(
            workers=cast(int, values["workers"]),
            keep=None if keep is None else Path(keep),
        )
    # --- end demo ---
    # --- descriptor ---
    if command == "schema":
        return _cmd_schema(cast(str | None, values["out"]))
    # --- end descriptor ---
    # --- init ---
    if command == "init":
        return _cmd_init(values)
    # --- end init ---
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
