"""Black-box checks for the promptfoo conversion contract in design 0020."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from itertools import product
from pathlib import Path
from typing import NotRequired, TypedDict, cast

import pytest

from arci.hashing import hash_record

REAL = Path(__file__).resolve().parent / "real" / "promptfoo"
OLDER = REAL.parents[2] / "outcomes" / "real" / "promptfoo"
SINGLE = REAL / "words-single.json"
REPEATED = REAL / "words-baseline.json"
CELLS = {
    "two-prompts": ((0, "scripted"), (1, "scripted")),
    "two-providers": ((0, "old"), (1, "new")),
}
STATS = {"pass": "successes", "fail": "failures", "error": "errors"}
DELETE = object()


class Case(TypedDict, total=False):
    description: str | None
    vars: dict[str, object] | None


class Provider(TypedDict):
    id: str
    label: NotRequired[str]


class RawRow(TypedDict):
    testCase: Case
    promptIdx: int
    provider: Provider
    repeatIndex: NotRequired[int | None]
    success: bool
    failureReason: int


class Results(TypedDict):
    results: list[RawRow]
    stats: dict[str, int]


class Document(TypedDict):
    results: Results


def load(source: Path) -> Document:
    return cast(Document, json.loads(source.read_bytes()))


def edited(tmp: Path, original: Path, path: tuple[str | int, ...], value: object) -> Path:
    """Change one JSON location in a fresh copy, including deliberately ill-typed values."""
    doc = load(original)
    node: object = doc
    for key in path[:-1]:
        if isinstance(key, int):
            node = cast(list[object], node)[key]
        else:
            node = cast(dict[str, object], node)[key]
    parent = cast(dict[str, object], node)
    field = path[-1]
    assert isinstance(field, str)
    if value is DELETE:
        del parent[field]
    else:
        parent[field] = value
    return save(tmp, doc)


def save(tmp: Path, value: object) -> Path:
    source = tmp / "source.json"
    source.write_text(json.dumps(value, ensure_ascii=True), encoding="utf-8")
    return source


def arci(tmp: Path, *args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "arci", *args],
        cwd=tmp,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )


def convert(tmp: Path, source: Path, out: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return arci(tmp, "convert", "--from", "promptfoo", source, "--out", out, *args)


def tree(tmp: Path) -> dict[Path, bytes | None]:
    return {p: p.read_bytes() if p.is_file() else None for p in tmp.rglob("*")}


def refused(tmp: Path, source: Path, *args: str, out: Path | None = None) -> str:
    before = tree(tmp)
    proc = convert(tmp, source, out or tmp / "out.jsonl", *args)
    message = (proc.stdout + proc.stderr).strip()
    after = tree(tmp)
    assert (proc.returncode, after == before) == (3, True), (
        proc.returncode,
        message,
        "changed paths",
        [
            str(p)
            for p in before.keys() | after.keys()
            if p not in before or p not in after or before[p] != after[p]
        ],
    )
    assert message and "Traceback" not in message
    return message


def cell(row: RawRow) -> tuple[int, str]:
    return row["promptIdx"], row["provider"].get("label", row["provider"]["id"])


def outcome(row: RawRow) -> str:
    return "error" if row["failureReason"] == 2 else "pass" if row["success"] else "fail"


class NeutralRow(TypedDict):
    task_id: str
    outcome: str
    source_sha256: str
    reader: str
    round: NotRequired[int]


def expected(source: Path, selected: tuple[int, str] | None = None) -> list[NeutralRow]:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    results = load(source)["results"]
    counts = Counter(outcome(r) for r in results["results"])
    assert {k: counts[k] for k in STATS} == {k: results["stats"][v] for k, v in STATS.items()}
    rows: list[NeutralRow] = []
    for raw in results["results"]:
        if selected is not None and cell(raw) != selected:
            continue
        case = raw["testCase"]
        desc = case.get("description")
        suffix = hash_record({"description": desc, "vars": case.get("vars") or {}})[:16]
        row: NeutralRow = {
            "task_id": f"{(desc or 'test')[:80]} #{suffix}",
            "outcome": outcome(raw),
            "source_sha256": digest,
            "reader": "promptfoo/1",
        }
        index = raw.get("repeatIndex")
        if index is not None:
            row["round"] = index + 1
        rows.append(row)
    return rows


def accepted(
    tmp: Path,
    source: Path,
    *args: str,
    selected: tuple[int, str] | None = None,
    name: str = "out.jsonl",
) -> tuple[list[NeutralRow], str]:
    rows = expected(source, selected)
    assert rows
    before = tree(tmp)
    out = tmp / name
    proc = convert(tmp, source, out, *args)
    message = proc.stdout + proc.stderr
    assert proc.returncode == 0, message
    data = out.read_bytes()
    assert tree(tmp) == {**before, out: data}
    lines = [
        json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
        for r in rows
    ]
    assert data == "".join(lines).encode("utf-8")
    return [cast(NeutralRow, json.loads(line)) for line in data.splitlines()], message


@pytest.mark.parametrize(
    "source",
    sorted(
        p
        for directory in (REAL, OLDER)
        for p in directory.glob("*.json")
        if p.stem not in {*CELLS, "shapes", "cache-warm"}
    ),
    ids=lambda p: p.stem,
)
def test_blind_real_rows(tmp_path: Path, source: Path) -> None:
    accepted(tmp_path, source)


def test_blind_golden_id(tmp_path: Path) -> None:
    doc = load(SINGLE)
    case = doc["results"]["results"][0]["testCase"]
    case.update(description="Row #1", vars={"x": [1, 1.0, True, None, ["é"]]})
    rows, _ = accepted(tmp_path, save(tmp_path, doc))
    assert rows[0]["task_id"] == "Row #1 #25722901d99dfa75"


@pytest.mark.parametrize(
    "desc",
    ["a #" + "🐍é" * 40, "left #right", "", DELETE, None],
    ids=["long-unicode", "embedded-delimiter", "empty", "absent", "null"],
)
def test_blind_description(tmp_path: Path, desc: object) -> None:
    source = edited(tmp_path, SINGLE, ("results", "results", 0, "testCase", "description"), desc)
    accepted(tmp_path, source)


@pytest.mark.parametrize(
    "variables",
    [DELETE, None, {}, {"x": {"b": [1, 1.0], "a": "é"}}, {"x": 1}, {"x": 1.0}],
    ids=["absent", "null", "empty", "nested", "integer", "fraction"],
)
def test_blind_vars(tmp_path: Path, variables: object) -> None:
    source = edited(tmp_path, SINGLE, ("results", "results", 0, "testCase", "vars"), variables)
    accepted(tmp_path, source)


def test_blind_shared_ids(tmp_path: Path) -> None:
    reference = {r["task_id"] for r in expected(SINGLE)}
    for source in (SINGLE, REPEATED, REAL / "words-candidate.json", *sorted(OLDER.glob("*.json"))):
        rows, _ = accepted(tmp_path, source, name=f"{source.stem}.jsonl")
        for number in {r.get("round") for r in rows}:
            assert {r["task_id"] for r in rows if r.get("round") == number} == reference


def test_blind_reorder(tmp_path: Path) -> None:
    doc = load(SINGLE)
    rows = doc["results"]["results"]
    rows[0]["testCase"]["vars"] = {"first": 1, "second": 2}
    original, _ = accepted(tmp_path, save(tmp_path, doc))
    rows[0]["testCase"]["vars"] = {"second": 2, "first": 1}
    rows.reverse()
    reordered, _ = accepted(tmp_path, save(tmp_path, doc), name="reordered.jsonl")
    assert [r["task_id"] for r in reordered] == [r["task_id"] for r in reversed(original)]


@pytest.mark.parametrize(("reason", "success"), list(product(range(3), (True, False))))
def test_blind_outcome(tmp_path: Path, reason: int, success: bool) -> None:
    doc = load(SINGLE)
    results = doc["results"]
    row = results["results"][0]
    row.update(failureReason=reason, success=success)
    # Match the reason so the file's counters are valid for each legitimate outcome.
    stats = results["stats"]
    stats["successes"] -= 1
    stats[("successes", "failures", "errors")[reason]] += 1
    source = save(tmp_path, doc)
    if success == (reason == 0):
        rows, _ = accepted(tmp_path, source)
        assert rows[0]["outcome"] == ("pass", "fail", "error")[reason]
    else:
        msg = refused(tmp_path, source).lower()
        assert "success" in msg or "failurereason" in msg, msg


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("promptIdx", False),
        ("repeatIndex", False),
        ("failureReason", False),
        ("promptIdx", 0.0),
        ("repeatIndex", 0.0),
        ("failureReason", 0.0),
        ("repeatIndex", -1),
        ("success", 1),
        ("failureReason", 3),
        ("testCase", DELETE),
    ],
)
def test_blind_invalid_row(tmp_path: Path, field: str, value: object) -> None:
    source = edited(tmp_path, REPEATED, ("results", "results", 0, field), value)
    refused(tmp_path, source)


def test_blind_vars_must_be_object(tmp_path: Path) -> None:
    refused(tmp_path, edited(tmp_path, SINGLE, ("results", "results", 0, "testCase", "vars"), []))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("stats", "cacheHits"), 1),
        (("results", 0, "response", "cached"), True),
        (("prompts", 0, "metrics", "testCacheHitCount"), 1),
        (("repeatStability", "cachedResults"), 1),
        (("repeatStability", "groups", 0, "cached"), 2),
        (("repeatStability", "groups", 0, "cached"), True),
        (("results", 0, "gradingResult", "metadata"), {"cachedResponse": True}),
        (
            ("results", 0, "gradingResult", "componentResults", 0, "metadata"),
            {"cachedResponse": True},
        ),
        (
            ("results", 0, "gradingResult", "componentResults", 0, "componentResults"),
            [{"metadata": {"cachedResponse": True}}],
        ),
    ],
    ids=[
        "stats",
        "response",
        "prompt",
        "stability-total",
        "group-two",
        "group-true",
        "grading",
        "component",
        "nested-component",
    ],
)
def test_blind_cache_signal(tmp_path: Path, path: tuple[str | int, ...], value: object) -> None:
    source = edited(tmp_path, REPEATED, ("results", *path), value)
    assert "cach" in refused(tmp_path, source).lower()


@pytest.mark.parametrize("name", ["cache-cold", "cache-env-off"])
def test_blind_cache_notice(tmp_path: Path, name: str) -> None:
    _, message = accepted(tmp_path, REAL / f"{name}.json")
    assert re.search(r"cach\w*[^\n]*(?:earlier|previous|prior|past)", message, re.I), message


@pytest.mark.parametrize(
    ("name", "reason"), [("cache-warm", r"cach"), ("shapes", r"duplicat|same|repeated id")]
)
def test_blind_real_refusal(tmp_path: Path, name: str, reason: str) -> None:
    assert re.search(reason, refused(tmp_path, REAL / f"{name}.json"), re.I)


def selector_cases() -> list[tuple[str, int | None, str | None]]:
    return [
        (name, prompt, provider)
        for name, cells in CELLS.items()
        for prompt, provider in product(
            (None, 0, 1, 9), (None, *sorted({p for _, p in cells}), "unknown")
        )
    ]


@pytest.mark.parametrize(("name", "prompt", "provider"), selector_cases())
def test_blind_cells(tmp_path: Path, name: str, prompt: int | None, provider: str | None) -> None:
    source = REAL / f"{name}.json"
    cells = {cell(r) for r in load(source)["results"]["results"]}
    matches = [c for c in cells if prompt in (None, c[0]) and provider in (None, c[1])]
    args: list[str] = []
    if prompt is not None:
        args += ["--prompt", str(prompt)]
    if provider is not None:
        args += ["--provider", provider]
    if len(matches) != 1:
        msg = refused(tmp_path, source, *args)
        for index, label in cells:
            assert re.search(rf"\b{index}\b", msg) and label in msg, msg
        return
    rows, _ = accepted(tmp_path, source, *args, selected=matches[0])
    assert {r["round"] for r in rows if "round" in r} == {1, 2, 3}
    other = next(c for c in cells if c != matches[0])
    assert {r["task_id"] for r in rows} == {r["task_id"] for r in expected(source, other)}


def test_blind_provider_id_fallback(tmp_path: Path) -> None:
    doc = load(SINGLE)
    for row in doc["results"]["results"]:
        del row["provider"]["label"]
    accepted(tmp_path, save(tmp_path, doc), "--provider", "scripted", selected=(0, "scripted"))


@pytest.mark.parametrize("issue", ["cache", "http", "recount"])
def test_blind_unselected_cell(tmp_path: Path, issue: str) -> None:
    source = REAL / "two-providers.json"
    doc = load(source)
    rows = doc["results"]["results"]
    index = next(i for i, r in enumerate(rows) if cell(r) == (1, "new") and r["success"])
    if issue == "recount":
        rows[index].update(success=False, failureReason=1)
        changed = save(tmp_path, doc)
    else:
        field, value = (
            ("cached", True) if issue == "cache" else ("metadata", {"http": {"status": 500}})
        )
        changed = edited(tmp_path, source, ("results", "results", index, "response", field), value)
    refused(tmp_path, changed, "--provider", "old")


@pytest.mark.parametrize("form", ["absent", "null"])
def test_blind_unlabelled_round(tmp_path: Path, form: str) -> None:
    doc = load(SINGLE)
    for row in doc["results"]["results"]:
        if form == "absent":
            row.pop("repeatIndex", None)
        else:
            row["repeatIndex"] = None
    source = edited(tmp_path, save(tmp_path, doc), ("runtimeOptions", "repeat"), DELETE)
    rows, _ = accepted(tmp_path, source)
    assert all("round" not in row for row in rows)


def test_blind_missing_all_repeat_indices(tmp_path: Path) -> None:
    refused(tmp_path, edited(tmp_path, SINGLE, ("runtimeOptions", "repeat"), 2))


def test_blind_boolean_repeat_count(tmp_path: Path) -> None:
    """contract silent on the repeat count's JSON type. True is a flag, not a count of one."""
    refused(tmp_path, edited(tmp_path, SINGLE, ("runtimeOptions", "repeat"), True))


