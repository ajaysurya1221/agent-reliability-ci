"""Stream Codex rollout logs; compressed input uses Python 3.14's stdlib."""

from __future__ import annotations

import importlib
import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, cast

from .measures import WindowReadResult
from .records import (
    ReaderCounters,
    ReadResult,
    Response,
    effort_of,
    in_project,
    object_of,
    parse_line,
    reasoning_of,
    render_model,
    string_of,
    time_of,
    version_name,
    without_timezone,
)

_USED = frozenset({"session_meta", "turn_context", "event_msg"})


def read(
    paths: Sequence[Path],
    *,
    project: Path | None,
    now: datetime,
    model_names: Sequence[str] = (),
    effort_names: Sequence[str] = (),
) -> ReadResult:
    counts = ReaderCounters()
    models: dict[str, int] = {name: i for i, name in enumerate(sorted(set(model_names)))}
    efforts: dict[str, int] = {name: i for i, name in enumerate(sorted(set(effort_names)))}
    versions: dict[str | None, int] = {}
    workdirs: dict[str | None, int] = {}
    responses: list[Response] = []
    unconfigured: list[Response] = []
    seen: set[tuple[str, datetime, str]] = set()
    latest_main_response: datetime | None = None
    for path in paths:
        file_unconfigured: list[Response] = []
        saved_counts = counts
        counts = replace(counts)
        saved_models, saved_efforts = models.copy(), efforts.copy()
        saved_versions, saved_workdirs = versions.copy(), workdirs.copy()
        saved_latest = latest_main_response
        file_seen: set[tuple[str, datetime, str]] = set()
        pending: list[Response] = []
        previous_total: object = None
        try:
            regular = path.is_file()
        except OSError:
            regular = False
        if not regular:
            counts.files_unreadable += 1
            continue
        compressed = path.name.endswith(".zst")
        zstd = None
        if compressed:
            try:
                zstd = importlib.import_module("compression.zstd")
            except ImportError:
                counts.files_unread_compressed += 1
                continue
        try:
            stream = cast(BinaryIO, zstd.open(path, "rb")) if zstd is not None else path.open("rb")
            with stream:
                counts.files_read += 1
                first = stream.readline()
                meta = (
                    parse_line(first.removeprefix(b"\xef\xbb\xbf"), _USED, counts)
                    if first
                    else None
                )
                if meta is None or meta["type"] != "session_meta":
                    # A readable file with no session header has an unrecognised
                    # format, not an I/O or decoding fault.
                    continue
                payload = object_of(meta.get("payload"))
                cwd, version = string_of(payload.get("cwd")), string_of(payload.get("cli_version"))
                inside = in_project(cwd, project)
                if not inside:
                    counts.files_outside_project += 1
                    continue
                session = string_of(payload.get("id"))
                workdir_id = workdirs.setdefault(cwd, len(workdirs))
                version_id = versions.setdefault(version, len(versions))
                main = payload.get("thread_source") != "subagent"
                context: dict[str, object] | None = None
                for raw in stream:
                    data = parse_line(raw, _USED, counts)
                    if data is None:
                        continue
                    payload = object_of(data.get("payload"))
                    if data["type"] == "turn_context":
                        context = payload
                        continue
                    if data["type"] != "event_msg" or payload.get("type") != "token_count":
                        counts.lines_unknown_type += 1
                        continue
                    if payload.get("info") is None:
                        previous_total = None
                        continue
                    info = object_of(payload.get("info"))
                    total = info.get("total_token_usage")
                    repeated = isinstance(total, dict) and total == previous_total
                    previous_total = total
                    if repeated:
                        counts.responses_duplicate += 1
                        continue
                    when = time_of(data.get("timestamp"))
                    if without_timezone(data.get("timestamp")):
                        counts.records_without_timezone += 1
                        continue
                    if when is None or not isinstance(payload.get("info"), dict):
                        counts.lines_lacking_field += 1
                        continue
                    total = info.get("total_token_usage")
                    if session and isinstance(total, dict):
                        try:
                            key = (session, when, json.dumps(total, sort_keys=True))
                        except (ValueError, RecursionError):
                            counts.lines_lacking_field += 1
                            continue
                        if key in seen or key in file_seen:
                            counts.responses_duplicate += 1
                            continue
                        file_seen.add(key)
                    if when > now:
                        counts.records_in_future += 1
                        continue
                    if main and (latest_main_response is None or when > latest_main_response):
                        latest_main_response = when
                    model = string_of(context.get("model")) if context is not None else None
                    effort = string_of(context.get("effort")) if context is not None else None
                    if not model or not effort:
                        counts.responses_without_setting += 1
                        file_unconfigured.append(
                            Response(
                                "codex", when, -1, -1, main, None, version_id, workdir_id, inside
                            )
                        )
                        continue
                    reasoning = reasoning_of(
                        object_of(info.get("last_token_usage")).get("reasoning_output_tokens")
                    )
                    pending.append(
                        Response(
                            "codex",
                            when,
                            models.setdefault(model, len(models)),
                            efforts.setdefault(effort, len(efforts)),
                            main,
                            reasoning,
                            version_id,
                            workdir_id,
                            inside,
                        )
                    )
                    counts.responses += 1
                    counts.responses_without_reasoning += reasoning is None
        except Exception:
            # Keep physical read counts, but discard all semantic state from this file.
            saved_counts.files_read = counts.files_read
            saved_counts.lines = counts.lines
            counts = saved_counts
            counts.files_unreadable += 1
            models, efforts = saved_models, saved_efforts
            versions, workdirs = saved_versions, saved_workdirs
            latest_main_response = saved_latest
            continue
        unconfigured.extend(file_unconfigured)
        responses.extend(pending)
        seen.update(file_seen)
    return WindowReadResult(
        "codex",
        tuple(responses),
        (),
        tuple(render_model(model) for model in models),
        tuple(effort_of(effort) for effort in efforts),
        tuple(models[model] for model in sorted(models)),
        tuple(efforts[effort] for effort in sorted(efforts)),
        counts,
        latest_main_response,
        versions=tuple(version_name(version) for version in versions),
        unconfigured_responses=tuple(unconfigured),
    )
