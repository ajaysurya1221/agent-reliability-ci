"""Defensive streaming JSONL readers; exceptions are counted, never rendered."""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Generator, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO, cast

from records import (
    EDIT_TOOLS,
    JSON,
    Counters,
    EditResult,
    ReadResult,
    Response,
    array,
    effort_id,
    integer,
    json_value,
    model_id,
    obj,
    timestamp,
)


class DiscoveredPaths(list[Path]):
    """Retain filter diagnostics without returning a rejected path or its contents."""

    def __init__(self) -> None:
        super().__init__()
        self.discovery_errors = 0
        self.filtered_files = 0


@contextmanager
def open_log(path: Path) -> Generator[TextIO]:
    if path.name.endswith(".jsonl.zst"):
        # No import of compression on Python 3.13.
        module = importlib.import_module("compression.zstd")
        with cast(TextIO, module.open(path, "rt", encoding="utf-8", errors="replace")) as stream:
            yield stream
    else:
        with path.open(encoding="utf-8", errors="replace") as stream:
            yield stream


def lines(path: Path, counts: Counters) -> Iterator[dict[str, JSON]]:
    counts.files += 1
    if path.name.endswith(".jsonl.zst") and sys.version_info < (3, 14):
        counts.unread_compressed += 1
        return
    try:
        with open_log(path) as stream:
            for line in stream:
                counts.lines += 1
                try:
                    value = json_value(json.loads(line))
                    if not isinstance(value, dict) or "\ufffd" in line:
                        counts.unparseable_lines += 1
                        continue
                    yield value
                except Exception:
                    counts.unparseable_lines += 1
    except Exception:
        counts.unread_files += 1


def _unknown(data: dict[str, JSON], allowed: str, counts: Counters) -> None:
    counts.unknown_keys += len(data.keys() - set(allowed.split()))


def _response(
    out: ReadResult,
    tool: str,
    index: int,
    time: datetime | None,
    model: str,
    effort: str,
    main: bool,
    reasoning: int | None,
) -> None:
    counts = out.counters
    counts.responses += 1
    counts.lacking_model += model == "other"
    counts.lacking_timestamp += time is None
    counts.lacking_reasoning += reasoning is None
    counts.complete_responses += model != "other" and time is not None and reasoning is not None
    if time is not None and tool in ("claude", "codex"):
        out.records.append(Response(tool, index, time, model, effort, main, reasoning))


@dataclass
class _ClaudeResponse:
    time: datetime | None
    model: str
    effort: str
    main: bool
    reasoning: int | None


def read_claude(paths: Iterable[Path]) -> ReadResult:
    out = ReadResult([], Counters())
    for index, path in enumerate(paths):
        if path.name == "journal.jsonl":
            continue
        responses: dict[str, _ClaudeResponse] = {}
        tools: dict[str, tuple[str, str, str, bool]] = {}
        completed: set[str] = set()
        file_main = "subagents" not in path.parts
        for data in lines(path, out.counters):
            try:
                _unknown(
                    data,
                    "type message timestamp version effort perTurnEffort isSidechain "
                    "isApiErrorMessage toolDenialKind permissionDecision",
                    out.counters,
                )
                kind = data.get("type")
                if kind not in ("assistant", "user"):
                    out.counters.skipped_line_types += 1
                    continue
                message = obj(data.get("message"))
                _unknown(message, "id model content usage stop_reason role", out.counters)
                main = file_main and data.get("isSidechain") is not True
                time = timestamp(data.get("timestamp"))
                if kind == "assistant":
                    if data.get("isApiErrorMessage") is True:
                        out.counters.skipped_api_errors += 1
                        continue
                    identity = message.get("id")
                    if not isinstance(identity, str) or not identity:
                        out.counters.missing_response_id += 1
                        continue
                    usage = obj(message.get("usage"))
                    _unknown(
                        usage,
                        "output_tokens_details input_tokens output_tokens "
                        "cache_creation_input_tokens cache_read_input_tokens service_tier",
                        out.counters,
                    )
                    details = obj(usage.get("output_tokens_details"))
                    _unknown(details, "thinking_tokens", out.counters)
                    reasoning = integer(details.get("thinking_tokens"))
                    if identity not in responses:
                        responses[identity] = _ClaudeResponse(
                            time,
                            model_id(message.get("model")),
                            effort_id(data.get("perTurnEffort", data.get("effort"))),
                            main,
                            reasoning,
                        )
                    else:
                        out.counters.duplicate_responses += 1
                        responses[identity].reasoning = reasoning
                    response = responses[identity]
                    # Union of tool blocks, without retaining text, signatures or arguments.
                    for block in array(message.get("content")):
                        b = obj(block)
                        _unknown(b, "type id name text thinking signature input", out.counters)
                        tool_id, name = b.get("id"), b.get("name")
                        if b.get("type") == "tool_use" and isinstance(tool_id, str):
                            tools[tool_id] = (
                                name if isinstance(name, str) and name in EDIT_TOOLS else "other",
                                response.model,
                                response.effort,
                                response.main,
                            )
                else:
                    denied = "toolDenialKind" in data or (
                        obj(data.get("permissionDecision")).get("decision") == "reject"
                    )
                    for block in array(message.get("content")):
                        b = obj(block)
                        _unknown(b, "type tool_use_id is_error content", out.counters)
                        if b.get("type") != "tool_result":
                            continue
                        tool_id = b.get("tool_use_id")
                        if not isinstance(tool_id, str) or tool_id not in tools:
                            out.counters.unmatched_edits += 1
                            continue
                        if tool_id in completed:
                            continue
                        completed.add(tool_id)
                        name, model, effort, tool_main = tools[tool_id]
                        if name not in EDIT_TOOLS:
                            continue
                        if denied:
                            out.counters.denied_edits += 1
                        elif time is not None:
                            out.counters.edit_results += 1
                            out.records.append(
                                EditResult(
                                    "claude",
                                    time,
                                    main and tool_main,
                                    b.get("is_error") is True,
                                    model,
                                    effort,
                                )
                            )
            except Exception:
                out.counters.unparseable_lines += 1
        for response in responses.values():
            _response(
                out,
                "claude",
                index,
                response.time,
                response.model,
                response.effort,
                response.main,
                response.reasoning,
            )
    return out


