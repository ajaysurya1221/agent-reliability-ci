"""Read local session logs without exposing private input in errors or reports."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import NoReturn, TextIO, cast

from arci import __version__

from . import claude_code, codex, discover, measures, report
from .decide import decide_tool, error_tool, exit_code
from .html import render_html
from .records import Tool
from .schema import LogsDecision, ToolDecision, seal


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _UsageError(report.USAGE_ERROR)


def _parser() -> _Parser:
    parser = _Parser(prog="realornoise", add_help=False, allow_abbrev=False)
    parser.add_argument("--help", "-h", action="store_true")
    parser.add_argument("--tool", choices=("auto", "claude-code", "codex", "both"), default="auto")
    for name in (
        "since",
        "model",
        "effort",
        "project",
        "claude-dir",
        "codex-dir",
        "markdown",
        "html",
        "json",
    ):
        parser.add_argument(f"--{name}")
    parser.add_argument("--utc", action="store_true")
    parser.add_argument("--example", action="store_true")
    return parser


def _execute(
    argv: Sequence[str],
    *,
    now: datetime | None,
    env: Mapping[str, str] | None,
    home: Path | None,
    out: TextIO,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.help:
        out.write(parser.format_help())
        return 0
    since: date | None = None
    if args.since is not None:
        try:
            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", args.since) is None:
                raise ValueError
            since = date.fromisoformat(args.since)
        except ValueError:
            raise _UsageError(report.SINCE_DATE) from None
    instant = datetime.now().astimezone() if now is None else now
    if args.example:
        from .example import load

        claude_root, codex_root, instant = load()
    else:
        environment = os.environ if env is None else env
        # Avoid resolving HOME or an unused root when explicit directories were supplied.
        root_home = Path.home() if home is None else home
        claude_root = (
            Path(args.claude_dir)
            if args.claude_dir is not None
            else discover.claude_root(environment, root_home)
        )
        codex_root = (
            Path(args.codex_dir)
            if args.codex_dir is not None
            else discover.codex_root(environment, root_home)
        )
    if instant.utcoffset() is None:
        raise _UsageError(report.CALENDAR_RANGE)
    offset = timedelta() if args.utc else instant.utcoffset()
    assert offset is not None
    # The record stores whole offset minutes; the same offset defines all days.
    minutes = offset // timedelta(minutes=1)
    offset = timedelta(minutes=minutes)
    instant = instant.astimezone(UTC)
    roots: dict[Tool, Path] = {"claude-code": claude_root, "codex": codex_root}
    requested: list[Tool]
    if args.tool == "auto":
        requested = [
            tool
            for tool, root in roots.items()
            if root.exists()
            or (
                args.claude_dir is not None if tool == "claude-code" else args.codex_dir is not None
            )
        ] or list(roots)
    elif args.tool == "both":
        requested = list(roots)
    else:
        requested = [cast(Tool, args.tool)]
    project = (
        Path(os.path.abspath(os.path.expanduser(args.project)))
        if args.project is not None
        else None
    )
    decisions: list[ToolDecision] = []
    for tool in requested:
        paths = (discover.claude_files if tool == "claude-code" else discover.codex_files)(
            roots[tool]
        )
        result = (claude_code.read if tool == "claude-code" else codex.read)(
            paths, project=project, now=instant
        )
        counts = result.counters
        reason = (
            "no_logs"
            if not paths
            else "read_error"
            if not counts.files_read
            or counts.files_unreadable == len(paths) - counts.files_unread_compressed
            else "format_not_recognised"
            if not result.responses
            and not (counts.responses_without_setting or counts.files_outside_project)
            else None
        )
        if reason is not None:
            decisions.append(error_tool(tool, reason, counts))
        else:
            table = measures.build(
                result,
                utc_offset=offset,
                now=instant,
                since=since,
                model=args.model,
                effort=args.effort,
            )
            decisions.append(decide_tool(table, counts))
    decision = seal(
        LogsDecision(
            arci_version=__version__,
            example=args.example,
            utc_offset_minutes=minutes,
            project_filtered=project is not None,
            tools=tuple(decisions),
            exit_code=exit_code(decisions),
        )
    )
    try:
        targets = [
            Path(path).expanduser().resolve()
            for path in (args.json, args.markdown, args.html)
            if path is not None
        ]
        duplicate = len(set(targets)) != len(targets) or any(
            a.exists() and b.exists() and a.samefile(b)
            for i, a in enumerate(targets)
            for b in targets[i + 1 :]
        )
    except BaseException:
        raise _UsageError(report.WRITE_ERROR) from None
    if duplicate:
        raise _UsageError(report.DUPLICATE_OUTPUT)
    directory_tools: tuple[Tool, ...] = tuple(
        tool
        for tool in roots
        if (args.claude_dir if tool == "claude-code" else args.codex_dir) is not None
    )
    text = report.render_text(decision, directory_tools=directory_tools)
    contents: list[str] = []
    if args.json is not None:
        contents.append(
            json.dumps(decision.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"
        )
    if args.markdown is not None:
        contents.append(report.render_markdown(decision, directory_tools=directory_tools))
    if args.html is not None:
        contents.append(render_html(decision, directory_tools=directory_tools))
    try:
        _write_outputs(list(zip(targets, contents, strict=True)))
    except _UsageError:
        raise
    except BaseException:
        raise _UsageError(report.WRITE_ERROR) from None
    out.write(text)
    return decision.exit_code


def _write_outputs(outputs: Sequence[tuple[Path, str]]) -> None:
    """Stage all output and backups before replacement; roll back on a failed move."""
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    installed: list[Path] = []
    temporary: list[Path] = []
    placeholders: set[Path] = set()
    keep: set[Path] = set()

    def temporary_for(target: Path) -> Path:
        fd, name = tempfile.mkstemp(prefix=".realornoise-", dir=target.parent)
        path = Path(name)
        temporary.append(path)
        os.close(fd)
        return path

    try:
        checked: list[Path] = []
        for target, _ in outputs:
            if not target.exists():
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
                placeholders.add(target)
                os.close(fd)
            if any(target.samefile(other) for other in checked):
                raise _UsageError(report.DUPLICATE_OUTPUT)
            checked.append(target)
        for target, content in outputs:
            if not target.is_file():
                raise OSError
            staged[target] = temporary_for(target)
            staged[target].write_text(content, encoding="utf-8")
            os.chmod(staged[target], stat.S_IMODE(target.stat().st_mode))
            if target not in placeholders:
                backups[target] = temporary_for(target)
                shutil.copy2(target, backups[target])
        for target, _ in outputs:
            os.replace(staged[target], target)
            installed.append(target)
    except BaseException:
        for target in reversed(installed):
            try:
                if target in backups:
                    os.replace(backups[target], target)
                else:
                    target.unlink()
            except BaseException:
                if target in backups:
                    keep.add(backups[target])
        raise
    finally:
        for path in (set(temporary) - keep) | (placeholders - set(installed)):
            with suppress(OSError):
                path.unlink(missing_ok=True)


def run(
    argv: Sequence[str],
    *,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Return a result code; exceptions and offending values never reach the user."""
    output = sys.stdout if out is None else out
    errors = sys.stderr if err is None else err
    try:
        return _execute(argv, now=now, env=env, home=home, out=output)
    except _UsageError as error:
        message = str(error)  # Only our fixed constants enter this private exception.
    except measures.UsageError as error:
        message = report.SINCE_EARLY if error.code == "since_too_early" else report.CALENDAR_RANGE
    except BaseException:
        message = report.INTERNAL_ERROR
    with suppress(BaseException):
        errors.write(message + "\n")
    return 3


def main(argv: Sequence[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv)
