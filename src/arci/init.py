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

Durability is best effort: the staged file and its directory are fsynced, but on macOS `os.fsync`
is not `F_FULLFSYNC`, so a published descriptor may not survive a power loss there.
"""

from __future__ import annotations

import contextlib
import errno
import importlib.util
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
    request: InitRequest,
    *,
    deadline: float = REFERENCE_CHECK_SECONDS,
    import_paths: Sequence[str] = (),
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
    env["PYTHONPATH"] = child_pythonpath(import_paths)
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


# `os.link` errnos that mean "this filesystem does not do hard links" (on Linux ENOTSUP is
# EOPNOTSUPP; EPERM is what some filesystems, FAT among them, return for link(2)).
_LINKS_UNSUPPORTED: Final = frozenset({errno.EOPNOTSUPP, errno.ENOTSUP, errno.EPERM})


def _link_failure(request: InitRequest, exc: OSError) -> InitError:
    """The hard-link publication failed: name unsupported links, otherwise the actual cause."""
    shown = _show(request.out_text)
    if exc.errno in _LINKS_UNSUPPORTED:
        return InitError(
            f"output {shown}: cannot publish atomically here "
            "(hard links unsupported); choose another directory or pass --force"
        )
    name = errno.errorcode.get(exc.errno, str(exc.errno)) if exc.errno is not None else "unknown"
    reason = exc.strerror or type(exc).__name__
    return InitError(f"output {shown}: cannot publish: {reason} (errno {name})")


def publish(request: InitRequest, text: str) -> None:
    """Stage beside the destination, verify, then publish atomically. Nothing is left on error.

    The staged bytes are fsynced first. With --force the staged file replaces the destination by a
    rename. Without it the only publication is a hard link, which refuses an existing destination;
    where hard links are unsupported nothing is published (no copy, no replacing rename), and any
    other link failure is reported with its errno, also publishing nothing. The fsyncs are best
    effort: on macOS `os.fsync` is not `F_FULLFSYNC` (see the module docstring).
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
            except OSError as exc:
                raise _link_failure(request, exc) from None
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


