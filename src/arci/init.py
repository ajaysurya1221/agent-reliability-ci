"""`arci init`: write a runnable `arci.yaml` for a first experiment (docs/design/0008-arci-init.md).

Validation stops at the first failure, in the ADR's order. In this process, before any user code:
argument syntax, the experiment id, reference syntax, the task JSON, fault syntax and the output
path. Then ONE child process, built like the runner's children (`sys.executable -P` with the
runner's `PYTHONPATH`, which carries the current directory: ADR 0006), imports and resolves the
four references, calls the toolset factory once with the task and seed 0, and reports the tool
names it advertises; explicit fault tools are checked against them. Agents, the oracle, the tools
and `snapshot` are never called, and this process never imports a reference (AGENT_SEMANTICS).

The descriptor is rendered with every string value double-quoted, staged beside the destination,
re-loaded through the descriptor loader and seal-checked, then published atomically: with `--force`
by a rename; without it by a hard link only, so an existing file is never replaced and, where hard
links are unsupported, nothing is published (DECISIONS D-10). Errors are `InitError`, one line,
with nothing written.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import re
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Final, cast

import yaml
from pydantic import JsonValue

from arci.descriptor import (
    DESCRIPTOR_SUFFIXES,
    REF_PATTERN,
    DescriptorError,
    compile_descriptor_text,
)
from arci.perturb import REGISTRY
from arci.runner import child_pythonpath
from arci.schema import N_PER_ARM_MAX, N_PER_ARM_MIN, Manifest

EXPERIMENT_ID_PATTERN: Final = r"[A-Za-z0-9][A-Za-z0-9._-]*"
DEFAULT_N_PER_ARM: Final = 8
DEFAULT_OUT: Final = "arci.yaml"
INIT_FAULTS: Final = ("tool_timeout", "tool_error_once", "empty_result")
REFERENCE_CHECK_SECONDS: Final = 30.0
BASELINE_LABEL: Final = "baseline"
CANDIDATE_LABEL: Final = "candidate"
FAULTS_CONDITION: Final = "faults"
CLEAN_CONDITION: Final = "clean"

HEADER: Final = (
    "# arci experiment descriptor. Schema: `arci schema`.\n"
    "# smoke design: expect INCONCLUSIVE; run arci plan before a confirmatory N\n"
    "# Default: 8 trials per arm; this scaffold does not establish confirmatory power.\n"
    "# Plan before trials: arci plan --help\n"
    "# Never extend this experiment based on its verdict.\n"
)
# From this N per arm a design is not a smoke design (the same bound as `arci run`'s notice).
NON_SMOKE_N: Final = 100

# The flags in validation order; the child resolves the references in this order too.
_REFERENCE_FLAGS: Final = ("--baseline", "--candidate", "--toolset", "--oracle")
_DETAIL_LIMIT: Final = 200
EXPERIMENT_ID_MAX: Final = 200
OCCURRENCE_MAX: Final = 10**9
_ADVERTISED_MAX: Final = 20

assert set(INIT_FAULTS) <= set(REGISTRY), "init offers only registered built-in faults"


class InitError(ValueError):
    """One actionable line; the CLI shows it as `error: CliError: init: <line>`."""


@dataclass(frozen=True, slots=True)
class InitFault:
    """One `--fault NAME[:TOOL[:OCC]]`: TOOL None means any tool; OCC defaults to 0."""

    text: str
    name: str
    tool: str | None
    occurrence: int


@dataclass(frozen=True, slots=True)
class InitRequest:
    experiment_id: str
    baseline: str
    candidate: str
    toolset: str
    oracle: str
    task: dict[str, JsonValue]
    faults: tuple[InitFault, ...]
    n_per_arm: int
    out: Path
    out_text: str
    force: bool

    def references(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            zip(
                _REFERENCE_FLAGS,
                (self.baseline, self.candidate, self.toolset, self.oracle),
                strict=True,
            )
        )


def _show(value: str) -> str:
    """A value as typed when it is plain; otherwise JSON-quoted, so the line stays one line."""
    if value and all(ch.isprintable() and not ch.isspace() for ch in value) and '"' not in value:
        return value
    return json.dumps(value)


def _one_line(text: str) -> str:
    flat = " ".join(text.split())
    flat = "".join(ch if ch.isprintable() else json.dumps(ch)[1:-1] for ch in flat)
    return flat if len(flat) <= _DETAIL_LIMIT else flat[: _DETAIL_LIMIT - 3] + "..."


# --- in-process checks, in the ADR's order -----------------------------------------------------


def _parse_n(text: str) -> int:
    if not (text.isascii() and text.isdecimal() and len(text) <= len(str(N_PER_ARM_MAX))) or not (
        N_PER_ARM_MIN <= int(text) <= N_PER_ARM_MAX
    ):
        raise InitError(
            f"--n must be an integer from {N_PER_ARM_MIN} to {N_PER_ARM_MAX}, got {_show(text)}"
        )
    return int(text)


def _check_out_suffix(out_text: str) -> None:
    if Path(out_text).suffix.lower() not in DESCRIPTOR_SUFFIXES:
        raise InitError(
            f"--out {_show(out_text)}: must end in .yaml or .yml "
            "(arci run reads any other path as a manifest JSON)"
        )


def _check_experiment_id(experiment_id: str) -> None:
    if len(experiment_id) > EXPERIMENT_ID_MAX:
        raise InitError(
            f"experiment id has {len(experiment_id)} characters; at most {EXPERIMENT_ID_MAX} "
            "(it names the run directory)"
        )
    if re.fullmatch(EXPERIMENT_ID_PATTERN, experiment_id) is None:
        raise InitError(
            f"experiment id {_show(experiment_id)} must match {EXPERIMENT_ID_PATTERN} "
            "(it names the run directory)"
        )


def _check_reference(flag: str, ref: str) -> None:
    if re.fullmatch(REF_PATTERN, ref) is None:
        raise InitError(f"{flag} {_show(ref)}: invalid reference; expected module:function")


def _reject_constant(text: str) -> JsonValue:
    raise ValueError(f"{text} is not a JSON number")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"{text} is out of range")
    return value


def _parse_task(flag: str, text: str) -> dict[str, JsonValue]:
    try:
        value = json.loads(text, parse_constant=_reject_constant, parse_float=_finite_float)
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        raise InitError(f"{flag}: invalid JSON ({_one_line(str(exc))})") from None
    if not isinstance(value, dict):
        kind = {list: "an array", str: "a string", bool: "a boolean", type(None): "null"}.get(
            type(value), "a number"
        )
        raise InitError(f"{flag}: must be a JSON object, got {kind}")
    return cast(dict[str, JsonValue], value)


def _read_task_file(path_text: str) -> dict[str, JsonValue]:
    flag = f"--task-file {_show(path_text)}"
    try:
        text = Path(path_text).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise InitError(f"{flag}: not UTF-8 text") from None
    except OSError as exc:
        raise InitError(f"{flag}: cannot read: {exc.strerror or type(exc).__name__}") from None
    return _parse_task(flag, text)


def _parse_fault(text: str) -> InitFault:
    flag = f"--fault {_show(text)}"
    parts = text.split(":")
    if len(parts) > 3:
        raise InitError(f"{flag}: expected NAME[:TOOL[:OCC]]")
    name = parts[0]
    if name not in INIT_FAULTS:
        raise InitError(
            f"{flag}: unknown fault {_show(name)}; expected one of {', '.join(INIT_FAULTS)} "
            "(a custom module:function fault is written by hand in the descriptor)"
        )
    tool = parts[1] if len(parts) > 1 and parts[1] else None
    occurrence = 0
    if len(parts) == 3:
        occ = parts[2]
        if not (
            occ.isascii()
            and occ.isdecimal()
            and len(occ) <= len(str(OCCURRENCE_MAX))
            and int(occ) <= OCCURRENCE_MAX
        ):
            raise InitError(
                f"{flag}: occurrence {_show(occ)} must be an integer from 0 to {OCCURRENCE_MAX}"
            )
        occurrence = int(occ)
    return InitFault(text=text, name=name, tool=tool, occurrence=occurrence)


def _check_output(out: Path, out_text: str, force: bool) -> None:
    shown = _show(out_text)
    try:
        info = os.lstat(out)
    except FileNotFoundError:
        parent = out.parent
        if not parent.is_dir():
            raise InitError(f"output directory {_show(str(parent))} does not exist") from None
        return
    except OSError as exc:
        raise InitError(
            f"output {shown}: cannot inspect: {exc.strerror or type(exc).__name__}"
        ) from None
    if stat.S_ISLNK(info.st_mode):
        raise InitError(f"output {shown} is a symlink; it is never replaced")
    if stat.S_ISDIR(info.st_mode):
        raise InitError(f"output {shown} is a directory; it is never replaced")
    if not stat.S_ISREG(info.st_mode):
        raise InitError(f"output {shown} is not a regular file; it is never replaced")
    if not force:
        raise InitError(f"output {shown} exists; use --force to replace it")


def parse_request(
    *,
    experiment_id: str,
    baseline: str,
    candidate: str,
    toolset: str,
    oracle: str,
    task: str | None,
    task_file: str | None,
    faults: Sequence[str],
    n: str,
    out: str,
    force: bool,
) -> InitRequest:
    """Every in-process check, in the ADR's order; nothing here imports or runs user code."""
    # Argument syntax.
    if task is not None and task_file is not None:
        raise InitError("--task and --task-file are mutually exclusive; give one")
    n_per_arm = _parse_n(n)
    _check_out_suffix(out)
    # The experiment id, then reference syntax, then the task, then faults, then the output.
    _check_experiment_id(experiment_id)
    for flag, ref in zip(_REFERENCE_FLAGS, (baseline, candidate, toolset, oracle), strict=True):
        _check_reference(flag, ref)
    if task is not None:
        task_value = _parse_task("--task", task)
    elif task_file is not None:
        task_value = _read_task_file(task_file)
    else:
        task_value = {}
    parsed_faults = tuple(_parse_fault(text) for text in faults)
    out_path = Path(out)
    _check_output(out_path, out, force)
    return InitRequest(
        experiment_id=experiment_id,
        baseline=baseline,
        candidate=candidate,
        toolset=toolset,
        oracle=oracle,
        task=task_value,
        faults=parsed_faults,
        n_per_arm=n_per_arm,
        out=out_path,
        out_text=out,
        force=force,
    )