@pytest.mark.parametrize(
    "change", ["declared-two", "absent-index", "null-index", "gap", "different-ids"]
)
def test_blind_bad_rounds(tmp_path: Path, change: str) -> None:
    doc = load(REPEATED)
    rows = doc["results"]["results"]
    if change == "declared-two":
        source = edited(tmp_path, REPEATED, ("runtimeOptions", "repeat"), 2)
    else:
        if change == "absent-index":
            del rows[0]["repeatIndex"]
        elif change == "null-index":
            rows[0]["repeatIndex"] = None
        elif change == "gap":
            for row in rows:
                if row.get("repeatIndex") == 2:
                    row["repeatIndex"] = 3
        else:
            rows[0]["testCase"]["description"] = "only in round one"
        source = save(tmp_path, doc)
    refused(tmp_path, source)


@pytest.mark.parametrize("status", [500, 500.0, 404, 429, 399])
def test_blind_http_status(tmp_path: Path, status: int | float) -> None:
    source = edited(
        tmp_path,
        REAL / "cache-cold.json",
        ("results", "results", 1, "response", "metadata", "http", "status"),
        status,
    )
    if status >= 400:
        msg = refused(tmp_path, source)
        assert re.search(r"http|status", msg, re.I), msg
    else:
        accepted(tmp_path, source)


