"""Stream Claude Code logs into closed-vocabulary, path-free records."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .records import (
    EditResult,
    ReaderCounters,
    ReadResult,
    Response,
    array_of,
    effort_of,
    in_project,
    object_of,
    parse_line,
    reasoning_of,
    render_model,
    string_of,
    time_of,
)

_USED = frozenset({"assistant", "user"})
_EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})


def read(paths: Sequence[Path], *, project: Path | None, now: datetime) -> ReadResult:
    counts = ReaderCounters()
    models: dict[str, int] = {}
    efforts: dict[str, int] = {}
    versions: dict[str | None, int] = {}
    workdirs: dict[str | None, int] = {}
    responses: list[Response] = []
    edits: list[EditResult] = []
    seen: set[str] = set()
    for path in paths:
        file_seen: set[str] = set()
        duplicates: set[str] = set()
        pending: dict[str, Response] = {}
        calls: dict[str, tuple[bool, Response]] = {}
        try:
            with path.open("rb") as stream:
                for raw in stream:
                    data = parse_line(raw.decode("utf-8"), _USED, counts)
                    if data is None:
                        continue
                    message = object_of(data.get("message"))
                    if data["type"] == "assistant":
                        if data.get("isApiErrorMessage") is True:
                            continue
                        identity = string_of(message.get("id"))
                        model = string_of(message.get("model"))
                        effort = string_of(data.get("effort", data.get("perTurnEffort")))
                        when = time_of(data.get("timestamp"))
                        if not identity or when is None:
                            counts.lines_lacking_field += 1
                            continue
                        if identity in seen:
                            if identity not in duplicates:
                                counts.responses_duplicate += 1
                                duplicates.add(identity)
                            continue
                        if identity not in file_seen:
                            file_seen.add(identity)
                            if not model or not effort:
                                counts.responses_without_setting += 1
                                continue
                        elif identity not in pending:
                            # A later content block cannot supply a missing first setting.
                            continue
                        usage = object_of(
                            object_of(message.get("usage")).get("output_tokens_details")
                        )
                        reasoning = reasoning_of(usage.get("thinking_tokens"))
                        if identity not in pending:
                            assert model and effort
                            version, cwd = (
                                string_of(data.get("version")),
                                string_of(data.get("cwd")),
                            )
                            pending[identity] = Response(
                                "claude-code",
                                when,
                                models.setdefault(model, len(models)),
                                efforts.setdefault(effort, len(efforts)),
                                data.get("isSidechain") is not True,
                                reasoning,
                                versions.setdefault(version, len(versions)),
                                workdirs.setdefault(cwd, len(workdirs)),
                                in_project(cwd, project),
                            )
                        else:
                            pending[identity] = replace(pending[identity], reasoning=reasoning)
                        response = pending[identity]
                        for value in array_of(message.get("content")):
                            block = object_of(value)
                            call_id = string_of(block.get("id"))
                            if block.get("type") == "tool_use" and call_id:
                                name = string_of(block.get("name"))
                                calls.setdefault(call_id, (name in _EDIT_TOOLS, response))
                    else:
                        denied = "toolDenialKind" in data or (
                            object_of(data.get("permissionDecision")).get("decision") == "reject"
                        )
                        when = time_of(data.get("timestamp"))
                        lacking_time = False
                        for value in array_of(message.get("content")):
                            block = object_of(value)
                            if block.get("type") != "tool_result":
                                continue
                            call_id = string_of(block.get("tool_use_id"))
                            call = calls.get(call_id) if call_id else None
                            if call is None:
                                counts.edits_unmatched += 1
                                continue
                            is_edit, response = call
                            if not is_edit:
                                continue
                            if denied:
                                counts.edits_denied += 1
                            elif when is None:
                                lacking_time = True
                            elif when > now:
                                counts.records_in_future += 1
                            else:
                                edits.append(
                                    EditResult(
                                        "claude-code",
                                        when,
                                        response.model,
                                        response.effort,
                                        response.main_thread,
                                        block.get("is_error") is True,
                                        response.in_project,
                                    )
                                )
                        counts.lines_lacking_field += lacking_time
            counts.files_read += 1
        except (OSError, UnicodeError, ValueError):
            counts.files_unreadable += 1
        seen.update(file_seen)
        for response in pending.values():
            if response.when > now:
                counts.records_in_future += 1
            else:
                responses.append(response)
                counts.responses += 1
                counts.responses_without_reasoning += response.reasoning is None
    return ReadResult(
        "claude-code",
        tuple(responses),
        tuple(edits),
        tuple(render_model(model) for model in models),
        tuple(effort_of(effort) for effort in efforts),
        tuple(models[model] for model in sorted(models)),
        tuple(efforts[effort] for effort in sorted(efforts)),
        counts,
    )