# --- the reference check, in one child process ---------------------------------------------------

# Runs as `python -P -c`. The request arrives on stdin; the one-line JSON result leaves on a
# private duplicate of the original stdout, while fd 1 and sys.stdout point at stderr so that
# anything the user's modules print (from Python or from C) never mixes with the result.
_CHILD = r"""
import importlib, json, os, sys
from collections.abc import Mapping

request = json.loads(sys.stdin.read())
result_fd = os.dup(1)
os.dup2(2, 1)
sys.stdout = sys.stderr

def finish(result):
    try:
        sys.stderr.flush()
    except BaseException:
        pass
    os.write(result_fd, (json.dumps(result) + "\n").encode("utf-8"))
    os._exit(0)

def describe(exc):
    return f"{type(exc).__name__}: {exc}"

try:
    from arci.contracts import resolve
except BaseException as exc:
    finish({"ok": False, "kind": "harness", "detail": describe(exc)})

for flag, ref in request["references"]:
    module, _, attribute = ref.partition(":")
    try:
        importlib.import_module(module)
    except BaseException as exc:
        finish({"ok": False, "kind": "import", "flag": flag, "ref": ref, "detail": describe(exc)})
    try:
        resolve(ref)
    except AttributeError as exc:
        finish({"ok": False, "kind": "attribute", "flag": flag, "ref": ref,
                "detail": describe(exc)})
    except TypeError as exc:
        finish({"ok": False, "kind": "callable", "flag": flag, "ref": ref,
                "detail": describe(exc)})
    except BaseException as exc:
        finish({"ok": False, "kind": "resolve", "flag": flag, "ref": ref,
                "detail": type(exc).__name__})

toolset = request["toolset"]
try:
    world = resolve(toolset)(request["task"], 0)
except BaseException as exc:
    finish({"ok": False, "kind": "toolset_call", "ref": toolset, "detail": describe(exc)})
try:
    tools = world.tools
    names = sorted(tools) if isinstance(tools, Mapping) else None
except BaseException:
    names = None
if names is None or not all(isinstance(name, str) for name in names):
    finish({"ok": False, "kind": "toolset_tools", "ref": toolset})
try:
    snapshot_callable = callable(world.snapshot)
except BaseException:
    snapshot_callable = False
if not snapshot_callable:
    finish({"ok": False, "kind": "toolset_snapshot", "ref": toolset})
finish({"ok": True, "tools": names})
"""


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(OSError):
        os.killpg(process.pid, signal.SIGKILL)


