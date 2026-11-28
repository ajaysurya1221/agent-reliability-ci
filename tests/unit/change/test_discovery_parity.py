"""Compare campaign registration with released discovery on the same scored snapshot."""

from __future__ import annotations

import csv
import errno
import io
import json
import os
import shlex
import sys
from pathlib import Path

import pytest

from arci.change import ChangeFormat
from arci.cli import main
from arci.importers import OutcomeError
from arci.outcomes import discover_rule, load_rule
from examples.integrations.mlflow_rows import mlflow_rows
from tests.unit.integrations.test_mlflow_rows import SCORER, records, word

REAL = Path(__file__).resolve().parents[1] / "integrations/real"
FORMATS = ("csv", "jsonl", "junit", "promptfoo")
COPY = """\
import os, shutil, sys
from pathlib import Path
arm = os.environ["ARCI_CHANGE_ARM"]
name = "discovery" if os.environ["ARCI_CHANGE_ROUND"] == "0" else arm
shutil.copyfile(Path(sys.argv[1]) / name, sys.argv[2])
"""


def fixture(fmt: ChangeFormat, launch: str) -> bytes:
    if fmt in {"promptfoo", "junit"}:
        folder, suffix = ("promptfoo", "json") if fmt == "promptfoo" else ("deepeval", "xml")
        name = "discovery" if launch == "discovery" else f"r1-{launch}"
        return (REAL / folder / f"e2e-{name}.{suffix}").read_bytes()
    rows = mlflow_rows(records("fail" if launch == "candidate" else "pass"), SCORER, word)
    if fmt == "jsonl":
        return "".join(json.dumps(row) + "\n" for row in rows).encode()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["task_id", "outcome"])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def edited(fmt: ChangeFormat, raw: bytes, case: str) -> bytes:
    if case == "edited":
        if fmt == "promptfoo":
            export = json.loads(raw)
            export["evalId"] = "different-discovery"
            return json.dumps(export).encode()
        return b"\xef\xbb\xbf" + raw
    if case == "invalid-utf8":
        return raw + b"\xff"
    if case == "empty":
        return b""
    if case == "duplicate":
        if fmt == "junit":
            return raw.replace(b"task-w02", b"task-w01")
        return raw + raw.splitlines(keepends=True)[1]
    if case in {"original", "short-cap", "byte-path", "display-path"}:
        return raw
    old, new = {
        "bad-outcome": (b"pass", b"other"),
        "empty-id": (b"w01", b""),
        "mixed-rounds": (b'{"task_id"', b'{"round":0,"task_id"'),
        "invalid-id": (b"w01", rb"\udcff"),
        "bad-header": (b"task_id", b"outcome"),
        "malformed-csv": (b"w01", b'"w01'),
        "duplicate-key": (b'{"task_id"', b'{"task_id":"a","task_id"'),
        "bad-round": (b'{"task_id"', b'{"round":true,"task_id"'),
        "doctype": (b"<testsuites", b"<!DOCTYPE testsuites><testsuites"),
        "missing-class": (b"classname=", b"other="),
        "encoding": (b'encoding="utf-8"', b'encoding="utf-16"'),
    }[case]
    assert old in raw
    return raw.replace(old, new, 1)


CASES = (
    [
        (fmt, case)
        for fmt in FORMATS
        for case in ("original", "edited", "short-cap", "byte-path", "display-path")
    ]
    + [
        (fmt, case)
        for fmt in ("csv", "jsonl", "junit")
        for case in ("invalid-utf8", "empty", "duplicate")
    ]
    + [(fmt, case) for fmt in ("csv", "jsonl") for case in ("empty-id", "bad-outcome")]
    + [("csv", case) for case in ("bad-header", "malformed-csv")]
    + [("jsonl", case) for case in ("invalid-id", "mixed-rounds", "duplicate-key", "bad-round")]
    + [("junit", case) for case in ("doctype", "missing-class", "encoding")]
)


@pytest.mark.parametrize(("fmt", "case"), CASES)
def test_plan_and_full_discovery_match_released_reader(
    fmt: ChangeFormat, case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path
    if case == "byte-path":
        if os.name != "posix":
            pytest.skip("requires POSIX byte paths")
        directory = tmp_path / os.fsdecode(b"bad-\xff")
        try:
            directory.mkdir()
        except OSError as exc:
            if exc.errno not in {errno.EINVAL, errno.EILSEQ, errno.EPERM, errno.EACCES}:
                raise
            pytest.skip("filesystem refuses directories with non-UTF-8 names")
    if case == "display-path":
        # Exercise the reader's UTF-8 check even on filesystems that refuse such names.
        # Keep native file access pointed at the real, readable snapshot.
        native_path = Path.__str__

        def display_path(path: Path) -> str:
            value = native_path(path)
            if ".snapshot." in path.name:
                return os.path.join(native_path(path.parent), "\udcff", path.name)
            return value

        monkeypatch.setattr(Path, "__fspath__", native_path)
        monkeypatch.setattr(Path, "__str__", display_path)

    for launch in ("discovery", "baseline", "candidate"):
        raw = fixture(fmt, launch)
        (tmp_path / launch).write_bytes(edited(fmt, raw, case) if launch == "discovery" else raw)
    command = shlex.join([sys.executable, "-c", COPY, str(tmp_path), "{out}"])
    scored = "jsonl" if fmt == "promptfoo" else fmt
    cap = 1 if case == "short-cap" else 20
    for mode in ("plan", "full"):
        root = directory / mode
        code = main(
            [
                "check-change",
                "--baseline",
                command,
                "--candidate",
                command,
                "--out-dir",
                str(root),
                "--format",
                fmt,
                "--margin",
                "1/10",
                "--max-rounds",
                str(cap),
                *(["--plan-only"] if mode == "plan" else []),
            ]
        )
        (snapshot,) = (root / "discovery").glob("baseline.snapshot.*")
        assert snapshot.is_file()
        try:
            released = discover_rule([snapshot], fmt=scored, margin="1/10", max_rounds=cap)
        except OutcomeError:
            assert case not in {"original", "edited"}
            assert code == 3
            assert not (root / "rule.yaml").exists() and not list(root.glob("round-*"))
        else:
            assert case in {"original", "edited"}
            assert code == (0 if mode == "plan" else 1)
            assert load_rule(root / "rule.yaml") == released.model_copy(
                update={"fixed_before_runs": True}
            )