@pytest.mark.parametrize("field", list(STATS.values()))
def test_blind_recount(tmp_path: Path, field: str) -> None:
    source = REAL / "two-providers.json"
    original = load(source)["results"]["stats"][field]
    refused(
        tmp_path,
        edited(tmp_path, source, ("results", "stats", field), original + 1),
        "--provider",
        "old",
    )


def test_blind_results_version(tmp_path: Path) -> None:
    refused(tmp_path, edited(tmp_path, SINGLE, ("results", "version"), 2))


def test_blind_nonobject(tmp_path: Path) -> None:
    refused(tmp_path, save(tmp_path, [load(SINGLE)]))


def test_blind_duplicate_key(tmp_path: Path) -> None:
    raw = json.dumps(load(SINGLE))
    marker = '"failureReason": 0'
    assert marker in raw
    source = tmp_path / "source.json"
    source.write_text(raw.replace(marker, marker + ", " + marker, 1), encoding="utf-8")
    refused(tmp_path, source)


def test_blind_float_overflow(tmp_path: Path) -> None:
    raw = json.dumps(load(SINGLE))
    marker = '"platform": "darwin"'
    assert raw.count(marker) == 1
    source = tmp_path / "source.json"
    source.write_text(raw.replace(marker, '"platform": 1e309'), encoding="utf-8")
    refused(tmp_path, source)


