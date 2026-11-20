"""The outcome extractor, against a stand-in for the table reader.

`pyarrow` is not installed in this repository's environment, so the two columns are served by a
stand-in with the same surface the extractor uses: `ParquetFile(...).schema_arrow`, `read_table`
and `pyarrow.types`.
"""

from __future__ import annotations

import json
import math
import stat
from pathlib import Path
from typing import Any

import pytest

from bench.logsignals import extract_outcome
from tests.unit.logsignals import transcripts

TDIR = "transcripts0"


class _Type:
    def __init__(self, kind: str) -> None:
        self.kind = kind


class _Field:
    def __init__(self, kind: _Type) -> None:
        self.type = kind


class _Schema:
    def __init__(self, fields: dict[str, _Type]) -> None:
        self._fields = fields
        self.names: list[str] = list(fields)

    def field(self, name: str) -> _Field:
        return _Field(self._fields[name])


class _Column:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def to_pylist(self) -> list[object]:
        return list(self._values)


class _Table:
    def __init__(self, columns: dict[str, list[object]]) -> None:
        self._columns = columns
        self.num_rows = len(next(iter(columns.values()))) if columns else 0

    def column(self, name: str) -> _Column:
        return _Column(self._columns[name])


class _ParquetFileHandle:
    def __init__(self, schema: _Schema) -> None:
        self.schema_arrow = schema


class _Parquet:
    def __init__(self, schema: _Schema, columns: dict[str, list[object]]) -> None:
        self._schema = schema
        self._columns = columns

    def ParquetFile(self, _path: str) -> _ParquetFileHandle:
        return _ParquetFileHandle(self._schema)

    def read_table(self, _path: str, columns: list[str] | None = None) -> _Table:
        wanted = list(self._columns) if columns is None else columns
        return _Table({name: self._columns[name] for name in wanted})


class _Types:
    @staticmethod
    def is_string(kind: _Type) -> bool:
        return kind.kind == "string"

    @staticmethod
    def is_large_string(kind: _Type) -> bool:
        return kind.kind == "large_string"

    @staticmethod
    def is_floating(kind: _Type) -> bool:
        return kind.kind == "double"

    @staticmethod
    def is_integer(kind: _Type) -> bool:
        return kind.kind == "int64"


class _Arrow:
    types = _Types()


def _stand_in(
    paths: list[object],
    values: list[object],
    *,
    path_type: str = "string",
    value_type: str = "double",
    drop: str = "",
) -> tuple[_Parquet, _Arrow]:
    fields = {"transcript_path": _Type(path_type), "agent_percentage": _Type(value_type)}
    columns: dict[str, list[object]] = {"transcript_path": paths, "agent_percentage": values}
    if drop:
        del fields[drop]
        del columns[drop]
    return _Parquet(_Schema(fields), columns), _Arrow()


def _manifest(tmp_path: Path, paths: list[str]) -> Path:
    manifest = tmp_path / "manifest.tsv"
    lines = [
        "\t".join([path, "codex", format(index + 1, "016x"), "confirmation", "2026-04", ""])
        for index, path in enumerate(paths)
    ]
    _ = manifest.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return manifest


def test_one_row_per_manifest_path_in_manifest_order() -> None:
    paths = [f"{TDIR}/a.jsonl", f"{TDIR}/b.jsonl", f"{TDIR}/c.jsonl"]
    parquet, arrow = _stand_in(list(reversed(paths)), [100.0, 50.5, 0.0])
    pairs = extract_outcome.read_columns(parquet, arrow, "sessions.parquet")
    rows, counts = extract_outcome.build_rows(paths, pairs)
    assert rows == [
        f"{TDIR}/a.jsonl\t0.0",
        f"{TDIR}/b.jsonl\t50.5",
        f"{TDIR}/c.jsonl\t100.0",
    ]
    assert counts["rows_written"] == 3
    assert counts["not_in_table"] == 0


def test_a_missing_value_is_written_as_the_empty_field() -> None:
    paths = [f"{TDIR}/a.jsonl", f"{TDIR}/b.jsonl"]
    parquet, arrow = _stand_in(list(paths), [None, math.nan])
    rows, counts = extract_outcome.build_rows(
        paths, extract_outcome.read_columns(parquet, arrow, "sessions.parquet")
    )
    assert rows == [f"{TDIR}/a.jsonl\t", f"{TDIR}/b.jsonl\t"]
    assert counts["missing_value"] == 2