def read_codex(paths: Iterable[Path]) -> ReadResult:
    out = ReadResult([], Counters())
    if isinstance(paths, DiscoveredPaths):
        out.counters.discovery_errors = paths.discovery_errors
        out.counters.filtered_files = paths.filtered_files
    for index, path in enumerate(paths):
        model, effort, main = "other", "other", True
        previous: JSON = None
        have_previous = False
        for data in lines(path, out.counters):
            try:
                _unknown(data, "timestamp type payload", out.counters)
                payload = obj(data.get("payload"))
                kind = data.get("type")
                if kind == "session_meta":
                    _unknown(payload, "cwd cli_version thread_source", out.counters)
                    main = payload.get("thread_source") != "subagent"
                elif kind == "turn_context":
                    _unknown(payload, "model effort", out.counters)
                    model, effort = model_id(payload.get("model")), effort_id(payload.get("effort"))
                elif kind == "event_msg" and payload.get("type") == "token_count":
                    _unknown(payload, "type info rate_limits", out.counters)
                    info = payload.get("info")
                    if not isinstance(info, dict):
                        out.counters.skipped_line_types += 1
                        continue
                    _unknown(
                        info,
                        "last_token_usage total_token_usage model_context_window",
                        out.counters,
                    )
                    _unknown(
                        obj(info.get("last_token_usage")),
                        "reasoning_output_tokens input_tokens cached_input_tokens "
                        "output_tokens total_tokens",
                        out.counters,
                    )
                    _unknown(
                        obj(info.get("total_token_usage")),
                        "reasoning_output_tokens input_tokens cached_input_tokens "
                        "output_tokens total_tokens",
                        out.counters,
                    )
                    total = info.get("total_token_usage")
                    # Compare the entire cumulative-usage object, not just one counter.
                    if isinstance(total, dict):
                        if have_previous and total == previous:
                            out.counters.duplicate_responses += 1
                            continue
                        previous, have_previous = total, True
                    else:
                        previous, have_previous = None, False
                    _response(
                        out,
                        "codex",
                        index,
                        timestamp(data.get("timestamp")),
                        model,
                        effort,
                        main,
                        integer(obj(info.get("last_token_usage")).get("reasoning_output_tokens")),
                    )
                else:
                    out.counters.skipped_line_types += 1
            except Exception:
                out.counters.unparseable_lines += 1
    return out


def discover_claude(root: Path, dir_prefix: str = "") -> list[Path]:
    found: list[Path] = []
    try:
        for project in sorted(root.iterdir()):
            if (
                project.is_symlink()
                or not project.is_dir()
                or not project.name.startswith(dir_prefix)
            ):
                continue
            for path in project.rglob("*.jsonl"):
                relative = path.relative_to(project)
                if path.is_symlink() or any(
                    p.is_symlink() for p in path.parents if p != root.parent
                ):
                    continue
                if path.name != "journal.jsonl" and (
                    len(relative.parts) == 1
                    or ("subagents" in relative.parts and path.name.startswith("agent-"))
                ):
                    found.append(path)
    except Exception:
        raise ValueError("discovery_error") from None
    return sorted(found)


def discover_codex(root: Path, cwd_inside: Path | None = None) -> list[Path]:
    found = DiscoveredPaths()
    try:
        for folder in (root / "sessions", root / "archived_sessions"):
            for path in folder.rglob("*"):
                if path.is_symlink() or not path.is_file():
                    continue
                if any(p.is_symlink() for p in path.parents if p != root.parent):
                    continue
                if not (path.name.endswith(".jsonl") or path.name.endswith(".jsonl.zst")):
                    continue
                if folder.name == "sessions" and not path.name.startswith("rollout-"):
                    continue
                if cwd_inside is not None:
                    if path.name.endswith(".jsonl.zst") and sys.version_info < (3, 14):
                        found.append(path)  # Reader reports unread_compressed; no data is read.
                        continue
                    try:
                        with open_log(path) as stream:
                            data = obj(json_value(json.loads(stream.readline())))
                        cwd = obj(data.get("payload")).get("cwd")
                        if not isinstance(cwd, str) or not Path(cwd).is_absolute():
                            found.discovery_errors += 1
                            continue
                        if not Path(cwd).resolve().is_relative_to(cwd_inside.resolve()):
                            found.filtered_files += 1
                            continue
                    except Exception:
                        found.discovery_errors += 1
                        continue
                found.append(path)
    except Exception:
        raise ValueError("discovery_error") from None
    found.sort()
    return found