def _child_failure(result: dict[str, object]) -> InitError:
    kind = result.get("kind")
    flag = str(result.get("flag", "--toolset"))
    ref = str(result.get("ref", ""))
    detail = _one_line(str(result.get("detail", "")))
    module, _, attribute = ref.partition(":")
    if kind == "import":
        return InitError(
            f"{flag} {ref}: module not importable; importing {module} raised {detail}; "
            "check module and dependencies"
        )
    if kind == "resolve":
        return InitError(f"{flag} {ref}: importable but resolving {attribute} raised {detail}")
    if kind == "attribute":
        return InitError(
            f"{flag} {ref}: module {module} has no attribute {attribute}; check the function name"
        )
    if kind == "callable":
        return InitError(f"{flag} {ref}: {attribute} is not callable; reference a function")
    if kind == "toolset_call":
        return InitError(
            f"--toolset {ref}: calling it with the task and seed 0 raised {detail}; "
            "check the toolset factory and --task"
        )
    if kind == "toolset_tools":
        return InitError(
            f"--toolset {ref}: its result has no .tools mapping of tool names; "
            "return an object with .tools and .snapshot()"
        )
    if kind == "toolset_snapshot":
        return InitError(
            f"--toolset {ref}: its result has no callable .snapshot; "
            "return an object with .tools and .snapshot()"
        )
    return InitError(f"reference check could not start: {detail}")