def test_a_path_the_table_does_not_hold_once_is_counted_and_skipped() -> None:
    paths = [f"{TDIR}/a.jsonl", f"{TDIR}/b.jsonl", f"{TDIR}/c.jsonl"]
    parquet, arrow = _stand_in(
        [f"{TDIR}/a.jsonl", f"{TDIR}/b.jsonl", f"{TDIR}/b.jsonl"], [1.0, 2.0, 3.0]
    )
    rows, counts = extract_outcome.build_rows(
        paths, extract_outcome.read_columns(parquet, arrow, "sessions.parquet")
    )
    assert rows == [f"{TDIR}/a.jsonl\t1.0"]
    assert counts["ambiguous"] == 1
    assert counts["not_in_table"] == 1


def test_the_table_path_is_stripped() -> None:
    paths = [f"{TDIR}/a.jsonl"]
    parquet, arrow = _stand_in([f"  {TDIR}/a.jsonl \n"], [12.0])
    rows, _counts = extract_outcome.build_rows(
        paths, extract_outcome.read_columns(parquet, arrow, "sessions.parquet")
    )
    assert rows == [f"{TDIR}/a.jsonl\t12.0"]


def test_an_integer_column_is_written_with_repr_of_a_float() -> None:
    paths = [f"{TDIR}/a.jsonl"]
    parquet, arrow = _stand_in(list(paths), [100], value_type="int64")
    rows, _counts = extract_outcome.build_rows(
        paths, extract_outcome.read_columns(parquet, arrow, "sessions.parquet")
    )
    assert rows == [f"{TDIR}/a.jsonl\t100.0"]


def test_a_value_outside_zero_to_one_hundred_is_written_as_the_table_gives_it() -> None:
    paths = [f"{TDIR}/a.jsonl", f"{TDIR}/b.jsonl"]
    parquet, arrow = _stand_in(list(paths), [-1.5, math.inf])
    rows, _counts = extract_outcome.build_rows(
        paths, extract_outcome.read_columns(parquet, arrow, "sessions.parquet")
    )
    assert rows == [f"{TDIR}/a.jsonl\t-1.5", f"{TDIR}/b.jsonl\tinf"]


@pytest.mark.parametrize(
    ("path_type", "value_type", "drop"),
    [
        ("double", "double", ""),
        ("string", "string", ""),
        ("string", "double", "agent_percentage"),
        ("string", "double", "transcript_path"),
    ],
)
def test_a_wrong_schema_is_refused(path_type: str, value_type: str, drop: str) -> None:
    parquet, arrow = _stand_in(
        [f"{TDIR}/a.jsonl"], [1.0], path_type=path_type, value_type=value_type, drop=drop
    )
    with pytest.raises(extract_outcome.SchemaInvalid):
        _ = extract_outcome.read_columns(parquet, arrow, "sessions.parquet")


def test_a_large_string_path_column_is_accepted() -> None:
    parquet, arrow = _stand_in([f"{TDIR}/a.jsonl"], [1.0], path_type="large_string")
    assert extract_outcome.read_columns(parquet, arrow, "sessions.parquet") == [
        (f"{TDIR}/a.jsonl", 1.0)
    ]


def test_a_value_of_another_type_is_refused() -> None:
    with pytest.raises(extract_outcome.SchemaInvalid):
        _ = extract_outcome.build_rows([f"{TDIR}/a.jsonl"], [(f"{TDIR}/a.jsonl", "40")])


# --- the whole program ---------------------------------------------------------


class _FakeImport:
    def __init__(self, parquet: _Parquet, arrow: _Arrow) -> None:
        self._modules: dict[str, object] = {"pyarrow": arrow, "pyarrow.parquet": parquet}

    def import_module(self, name: str) -> object:
        return self._modules[name]


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    paths: list[str],
    table_paths: list[object],
    values: list[object],
    *,
    out_name: str = "outcome.tsv",
) -> tuple[int, Path]:
    parquet, arrow = _stand_in(table_paths, values)
    monkeypatch.setattr(extract_outcome, "importlib", _FakeImport(parquet, arrow))
    out = tmp_path / out_name
    code = extract_outcome.main(
        [
            "--sessions",
            str(tmp_path / "sessions.parquet"),
            "--manifest",
            str(_manifest(tmp_path, paths)),
            "--out",
            str(out),
        ]
    )
    return code, out


