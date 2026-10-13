"""`arci schema` is deterministic and docs/schema/arci.schema.json is never stale."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from arci.cli import main
from arci.descriptor import SCHEMA_ID, SCHEMA_TITLE, render_schema

REPO = Path(__file__).resolve().parents[3]
COMMITTED = REPO / "docs" / "schema" / "arci.schema.json"


def test_the_committed_schema_is_not_stale() -> None:
    # Regenerate with: .venv/bin/python -m arci.cli schema --out docs/schema/arci.schema.json
    assert COMMITTED.read_bytes() == render_schema().encode("utf-8")


def test_arci_schema_prints_the_committed_bytes(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schema"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.encode("utf-8") == COMMITTED.read_bytes()


def test_arci_schema_out_writes_identical_bytes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "arci.schema.json"
    assert main(["schema", "--out", str(out)]) == 0
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "")
    assert out.read_bytes() == COMMITTED.read_bytes()


def test_schema_format_title_and_id() -> None:
    text = render_schema()
    assert text.endswith("}\n") and not text.endswith("\n\n")
    document = json.loads(text)
    assert text == json.dumps(document, indent=2, sort_keys=True) + "\n"
    assert document["title"] == SCHEMA_TITLE == "ARCI experiment descriptor"
    assert document["$id"] == SCHEMA_ID
    assert SCHEMA_ID.endswith("/v0.8.0/docs/schema/arci.schema.json")
    assert document["additionalProperties"] is False
    assert sorted(document["required"]) == ["baseline", "candidate", "conditions", "experiment_id"]


def test_the_schema_describes_every_shorthand_and_exclusion() -> None:
    document = json.loads(render_schema())
    top = document["description"]
    for phrase in (
        "`oracle`",
        "`contract`",
        "bare",
        "`id`",
        "`fault`",
        "`occurrence`",
        "authoritative",
    ):
        assert phrase in top, phrase
    defs = document["$defs"]
    assert "exactly one of `id` and `condition_id`" in defs["DescriptorCondition"]["description"]
    assert "at most one of `fault`" in defs["DescriptorCondition"]["description"]
    assert "not both" in defs["DescriptorFault"]["description"]
    assert "exactly one of" in document["properties"]["baseline"]["description"]
    assert "exactly one of" in document["properties"]["oracle"]["description"]


@pytest.mark.parametrize("command", ["schema", "run"])
def test_help_exits_zero_with_empty_stderr(command: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "arci.cli", command, "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.startswith(f"usage: arci {command}")