def _read(handle: IO[bytes]) -> bytes:
    handle.seek(0)
    return handle.read()


def check_references(
    request: InitRequest, *, deadline: float = REFERENCE_CHECK_SECONDS
) -> tuple[str, ...]:
    """Resolve the four references in one child; return the tool names the toolset advertises.

    The child gets `deadline` seconds; on timeout its whole process group is killed. Its stdout
    and stderr go to temporary files, never pipes, so a descendant holding them open cannot stall
    this process. The child's process group is killed on every path, so no descendant that stays
    in that group outlives the check; a descendant that starts its own session (or moves to
    another process group) is outside that boundary and is not killed.
    """
    payload = json.dumps(
        {
            "references": [list(pair) for pair in request.references()],
            "toolset": request.toolset,
            "task": request.task,
        }
    ).encode("utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = child_pythonpath(())
    with (
        tempfile.TemporaryFile() as stdin,
        tempfile.TemporaryFile() as stdout,
        tempfile.TemporaryFile() as stderr,
    ):
        stdin.write(payload)
        stdin.seek(0)
        process = subprocess.Popen(
            [sys.executable, "-P", "-c", _CHILD],
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=env,
            start_new_session=True,
        )
        try:
            returncode = process.wait(timeout=deadline)
        except subprocess.TimeoutExpired:
            _kill_group(process)
            process.wait()
            raise InitError(
                f"reference check did not finish within {deadline:g} s (an import or the "
                "--toolset call hangs); nothing written"
            ) from None
        finally:
            _kill_group(process)
        lines = _read(stdout).decode("utf-8", errors="replace").splitlines()
    try:
        result = cast(dict[str, object], json.loads(lines[-1])) if lines else None
    except ValueError:
        result = None
    if not isinstance(result, dict):
        raise InitError(
            f"reference check process exited with code {returncode} before reporting; "
            "nothing written"
        )
    if result.get("ok") is not True:
        raise _child_failure(result)
    tools = tuple(str(name) for name in cast(list[object], result.get("tools", [])))
    for fault in request.faults:
        if fault.tool is not None and fault.tool not in tools:
            shown = [_show(name) for name in tools[:_ADVERTISED_MAX]]
            if len(tools) > _ADVERTISED_MAX:
                shown.append(f"and {len(tools) - _ADVERTISED_MAX} more")
            advertised = ", ".join(shown) if shown else "none"
            raise InitError(
                f"--fault {_show(fault.text)}: tool {_show(fault.tool)} absent from --toolset "
                f"{request.toolset}; choose an advertised tool ({advertised})"
            )
    return tools


# --- the descriptor -----------------------------------------------------------------------------


class _QuotedDumper(yaml.SafeDumper):
    """Every string scalar double-quoted, so no YAML 1.1 resolver can coerce it."""


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style='"')


_QuotedDumper.add_representer(str, _represent_str)


def _flow(value: JsonValue) -> str:
    """One string or JSON object as a single-line YAML flow value with quoted strings."""
    text = yaml.dump(
        value,
        Dumper=_QuotedDumper,
        default_flow_style=True,
        allow_unicode=True,
        width=2**30,
        sort_keys=False,
    )
    return text.removesuffix("\n...\n").rstrip("\n")


def header(n_per_arm: int) -> str:
    """`HEADER` for a smoke design (N < `NON_SMOKE_N`); otherwise lines 2-3 name the chosen N."""
    if n_per_arm < NON_SMOKE_N:
        return HEADER
    first, _, _, *rest = HEADER.splitlines(keepends=True)
    return "".join(
        [
            first,
            f"# design: {n_per_arm} trials per arm, chosen by you; plan it with arci plan\n",
            "# This file was written by arci init; re-run init or edit to change the design.\n",
            *rest,
        ]
    )