# Self-contained wheel templates; kept byte-for-byte in sync with the runnable example.
# These are source text, never framework imports in the core process.
LANGCHAIN_FILES: Final[dict[str, str]] = {
    "tools.py": r'''
"""A fresh, seeded order desk for each trial; no external service or shared state."""

from __future__ import annotations

import copy
import random
from typing import cast

from langchain_core.tools import StructuredTool
from pydantic import JsonValue

from arci.adapters.langchain import ToolEnv


def make_tools(task: dict[str, JsonValue], seed: int) -> ToolEnv:
    rng = random.Random(seed)
    order_id = str(task["order_id"])
    sku = f"SKU-{rng.randrange(1000, 9999)}"
    order: dict[str, JsonValue] = {
        "sku": sku,
        "total_cents": rng.randrange(1000, 20000),
        "refunded_cents": 0,
        "notes": [],
    }
    stock = rng.randrange(1, 50)

    def lookup_order(order_id: str) -> dict[str, JsonValue]:
        """Read an order's SKU, paid amount, refund and notes before changing it."""
        if order_id != str(task["order_id"]):
            raise ValueError("unknown order")
        return copy.deepcopy(order)

    def check_stock(sku: str) -> int:
        """Return the current available quantity for a SKU."""
        if sku != order["sku"]:
            raise ValueError("unknown SKU")
        return stock

    def issue_refund(order_id: str, amount_cents: int) -> str:
        """Refund the full paid amount; repeating the same refund is idempotent."""
        lookup_order(order_id)
        if amount_cents != order["total_cents"]:
            raise ValueError("refund must equal the paid amount")
        order["refunded_cents"] = amount_cents
        return "refunded"

    def add_note(order_id: str, note: str) -> str:
        """Append an exact service note once; repeating the same note is idempotent."""
        lookup_order(order_id)
        notes = cast(list[JsonValue], order["notes"])
        if note not in notes:
            notes.append(note)
        return "saved"

    def snapshot() -> dict[str, JsonValue]:
        return {"order_id": order_id, "order": copy.deepcopy(order), "stock": stock}

    return ToolEnv(
        [
            StructuredTool.from_function(fn)
            for fn in (lookup_order, check_stock, issue_refund, add_note)
        ],
        snapshot=snapshot,
    )
'''.lstrip("\n"),
    "agent.py": r'''
"""Different model ids keep both arms' retry and inference settings equal.

Exception: reasoning=False is passed only for Ollama; other providers keep their
default reasoning policy. Equal ids (including offline) compare removing a retry.
"""

from __future__ import annotations

from typing import Any

from configuration import resolve_settings, validate_registration
from langchain.agents.middleware import ToolRetryMiddleware
from langchain.chat_models import init_chat_model
from offline_model import OfflineModel
from pydantic import JsonValue
from tools import make_tools

from arci.adapters.langchain import ToolEnv, make_adapter


def settings(candidate: bool) -> dict[str, Any]:
    registered = resolve_settings()
    arm = "candidate" if candidate else "baseline"
    model_id = str(registered[arm])
    # Shared temperature; reasoning=False only for Ollama, provider defaults otherwise.
    inference: dict[str, Any] = {"temperature": registered["temperature"]}
    if registered[f"{arm}_reasoning"] is False:
        inference["reasoning"] = False
    model = (
        init_chat_model(model_id, **inference)
        if model_id != "offline:scripted"
        else OfflineModel(responses=[])
    )
    # Different ids isolate the model swap; equal ids retain the retry-change demo.
    model_swap = registered["baseline"] != registered["candidate"]
    retry = ToolRetryMiddleware(
        max_retries=0 if candidate and not model_swap else 1,
        initial_delay=0,
        jitter=False,
        retry_on=(TimeoutError, RuntimeError),
        on_failure="continue",
    )
    return {
        "model": model,
        "middleware": [retry],
        "system_prompt": (
            "Use the order desk tools. Read the order first. Refund exactly its total_cents. "
            "For stock notes, read its SKU stock and write exactly 'stock: N'. "
            "Only add a note when the task asks for one. For refund notes write exactly "
            "'refunded'. A plain refund needs no note. Retry an empty lookup once."
        ),
    }


def baseline_settings() -> dict[str, Any]:
    return settings(False)


def candidate_settings() -> dict[str, Any]:
    return settings(True)


def registered_tools(task: dict[str, JsonValue], seed: int) -> ToolEnv:
    registered = validate_registration(task)
    if registered["baseline"] == "offline:scripted":
        OfflineModel.validate_prompt(task.get("input"))
    return make_tools(task, seed)


toolset, baseline, candidate = make_adapter(
    registered_tools,
    baseline_settings,
    candidate_settings,
    # Keys are fault kinds, not perturbation names such as 'tool_timeout'.
    fault_exceptions={"timeout": TimeoutError, "error": RuntimeError},
)
'''.lstrip("\n"),
    "offline_model.py": r'''
"""A small scripted stand-in, not an LLM: read tool results instead of memorising seeds."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from typing import Any, cast

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool


class OfflineModel(FakeMessagesListChatModel):
    """One policy for both arms: abandon on a tool error that middleware did not recover."""

    @staticmethod
    def validate_prompt(prompt: object) -> str:
        if (
            not isinstance(prompt, str)
            or re.fullmatch(
                r"(?:Refund order ORD-\d+(?: and add a refunded note)?|"
                r"Check stock for order ORD-\d+ and add a stock note)\.",
                prompt,
            )
            is None
        ):
            raise ValueError(
                "offline model only solves the shipped task wording; "
                "replace the offline model when replacing tasks"
            )
        return prompt

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return cast(Runnable[LanguageModelInput, AIMessage], self)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        prompt = self.validate_prompt(next(m.text for m in messages if isinstance(m, HumanMessage)))
        match = re.search(r"ORD-\d+", prompt)
        if match is None:
            raise ValueError("expected an order id")
        order_id = match.group()
        replies = [m for m in messages if isinstance(m, ToolMessage)]
        results: dict[str, Any] = {}
        for reply in replies:
            if reply.status == "error":
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Done"))])
            try:
                results[str(reply.name)] = json.loads(reply.text)
            except ValueError:
                results[str(reply.name)] = reply.text
        name, args = "", {}
        order = results.get("lookup_order")
        if not order:
            # An empty read is not proof of success: both arms retry it.
            name, args = "lookup_order", {"order_id": order_id}
        elif prompt.startswith("Refund") and "issue_refund" not in results:
            name, args = (
                "issue_refund",
                {"order_id": order_id, "amount_cents": order["total_cents"]},
            )
        elif prompt.startswith("Check") and "check_stock" not in results:
            name, args = "check_stock", {"sku": order["sku"]}
        elif "note" in prompt and "add_note" not in results:
            note = "refunded" if prompt.startswith("Refund") else f"stock: {results['check_stock']}"
            name, args = "add_note", {"order_id": order_id, "note": note}
        response = (
            AIMessage(content="Done")
            if not name
            else AIMessage(
                content="", tool_calls=[{"name": name, "args": args, "id": f"call-{len(replies)}"}]
            )
        )
        return ChatResult(generations=[ChatGeneration(message=response)])
'''.lstrip("\n"),
    "configuration.py": r'''
"""Resolve public inference settings, also stored in each sealed suite task."""

from __future__ import annotations

import math
import os

from pydantic import JsonValue


def resolve_settings() -> dict[str, JsonValue]:
    baseline = os.environ.get("ARCI_QUICKSTART_BASELINE")
    candidate = os.environ.get("ARCI_QUICKSTART_CANDIDATE")
    if (baseline is None) != (candidate is None):
        raise ValueError(
            "set both ARCI_QUICKSTART_BASELINE and ARCI_QUICKSTART_CANDIDATE, or neither"
        )
    real = baseline is not None
    if real and any(
        not value or ":" not in value or value == "offline:scripted" or value.strip() != value
        for value in (baseline, candidate)
    ):
        raise ValueError("both model ids must be nonempty provider:model identifiers")
    temperature = float(os.environ.get("ARCI_QUICKSTART_TEMPERATURE", "0.7" if real else "0"))
    if (
        not math.isfinite(temperature)
        or (real and temperature <= 0)
        or (not real and temperature != 0)
    ):
        raise ValueError(
            "temperature must be finite and above 0 for real models, exactly 0 offline"
        )
    return {
        "baseline": baseline or "offline:scripted",
        "candidate": candidate or "offline:scripted",
        "temperature": temperature,
        "baseline_reasoning": False
        if baseline and baseline.startswith("ollama:")
        else "provider_default"
        if real
        else "not_applicable",
        "candidate_reasoning": False
        if candidate and candidate.startswith("ollama:")
        else "provider_default"
        if real
        else "not_applicable",
    }


def validate_registration(task: dict[str, JsonValue]) -> dict[str, JsonValue]:
    settings = resolve_settings()
    if task.get("quickstart_settings") != settings:
        raise ValueError(
            "quickstart environment disagrees with registered settings; "
            "run python register.py before starting a new experiment"
        )
    return settings
'''.lstrip("\n"),
    "register.py": r'''
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
    model_swap = settings["baseline"] != settings["candidate"]
    # ArmSpec.label accepts any string, so preserve the full provider:model ids.
    for arm, fixed in (("baseline", "retry"), ("candidate", "no-retry")):
        if isinstance(data[arm], str):  # a bare `module:function` arm is also valid
            data[arm] = {"agent": data[arm]}
        data[arm]["label"] = settings[arm] if model_swap else fixed
    tasks_path.write_text("".join(json.dumps(task) + "\n" for task in tasks))
    descriptor.write_text(yaml.safe_dump(data, sort_keys=False))


if __name__ == "__main__":
    register(Path(__file__).resolve().parent)
    print("Registered model settings; start a new run with arci run arci.yaml")
'''.lstrip("\n"),
    "check.py": r'''
"""Grade business state only; an agent's claimed success never decides the grade."""

from __future__ import annotations

from pydantic import JsonValue


def check(task: dict[str, JsonValue], final_state: dict[str, JsonValue]) -> bool:
    action = task["action"]
    if action not in ("refund", "refund_note", "stock_note"):
        raise ValueError(f"unknown grading action: {action!r}")
    state = final_state.get("state")
    if not isinstance(state, dict) or state.get("order_id") != task["order_id"]:
        return False
    order = state.get("order")
    if not isinstance(order, dict):
        return False
    refund = order.get("total_cents") if action in {"refund", "refund_note"} else 0
    notes = (
        []
        if action == "refund"
        else ["refunded" if action == "refund_note" else f"stock: {state.get('stock')}"]
    )
    return order.get("refunded_cents") == refund and (
        action == "refund" or order.get("notes") == notes
    )
'''.lstrip("\n"),
    "tasks.jsonl": (
        '{"id": "desk-01", "input": "Refund order ORD-101.", "order_id": "ORD-1'
        '01", "action": "refund", "quickstart_settings": {"baseline": "offline:'
        'scripted", "candidate": "offline:scripted", "temperature": 0.0, "basel'
        'ine_reasoning": "not_applicable", "candidate_reasoning": "not_applicab'
        'le"}}\n'
        '{"id": "desk-02", "input": "Refund order ORD-102 and add a refunded no'
        'te.", "order_id": "ORD-102", "action": "refund_note", "quickstart_sett'
        'ings": {"baseline": "offline:scripted", "candidate": "offline:scripted'
        '", "temperature": 0.0, "baseline_reasoning": "not_applicable", "candid'
        'ate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-03", "input": "Check stock for order ORD-103 and add a st'
        'ock note.", "order_id": "ORD-103", "action": "stock_note", "quickstart'
        '_settings": {"baseline": "offline:scripted", "candidate": "offline:scr'
        'ipted", "temperature": 0.0, "baseline_reasoning": "not_applicable", "c'
        'andidate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-04", "input": "Refund order ORD-104.", "order_id": "ORD-1'
        '04", "action": "refund", "quickstart_settings": {"baseline": "offline:'
        'scripted", "candidate": "offline:scripted", "temperature": 0.0, "basel'
        'ine_reasoning": "not_applicable", "candidate_reasoning": "not_applicab'
        'le"}}\n'
        '{"id": "desk-05", "input": "Refund order ORD-105 and add a refunded no'
        'te.", "order_id": "ORD-105", "action": "refund_note", "quickstart_sett'
        'ings": {"baseline": "offline:scripted", "candidate": "offline:scripted'
        '", "temperature": 0.0, "baseline_reasoning": "not_applicable", "candid'
        'ate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-06", "input": "Check stock for order ORD-106 and add a st'
        'ock note.", "order_id": "ORD-106", "action": "stock_note", "quickstart'
        '_settings": {"baseline": "offline:scripted", "candidate": "offline:scr'
        'ipted", "temperature": 0.0, "baseline_reasoning": "not_applicable", "c'
        'andidate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-07", "input": "Refund order ORD-107.", "order_id": "ORD-1'
        '07", "action": "refund", "quickstart_settings": {"baseline": "offline:'
        'scripted", "candidate": "offline:scripted", "temperature": 0.0, "basel'
        'ine_reasoning": "not_applicable", "candidate_reasoning": "not_applicab'
        'le"}}\n'
        '{"id": "desk-08", "input": "Refund order ORD-108 and add a refunded no'
        'te.", "order_id": "ORD-108", "action": "refund_note", "quickstart_sett'
        'ings": {"baseline": "offline:scripted", "candidate": "offline:scripted'
        '", "temperature": 0.0, "baseline_reasoning": "not_applicable", "candid'
        'ate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-09", "input": "Check stock for order ORD-109 and add a st'
        'ock note.", "order_id": "ORD-109", "action": "stock_note", "quickstart'
        '_settings": {"baseline": "offline:scripted", "candidate": "offline:scr'
        'ipted", "temperature": 0.0, "baseline_reasoning": "not_applicable", "c'
        'andidate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-10", "input": "Refund order ORD-110.", "order_id": "ORD-1'
        '10", "action": "refund", "quickstart_settings": {"baseline": "offline:'
        'scripted", "candidate": "offline:scripted", "temperature": 0.0, "basel'
        'ine_reasoning": "not_applicable", "candidate_reasoning": "not_applicab'
        'le"}}\n'
        '{"id": "desk-11", "input": "Refund order ORD-111 and add a refunded no'
        'te.", "order_id": "ORD-111", "action": "refund_note", "quickstart_sett'
        'ings": {"baseline": "offline:scripted", "candidate": "offline:scripted'
        '", "temperature": 0.0, "baseline_reasoning": "not_applicable", "candid'
        'ate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-12", "input": "Check stock for order ORD-112 and add a st'
        'ock note.", "order_id": "ORD-112", "action": "stock_note", "quickstart'
        '_settings": {"baseline": "offline:scripted", "candidate": "offline:scr'
        'ipted", "temperature": 0.0, "baseline_reasoning": "not_applicable", "c'
        'andidate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-13", "input": "Refund order ORD-113.", "order_id": "ORD-1'
        '13", "action": "refund", "quickstart_settings": {"baseline": "offline:'
        'scripted", "candidate": "offline:scripted", "temperature": 0.0, "basel'
        'ine_reasoning": "not_applicable", "candidate_reasoning": "not_applicab'
        'le"}}\n'
        '{"id": "desk-14", "input": "Refund order ORD-114 and add a refunded no'
        'te.", "order_id": "ORD-114", "action": "refund_note", "quickstart_sett'
        'ings": {"baseline": "offline:scripted", "candidate": "offline:scripted'
        '", "temperature": 0.0, "baseline_reasoning": "not_applicable", "candid'
        'ate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-15", "input": "Check stock for order ORD-115 and add a st'
        'ock note.", "order_id": "ORD-115", "action": "stock_note", "quickstart'
        '_settings": {"baseline": "offline:scripted", "candidate": "offline:scr'
        'ipted", "temperature": 0.0, "baseline_reasoning": "not_applicable", "c'
        'andidate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-16", "input": "Refund order ORD-116.", "order_id": "ORD-1'
        '16", "action": "refund", "quickstart_settings": {"baseline": "offline:'
        'scripted", "candidate": "offline:scripted", "temperature": 0.0, "basel'
        'ine_reasoning": "not_applicable", "candidate_reasoning": "not_applicab'
        'le"}}\n'
        '{"id": "desk-17", "input": "Refund order ORD-117 and add a refunded no'
        'te.", "order_id": "ORD-117", "action": "refund_note", "quickstart_sett'
        'ings": {"baseline": "offline:scripted", "candidate": "offline:scripted'
        '", "temperature": 0.0, "baseline_reasoning": "not_applicable", "candid'
        'ate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-18", "input": "Check stock for order ORD-118 and add a st'
        'ock note.", "order_id": "ORD-118", "action": "stock_note", "quickstart'
        '_settings": {"baseline": "offline:scripted", "candidate": "offline:scr'
        'ipted", "temperature": 0.0, "baseline_reasoning": "not_applicable", "c'
        'andidate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-19", "input": "Refund order ORD-119.", "order_id": "ORD-1'
        '19", "action": "refund", "quickstart_settings": {"baseline": "offline:'
        'scripted", "candidate": "offline:scripted", "temperature": 0.0, "basel'
        'ine_reasoning": "not_applicable", "candidate_reasoning": "not_applicab'
        'le"}}\n'
        '{"id": "desk-20", "input": "Refund order ORD-120 and add a refunded no'
        'te.", "order_id": "ORD-120", "action": "refund_note", "quickstart_sett'
        'ings": {"baseline": "offline:scripted", "candidate": "offline:scripted'
        '", "temperature": 0.0, "baseline_reasoning": "not_applicable", "candid'
        'ate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-21", "input": "Check stock for order ORD-121 and add a st'
        'ock note.", "order_id": "ORD-121", "action": "stock_note", "quickstart'
        '_settings": {"baseline": "offline:scripted", "candidate": "offline:scr'
        'ipted", "temperature": 0.0, "baseline_reasoning": "not_applicable", "c'
        'andidate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-22", "input": "Refund order ORD-122.", "order_id": "ORD-1'
        '22", "action": "refund", "quickstart_settings": {"baseline": "offline:'
        'scripted", "candidate": "offline:scripted", "temperature": 0.0, "basel'
        'ine_reasoning": "not_applicable", "candidate_reasoning": "not_applicab'
        'le"}}\n'
        '{"id": "desk-23", "input": "Refund order ORD-123 and add a refunded no'
        'te.", "order_id": "ORD-123", "action": "refund_note", "quickstart_sett'
        'ings": {"baseline": "offline:scripted", "candidate": "offline:scripted'
        '", "temperature": 0.0, "baseline_reasoning": "not_applicable", "candid'
        'ate_reasoning": "not_applicable"}}\n'
        '{"id": "desk-24", "input": "Check stock for order ORD-124 and add a st'
        'ock note.", "order_id": "ORD-124", "action": "stock_note", "quickstart'
        '_settings": {"baseline": "offline:scripted", "candidate": "offline:scr'
        'ipted", "temperature": 0.0, "baseline_reasoning": "not_applicable", "c'
        'andidate_reasoning": "not_applicable"}}\n'
    ),
    "arci.yaml": r"""
# A planted, seed-deterministic offline regression: expect BLOCK at round 1.
# Replace the task file and agent settings before registering your own experiment.
suite_id: langchain-order-desk
tasks: tasks.jsonl
toolset: agent:toolset
oracle: check:check
baseline: {label: retry, agent: 'agent:baseline'}
candidate: {label: no-retry, agent: 'agent:candidate'}
conditions:
  - id: clean
  - id: tool_timeout
    faults: [{name: tool_timeout, tool: lookup_order, occurrence: 0}]
  - id: tool_error_once
    faults: [{name: tool_error_once, tool: lookup_order, occurrence: 0}]
  - id: empty_result
    faults: [{name: empty_result, tool: lookup_order, occurrence: 0}]
# Default alpha=1/20, delta=1/10, stakes=[1/4,1/2], fixed seeds, five-round cap.
rule: {}
budgets: {max_tool_calls: 6, max_model_steps: 6, max_seconds: 15, grader_seconds: 10}
""".lstrip("\n"),
}


