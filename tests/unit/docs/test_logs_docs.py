"""Release documentation stays linked, bounded and tied to recorded numbers."""

from __future__ import annotations

import io
import re
import subprocess
import sys
from dataclasses import fields
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from arci.logs.cli import run
from arci.logs.records import ReaderCounters

ROOT = Path(__file__).resolve().parents[3]
NEW_DOCS = (
    "docs/STATISTICS_LOGS.md",
    "docs/design/0016-logs.md",
    "docs/LOG_FORMATS.md",
    "docs/recipes/logs.md",
)
README_SECTIONS = (
    "New in 2.3: a result from logs you already have",
    "Controlled trials: arci run",
    "Related tools",
)
REPOSITORY = "/ajaysurya1221/agent-reliability-ci/"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    return text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]


def first_screen(text: str) -> str:
    return text.split("\n## ", 1)[0]


def test_first_screen_word_count() -> None:
    result = subprocess.run(
        [sys.executable, "plan/exec/scripts/first_screen_words.py", "README.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # The script still exits 1 above its old 200-word limit; use the printed count.
    assert result.returncode in (0, 1) and not result.stderr
    match = re.fullmatch(r"first screen: (\d+) words \(limit 200\)\n", result.stdout)
    assert match is not None and int(match.group(1)) <= 250


def test_new_readme_section_length() -> None:
    body = section(read("README.md"), README_SECTIONS[0]).strip()
    assert 12 <= len(body.splitlines()) <= 20


def linked_paths(document: str, text: str) -> list[Path]:
    targets = re.findall(r"\[[^\]\n]*\]\(([^)\s]+)\)", text)
    targets += re.findall(r"^\[[^\]]+\]:\s*(\S+)", text, re.MULTILINE)
    found: list[Path] = []
    for target in targets:
        parts = urlsplit(target.strip("<>"))
        path = unquote(parts.path)
        if parts.netloc == "github.com" and path.startswith(REPOSITORY):
            suffix = path.removeprefix(REPOSITORY)
            if suffix.startswith(("blob/", "tree/")):
                _, _, relative = suffix.split("/", 2)
                found.append(ROOT / relative)
        elif parts.netloc == "raw.githubusercontent.com" and path.startswith(REPOSITORY):
            _, relative = path.removeprefix(REPOSITORY).split("/", 1)
            found.append(ROOT / relative)
        elif not parts.scheme and not parts.netloc and path:
            found.append(
                ROOT / path.lstrip("/") if path.startswith("/") else ROOT / document / ".." / path
            )
    return found


@pytest.mark.parametrize("document", NEW_DOCS)
def test_new_document_links_exist(document: str) -> None:
    for path in linked_paths(document, read(document)):
        assert path.resolve().exists(), f"{document}: {path}"


def test_new_readme_links_exist() -> None:
    text = read("README.md")
    added = first_screen(text) + "\n".join(section(text, name) for name in README_SECTIONS)
    for path in linked_paths("README.md", added):
        assert path.resolve().exists(), str(path)


@pytest.mark.parametrize("document", NEW_DOCS[:2])
def test_contract_documents_are_finished(document: str) -> None:
    text = read(document)
    assert "plan/exec" not in text
    assert re.search(r"\bdraft\b", text, re.IGNORECASE) is None


def test_percentages_have_a_source() -> None:
    source = read("docs/results/logs-selfcheck.md")
    percentages = {Decimal(value) for value in re.findall(r"(\d+(?:\.\d+)?)%", source)}
    # The self-check prints rates as proportions; retain their full decimal precision.
    percentages.update(Decimal(value) * 100 for value in re.findall(r"\b0\.\d+\b", source))
    text = section(read("README.md"), README_SECTIONS[0])
    # The required example's -46% is generated data, not a simulation rate.
    # Its full row is checked against the live packaged example below.
    text = re.sub(r"```text\n.*?```", "", text, flags=re.DOTALL)
    text += section(read("docs/STATISTICS_LOGS.md"), "What the method cannot see")
    for value in re.findall(r"(-?\d+(?:\.\d+)?)%", text):
        assert Decimal(value) in percentages, f"unsourced percentage: {value}%"


def test_published_selfcheck_tables_are_copied_without_rounding() -> None:
    source = read("docs/results/logs-selfcheck.md")
    text = section(read("docs/STATISTICS_LOGS.md"), "What the method cannot see")
    for heading in ("Power (report only)", "Days that come in streaks (report only)"):
        for line in section(source, heading).splitlines():
            if line.startswith("|"):
                assert line in text, f"missing or changed measured row: {line}"
    # README rates must keep the design, variant and count used by these source rows.
    summary = section(read("README.md"), README_SECTIONS[0])
    for design, rate in (("5/10", "0.080500"), ("7/21", "0.035500"), ("14/42", "0.002500")):
        rows = [
            line
            for line in section(source, "Days that come in streaks (report only)").splitlines()
            if line.startswith(f"| {design} | 0.5 | 0.45 | 0 | wrong REAL DROP |")
        ]
        assert len(rows) == 1 and f"= {rate} " in rows[0].split("|")[10]
        assert rate in summary and design in summary
    assert "2000 histories each" in summary and "rule as built" in summary


def test_example_output_is_real_and_labelled(tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    assert run(["--example"], env={}, home=tmp_path, out=out, err=err) == 1
    assert not err.getvalue()
    output = out.getvalue()
    recipe = read("docs/recipes/logs.md")
    captured = re.search(r"```text\n(realornoise .*?)```", recipe, re.DOTALL)
    assert captured is not None
    # A release bump changes only the banner; the captured pre-release banner is labelled.
    assert captured.group(1).splitlines()[1:] == output.splitlines()[1:]
    assert "Example data, generated. Not anyone's logs." in captured.group(1)
    row = next(line for line in output.splitlines() if line.startswith("reasoning tokens"))
    readme = read("README.md")
    for text in (first_screen(readme), section(readme, README_SECTIONS[0])):
        assert "RESULT: REAL DROP\n" + row in text
        assert "example data" in text.lower()


def test_every_reader_counter_is_documented() -> None:
    text = read("docs/LOG_FORMATS.md")
    for field in fields(ReaderCounters):
        assert f"| `{field.name}` |" in text


def test_no_obsolete_branch_links_outside_frozen_files() -> None:
    frozen = {line.split(maxsplit=1)[1] for line in read("FROZEN.sha256").splitlines()}
    paths = (
        subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .split("\0")
    )
    obsolete = re.compile(
        r"https://github\.com/ajaysurya1221/agent-reliability-ci/(?:tree|blob)/v2/phase0(?:/|[)#\s])"
    )
    for relative in set(paths) - frozen - {""}:
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        assert obsolete.search(text) is None, relative


def test_every_published_seed_row_matches_final_selfcheck() -> None:
    source = set(read("docs/results/logs-selfcheck.md").splitlines())
    text = read("docs/STATISTICS_LOGS.md")
    seed_column: int | None = None
    rows = 0
    for line in text.splitlines():
        if not line.startswith("|"):
            seed_column = None
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if "seed" in cells:
            seed_column = cells.index("seed")
        elif seed_column is not None and cells[seed_column].isdigit():
            assert line in source, f"changed seed row: {line}"
            rows += 1
    assert rows > 0


@pytest.mark.parametrize("document", NEW_DOCS[:2])
def test_records_drop_superseded_sentences(document: str) -> None:
    text = " ".join(read(document).split())
    for old in (
        "hold only counts, rates and the names of the model and effort compared",
        "A file that cannot be opened or decoded is counted and left out, with notice F17.",
        "Lines carrying `isApiErrorMessage` count as unused types.",
        "ERROR: the tool name, `ERROR` and the F5 text, and nothing else.",
        "Null simulation with the final rule, including setting selection, usable-day rules "
        "and the streak check:",
        "Claude Code's measures pass through response and edit records, day reduction, "
        "and the production decision rule.",
    ):
        assert old not in text


def test_logs2_printed_rates_match_selfcheck() -> None:
    from arci.logs import report

    lines = section(
        read("docs/results/logs-selfcheck.md"), "Days that come in streaks (report only)"
    ).splitlines()
    header = next(line for line in lines if line.startswith("| after/before"))
    columns = [cell.strip() for cell in header.strip("|").split("|")]
    rates: dict[str, list[Decimal]] = {"5/10": [], "7/21": []}
    for line in lines:
        if not line.startswith("|") or line == header:
            continue
        cells = dict(
            zip(columns, (cell.strip() for cell in line.strip("|").split("|")), strict=True)
        )
        design = cells["after/before"]
        if (
            design not in rates
            or cells["drop"] != "0"
            or cells["metric"] != "wrong REAL DROP"
            or Decimal(cells["rho"]) <= 0
        ):
            continue
        match = re.search(r"= ([0-9.]+) ", cells["as built (95% CI)"])
        assert match is not None
        rates[design].append(Decimal(match.group(1)))
    for design, constant in (("5/10", report.RATE_5_10), ("7/21", report.RATE_7_21)):
        expected = format(max(rates[design]) * 100, "f").rstrip("0").rstrip(".")
        assert constant == expected
        assert expected + "%" in report.limits_text()
        assert expected + "%" in report.MD_LIMITS.format(
            digest="0" * 12, rate_5_10=report.RATE_5_10, rate_7_21=report.RATE_7_21
        )