@pytest.mark.parametrize(
    "path",
    [
        ("results", "results", 0, "testCase", "description"),
        ("metadata", "platform"),
    ],
    ids=["hashed-description", "unused-metadata"],
)
def test_blind_lone_surrogate(tmp_path: Path, path: tuple[str | int, ...]) -> None:
    refused(tmp_path, edited(tmp_path, SINGLE, path, "\ud800"))


@pytest.mark.parametrize("case", ["suffix", "exists", "same", "missing-parent", "missing-source"])
def test_blind_paths(tmp_path: Path, case: str) -> None:
    source = tmp_path / ("input.jsonl" if case == "same" else "input.json")
    if case != "missing-source":
        source.write_bytes(SINGLE.read_bytes())
    out = tmp_path / "out.jsonl"
    if case == "exists":
        out.write_bytes(b"existing destination\x00\xff\n")
    elif case == "same":
        out = source
    elif case == "suffix":
        out = tmp_path / "out.json"
    elif case == "missing-parent":
        out = tmp_path / "missing" / out.name
    refused(tmp_path, source, out=out)


def test_blind_determinism(tmp_path: Path) -> None:
    accepted(tmp_path, REPEATED, name="a.jsonl")
    accepted(tmp_path, REPEATED, name="b.jsonl")
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()


