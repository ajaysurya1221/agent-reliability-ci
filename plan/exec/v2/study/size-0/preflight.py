"""Five independent native streaming toy exchanges using the study chat client."""

import os
import secrets
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from descriptors import Row, read
from identity import expected, inspect_model, validate
from records import atomic_json, require

TOOL = {
    "type": "function",
    "function": {
        "name": "read_pebble",
        "description": "Read a pebble's token.",
        "parameters": {
            "type": "object",
            "properties": {"pebble": {"type": "string"}},
            "required": ["pebble"],
        },
    },
}


def history_dir(claims: Path, slot: str, commit: str) -> Path:
    return claims / "preflights" / commit / slot


def latest_pin(claims: Path, slot: str, commit: str) -> Row:
    files = sorted(history_dir(claims, slot, commit).glob("*.json"))
    require(files, f"no preflight for {slot} at this registration")
    record = read(files[-1])
    require(record.get("status") == "qualified", "latest preflight incomplete")
    return record


def preflight(root: Path, claims: Path, model: Row, mode: str, commit: str) -> None:
    folder = history_dir(claims, model["slot"], commit)
    folder.mkdir(parents=True, exist_ok=True)
    files = sorted(folder.glob("*.json"))
    # Admission holds the suite lock. Sequence by attempt, independently of wall time.
    path = folder / f"{len(files) + 1:08d}-{uuid4().hex}.json"
    record: Row = dict(
        mode=mode,
        registration=commit,
        slot=model["slot"],
        model=model,
        probes=[],
        cold=None,
        status="incomplete",
    )
    atomic_json(path, record)
    try:
        probe(root, model, record, path)
        identity = validate_pin(root, model, record, mode, commit)
        for old in files:
            previous = read(old)
            if previous["status"] == "qualified":
                require(
                    validate_pin(root, model, previous, mode, commit) == identity,
                    "identity changed since earlier preflight",
                )
        record["status"] = "qualified"
    finally:
        atomic_json(path, record)


def probe(root: Path, model: Row, record: Row, path: Path) -> None:
    import httpx
    from agent_hooks import probe_capture
    from langchain.chat_models import init_chat_model
    from langchain_core.messages import ToolMessage

    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:11434"
    os.environ.update(LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
    initial = inspect_model(root, model, allow_unloaded=True)
    loaded = initial["loaded_digest"] is not None
    for key, value in expected(root, model).items():
        if loaded or key not in ("loaded_digest", "loaded_context"):
            require(initial[key] == value, f"preflight installed or loaded {key} differs")
    record.update(before=initial, cold=not loaded)
    atomic_json(path, record)
    probes = record["probes"]
    for i in range(5):
        capture: Row = {"thinking": False, "models": [], "load_duration": None, "completed": 0}
        chat = init_chat_model(
            "ollama:" + model["tag"],
            temperature=0.7,
            reasoning=False,
            sync_client_kwargs={
                "trust_env": False,
                "follow_redirects": False,
                "timeout": httpx.Timeout(120),
                "event_hooks": probe_capture(capture),
            },
        ).bind_tools([TOOL])
        pebble = f"stone-{i + 1}"
        history: list[Any] = [
            ("system", "Use the pebble reader to answer the question."),
            ("human", f"What token is on pebble {pebble}?"),
        ]
        start = time.monotonic()
        parsed = repeated = parser_error = False
        expected_responses = 1
        try:
            answer = chat.invoke(history)
            calls = answer.tool_calls
            parsed = (
                len(calls) == 1
                and calls[0]["name"] == "read_pebble"
                and calls[0]["args"] == {"pebble": pebble}
            )
            if parsed:
                expected_responses += 1
                token = secrets.token_hex(12)
                final = chat.invoke(
                    [*history, answer, ToolMessage(content=token, tool_call_id=calls[0]["id"])]
                )
                repeated = (
                    isinstance(final.content, str)
                    and token in final.content
                    and not final.tool_calls
                )
        except Exception:
            # Only a completed exchange from the registered model qualifies below.
            parser_error = True
            parsed = False
        seconds = time.monotonic() - start
        actual = inspect_model(root, model)
        validate(root, model, actual)
        require(
            capture["completed"] == expected_responses and set(capture["models"]) == {model["tag"]},
            "incomplete or mismatched preflight stream",
        )
        probes.append(
            dict(
                native_call=parsed,
                parser_error=parser_error,
                token_repeated=repeated,
                thinking=capture["thinking"],
                seconds=seconds,
                identity=actual,
                load_seconds=capture["load_duration"],
                load_duration_missing=capture.get("load_duration_missing", False),
            )
        )
        if i == 0:
            record["load_duration_missing"] = probes[0]["load_duration_missing"]
            record["cold_load_seconds"] = None if loaded else probes[0]["load_seconds"]
        atomic_json(path, record)


def validate_pin(root: Path, model: Row, record: Row, mode: str, commit: str) -> Row:
    require(
        record["mode"] == mode
        and record["registration"] == commit
        and record["model"] == model
        and record["slot"] == model["slot"]
        and len(record["probes"]) == 5,
        "preflight binding differs",
    )
    first = record["probes"][0]
    initial = record["before"]
    loaded = initial["loaded_digest"] is not None
    require(
        initial
        == (
            first["identity"]
            if loaded
            else first["identity"] | dict(loaded_digest=None, loaded_context=None)
        ),
        "identity changed during first probe",
    )
    require(
        record["cold"] is (not loaded)
        and record["cold_load_seconds"] == (None if loaded else first["load_seconds"])
        and record.get("load_duration_missing", False) is first.get("load_duration_missing", False)
        and isinstance(first["load_seconds"], (int, float))
        and first["load_seconds"] >= 0,
        "missing first load duration",
    )
    for p in record["probes"]:
        validate(root, model, p["identity"])
        require(
            p["identity"] == first["identity"]
            and not (p["parser_error"] and p["native_call"])
            and p["seconds"] >= 0
            and all(
                type(p[k]) is bool
                for k in ("native_call", "token_repeated", "thinking", "parser_error")
            ),
            "preflight identity or observation differs",
        )
    return first["identity"]