def render_descriptor(request: InitRequest) -> str:
    """The header, then the descriptor keys; every string value is quoted."""
    lines = [
        f"experiment_id: {_flow(request.experiment_id)}",
        f"task: {_flow(request.task)}",
        f"toolset: {_flow(request.toolset)}",
        f"oracle: {_flow(request.oracle)}",
        "baseline:",
        f"  label: {_flow(BASELINE_LABEL)}",
        f"  agent: {_flow(request.baseline)}",
        "candidate:",
        f"  label: {_flow(CANDIDATE_LABEL)}",
        f"  agent: {_flow(request.candidate)}",
        "conditions:",
    ]
    if request.faults:
        lines += [f"  - id: {_flow(FAULTS_CONDITION)}", "    faults:"]
        for fault in request.faults:
            lines += [
                f"      - name: {_flow(fault.name)}",
                '        bucket: "falsify"',
            ]
            if fault.tool is not None:
                lines.append(f"        tool: {_flow(fault.tool)}")
            lines.append(f"        occurrence: {fault.occurrence}")
    else:
        lines.append(f"  - id: {_flow(CLEAN_CONDITION)}")
    lines.append(f"n_per_arm: {request.n_per_arm}")
    return header(request.n_per_arm) + "\n".join(lines) + "\n"


def _verify(request: InitRequest, staged: Path) -> Manifest:
    """Re-load the staged bytes through the descriptor loader and check the seal and content."""
    try:
        manifest = compile_descriptor_text(staged.read_text(encoding="utf-8"), request.out_text)
    except DescriptorError as exc:
        raise InitError(f"the written descriptor does not load: {exc}") from None
    expected = (
        request.experiment_id,
        request.experiment_id,
        request.task,
        request.toolset,
        request.oracle,
        request.baseline,
        request.candidate,
        request.n_per_arm,
    )
    actual = (
        manifest.experiment_id,
        manifest.task_id,
        manifest.task,
        manifest.toolset,
        manifest.contract.oracle,
        manifest.baseline.agent,
        manifest.candidate.agent,
        manifest.n_per_arm,
    )
    if not manifest.validate_seal() or actual != expected:
        raise InitError("the written descriptor did not round-trip; nothing written")
    return manifest


def _umask() -> int:
    mask = os.umask(0o022)
    os.umask(mask)
    return mask


def _exists(request: InitRequest) -> InitError:
    return InitError(f"output {_show(request.out_text)} exists; use --force to replace it")


def _fsync_directory(directory: Path) -> None:
    """Make a published entry durable where the platform allows; errors are ignored."""
    with contextlib.suppress(OSError):
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def publish(request: InitRequest, text: str) -> None:
    """Stage beside the destination, verify, then publish atomically. Nothing is left on error.

    The staged bytes are fsynced first. With --force the staged file replaces the destination by a
    rename. Without it the only publication is a hard link, which refuses an existing destination;
    where hard links are unsupported nothing is published (no copy, no replacing rename).
    """
    staged: Path | None = None
    try:
        fd, staged_name = tempfile.mkstemp(
            prefix=f".{request.out.name}.", suffix=".tmp", dir=request.out.parent
        )
        staged = Path(staged_name)
        try:
            handle = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
        except BaseException:
            os.close(fd)
            raise
        with handle:
            handle.write(text)
            handle.flush()
            # mkstemp creates 0600; give the descriptor the mode an ordinary new file would get.
            os.fchmod(handle.fileno(), 0o666 & ~_umask())
            os.fsync(handle.fileno())
        _verify(request, staged)
        # Re-checked at the last moment: a directory or symlink is never replaced, and without
        # --force a file that appeared meanwhile is not replaced either.
        _check_output(request.out, request.out_text, request.force)
        if request.force:
            os.replace(staged, request.out)
        else:
            try:
                os.link(staged, request.out)
            except FileExistsError:
                raise _exists(request) from None
            except OSError:
                raise InitError(
                    f"output {_show(request.out_text)}: cannot publish atomically here "
                    "(hard links unsupported); choose another directory or pass --force"
                ) from None
        _fsync_directory(request.out.parent)
    except OSError as exc:
        raise InitError(
            f"output {_show(request.out_text)}: cannot write: {exc.strerror or type(exc).__name__}"
        ) from None
    finally:
        if staged is not None:
            with contextlib.suppress(OSError):
                staged.unlink()


def next_command(request: InitRequest) -> str:
    """`arci run PATH`, shell-quoted; `--` first when PATH starts with `-`, so it is not a flag."""
    separator = "-- " if request.out_text.startswith("-") else ""
    return f"arci run {separator}{shlex.quote(request.out_text)}"


def run_init(request: InitRequest, *, deadline: float = REFERENCE_CHECK_SECONDS) -> str:
    """Check the references, write the descriptor, return the one stdout line."""
    check_references(request, deadline=deadline)
    publish(request, render_descriptor(request))
    return next_command(request)