def test_blind_convert_summary(tmp_path: Path) -> None:
    rows, message = accepted(tmp_path, REPEATED)
    assert "promptfoo/1" in message and "0.126.0" in message and rows[0]["source_sha256"] in message
    assert "baseline" in message
    statement = (
        "These are existing results: use arci verdict-rule and arci verdict for a descriptive "
        "verdict; the error bound needs fresh runs (arci check-change)."
    )
    assert statement in " ".join(message.replace("`", "").split())


def test_blind_untested_version(tmp_path: Path) -> None:
    source = edited(tmp_path, SINGLE, ("metadata", "promptfooVersion"), "0.999.0")
    _, message = accepted(tmp_path, source)
    notices = [
        line
        for line in message.lower().splitlines()
        if re.search(r"not tested|untested|un(?:der)?tested|never tested|only tested", line)
    ]
    assert len(notices) == 1, message


def test_blind_descriptive_verdict(tmp_path: Path) -> None:
    """A5 requires descriptive pair counts. Layout and headings are contract silent."""
    candidate = REAL / "words-candidate.json"
    for source, name in ((REPEATED, "base.jsonl"), (candidate, "candidate.jsonl")):
        accepted(tmp_path, source, name=name)
    rule = arci(tmp_path, "verdict-rule", "--tasks", "base.jsonl", "--out", "rule.json")
    assert rule.returncode == 0, rule.stderr
    verdict = arci(
        tmp_path,
        "verdict",
        "rule.json",
        "--baseline",
        "base.jsonl",
        "--candidate",
        "candidate.jsonl",
    )
    assert verdict.returncode in (0, 1, 2), (verdict.returncode, verdict.stderr)
    assert "descriptive" in verdict.stdout.lower()
    arms = [
        {(r.get("round"), r["task_id"]): r["outcome"] for r in expected(source)}
        for source in (REPEATED, candidate)
    ]
    base, cand = arms
    assert base.keys() == cand.keys()
    table = [
        [c.strip().lower() for c in line.strip("| ").split("|")]
        for line in verdict.stdout.splitlines()
        if line.lstrip().startswith("|")
    ]
    header = next(line for line in table if "round" in line and "pairs" in line)
    counts: Counter[str] = Counter()
    for number in (1, 2, 3):
        for key, left in base.items():
            if key[0] != number:
                continue
            right = cand[key]
            if "error" in (left, right):
                counts["errored"] += 1
            elif left == right:
                counts["zero"] += 1
            else:
                counts["minus" if left == "pass" else "plus"] += 1
        data = next(line for line in table if line[header.index("round")] == str(number))
        assert int(data[header.index("pairs")]) == counts.total()
        for label in ("minus", "zero", "plus", "errored"):
            assert int(data[header.index(label)]) == counts[label], (number, label, data)