def run_langchain_init() -> str:
    """Publish an offline suite in cwd, never replacing any existing destination.

    All files are staged and checked first. Each publication is an atomic no-clobber
    hard link; handled failures roll back our links. A process kill can leave a
    partial scaffold: publication of several directory entries is not a transaction.
    """
    if importlib.util.find_spec("langchain") is None:
        raise InitError("pip install 'agent-reliability-ci[langchain]>=2.0.0'")
    root = Path.cwd()
    existing = sorted(root.iterdir())
    if existing:
        raise InitError(
            f"output {_show(existing[0].name)} exists; "
            "run arci init --langchain in an empty directory"
        )
    linked: list[tuple[Path, Path]] = []
    try:
        with tempfile.TemporaryDirectory(prefix=".arci-langchain-", dir=root) as temporary:
            stage = Path(temporary)
            try:
                for name, content in LANGCHAIN_FILES.items():
                    with (stage / name).open("w", encoding="utf-8", newline="\n") as handle:
                        handle.write(content)
                        handle.flush()
                        os.fsync(handle.fileno())
                from arci.descriptor import loads_suite_descriptor

                manifest = loads_suite_descriptor(
                    (stage / "arci.yaml").read_text(encoding="utf-8"), str(stage / "arci.yaml")
                )
                if not manifest.validate_seal():
                    raise InitError("the written descriptor did not round-trip; nothing written")
                request = parse_request(
                    experiment_id="langchain-order-desk",
                    baseline="agent:baseline",
                    candidate="agent:candidate",
                    toolset="agent:toolset",
                    oracle="check:check",
                    task=json.dumps(manifest.tasks[0].task),
                    task_file=None,
                    faults=(
                        "tool_timeout:lookup_order:0",
                        "tool_error_once:lookup_order:0",
                        "empty_result:lookup_order:0",
                    ),
                    n="8",
                    out=DEFAULT_OUT,
                    force=False,
                )
                check_references(request, import_paths=(str(stage),))
                for name in LANGCHAIN_FILES:
                    source, destination = stage / name, root / name
                    try:
                        os.link(source, destination)
                    except FileExistsError:
                        raise InitError(
                            f"output {_show(name)} exists; "
                            "run arci init --langchain in an empty directory"
                        ) from None
                    except OSError as exc:
                        if exc.errno in _LINKS_UNSUPPORTED:
                            raise InitError(
                                f"output {_show(name)}: cannot publish atomically here "
                                "(hard links unsupported); choose another directory"
                            ) from None
                        raise
                    linked.append((source, destination))
                _fsync_directory(root)
            except BaseException as exc:
                for source, destination in reversed(linked):
                    with contextlib.suppress(OSError):
                        if os.path.samestat(source.stat(), destination.lstat()):
                            destination.unlink()
                if isinstance(exc, OSError):
                    raise InitError(
                        f"cannot write scaffold: {exc.strerror or type(exc).__name__}"
                    ) from None
                if isinstance(exc, DescriptorError):
                    raise InitError(f"the written descriptor does not load: {exc}") from None
                raise
    except OSError as exc:
        raise InitError(f"cannot write scaffold: {exc.strerror or type(exc).__name__}") from None
    return "LANGSMITH_TRACING=false LANGSMITH_TRACING_V2=false arci run arci.yaml"