def test_the_program_writes_the_table_and_prints_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = [f"{TDIR}/{transcripts.CANARY}-a.jsonl", f"{TDIR}/{transcripts.CANARY}-b.jsonl"]
    code, out = _run(tmp_path, monkeypatch, paths, list(paths), [0.0, 100.0])
    assert code == 0
    assert out.read_text(encoding="utf-8") == (
        "path\tagent_percentage\n" + f"{paths[0]}\t0.0\n" + f"{paths[1]}\t100.0\n"
    )
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    captured = capsys.readouterr()
    assert captured.err == ""
    assert transcripts.CANARY not in captured.out
    counts: Any = json.loads(captured.out)
    assert all(isinstance(value, int) for value in counts.values())


def test_the_program_refuses_an_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = [f"{TDIR}/a.jsonl"]
    code, out = _run(tmp_path, monkeypatch, paths, list(paths), [1.0])
    assert code == 0
    before = out.read_bytes()
    code, out = _run(tmp_path, monkeypatch, paths, list(paths), [2.0])
    assert code == 2
    assert out.read_bytes() == before


def test_the_program_refuses_a_broken_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = tmp_path / "manifest.tsv"
    _ = manifest.write_text("one\ttwo\n", encoding="utf-8")
    parquet, arrow = _stand_in([f"{TDIR}/a.jsonl"], [1.0])
    monkeypatch.setattr(extract_outcome, "importlib", _FakeImport(parquet, arrow))
    out = tmp_path / "outcome.tsv"
    code = extract_outcome.main(
        [
            "--sessions",
            str(tmp_path / "sessions.parquet"),
            "--manifest",
            str(manifest),
            "--out",
            str(out),
        ]
    )
    assert code == 2
    assert not out.exists()
    assert capsys.readouterr().err == "manifest-invalid\n"


def test_a_wrong_schema_stops_the_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    parquet, arrow = _stand_in([f"{TDIR}/a.jsonl"], ["40"], value_type="string")
    monkeypatch.setattr(extract_outcome, "importlib", _FakeImport(parquet, arrow))
    out = tmp_path / "outcome.tsv"
    code = extract_outcome.main(
        [
            "--sessions",
            str(tmp_path / "sessions.parquet"),
            "--manifest",
            str(_manifest(tmp_path, [f"{TDIR}/a.jsonl"])),
            "--out",
            str(out),
        ]
    )
    assert code == 2
    assert not out.exists()
    assert capsys.readouterr().err == "schema-invalid\n"


@pytest.mark.parametrize(
    "text",
    [
        "transcripts0/a.jsonl\tcodex\t0000000000000001\tconfirmation\t2026-04\n",
        "transcripts0/a.jsonl\tcodex\t0000000000000001\tconfirmation\t2026-04\t\textra\n",
        "transcripts0/a.jsonl\tother\t0000000000000001\tconfirmation\t2026-04\t\n",
        "transcripts0/a.jsonl\tcodex\tNOTHEX\tconfirmation\t2026-04\t\n",
        "transcripts0/a.jsonl\tcodex\t0000000000000001\tneither\t2026-04\t\n",
        "transcripts0/a.jsonl\tcodex\t0000000000000001\tconfirmation\t2026-13\t\n",
        "transcripts0/a.jsonl\tcodex\t0000000000000001\tconfirmation\t2026-04\tNOTHEX\n",
        "elsewhere/a.jsonl\tcodex\t0000000000000001\tconfirmation\t2026-04\t\n",
        "transcripts0/a\tb.jsonl\tcodex\t0000000000000001\tconfirmation\t2026-04\t\n",
        2 * "transcripts0/a.jsonl\tcodex\t0000000000000001\tconfirmation\t2026-04\t\n",
    ],
)
def test_a_manifest_that_breaks_the_format_is_refused(text: str) -> None:
    with pytest.raises(extract_outcome.ManifestInvalid):
        _ = extract_outcome.manifest_paths(text)


def test_a_manifest_that_is_not_utf_eight_or_absent_is_refused(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.tsv"
    _ = manifest.write_bytes(b"transcripts0/\xff.jsonl\tcodex\t0000000000000001\tdiscovery\t\t\n")
    with pytest.raises(extract_outcome.ManifestInvalid):
        _ = extract_outcome.read_manifest(manifest)
    with pytest.raises(extract_outcome.ManifestInvalid):
        _ = extract_outcome.read_manifest(tmp_path / "absent.tsv")


def test_the_module_names_no_transcript_and_no_signal() -> None:
    source = Path(extract_outcome.__file__).read_text(encoding="utf-8")
    assert "import arci" not in source
    assert "arci." not in source
    assert "no_reasoning_share" not in source
    assert "reasoning" not in source
