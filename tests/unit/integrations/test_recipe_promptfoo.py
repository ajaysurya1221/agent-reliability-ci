"""Check the promptfoo recipe and the five-tool index against the saved exports (D1-D3)."""

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from arci.suite_stats import default_max_rounds

REAL = Path(__file__).with_name("real")
OLDER = REAL.parents[1] / "outcomes" / "real"
RECIPES = REAL.parents[3] / "docs" / "recipes"
PROMPTFOO = RECIPES / "promptfoo.md"
INDEX = RECIPES / "eval-tools.md"
TOOLS = ("promptfoo", "deepeval", "opik", "mlflow", "langfuse")
VERSION = r"\b\d+\.\d+\.\d+\b"


def tool_version(readme: Path, tool: str) -> str:
    row = next(
        line for line in readme.read_text().splitlines() if line.startswith(f"| `{tool}/` |")
    )
    match = re.search(VERSION, row.split("|")[2])
    assert match
    return match.group()


def test_d01_versions_and_links() -> None:
    rows = [
        line.split("|")[1:-1] for line in INDEX.read_text().splitlines() if line.startswith("| [")
    ]
    assert len(rows) == len(TOOLS)
    for tool, row in zip(TOOLS, rows, strict=True):
        link, versions, route, method, caveat = (field.strip() for field in row)
        assert link.lower() == f"[{tool}]({tool}.md)"
        assert (RECIPES / f"{tool}.md").is_file()
        assert route and method and caveat
        expected = {tool_version(REAL / "README.md", tool)}
        if tool == "promptfoo":
            expected.add(tool_version(OLDER / "README.md", tool))
            assert set(re.findall(VERSION, PROMPTFOO.read_text())) == expected
        assert set(re.findall(VERSION, versions)) == expected
        assert set(re.findall(VERSION, " ".join(row))) == expected


def shell_blocks() -> list[list[list[str]]]:
    blocks = re.findall(r"^```sh\n(.*?)^```$", PROMPTFOO.read_text(), re.M | re.S)
    return [
        [shlex.split(line) for line in block.replace("\\\n", " ").splitlines() if line.strip()]
        for block in blocks
    ]


def run_arci(
    args: list[str], work: Path, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    assert args[0] == "arci"
    return subprocess.run(
        [sys.executable, "-m", "arci", *args[1:]],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize(
    ("alternative", "sources"),
    [
        (0, {"old.json": "words-baseline.json", "new.json": "words-candidate.json"}),
        (1, {"prompts.json": "two-prompts.json"}),
        (2, {"providers.json": "two-providers.json"}),
    ],
    ids=["separate-files", "two-prompts", "two-providers"],
)
def test_d02_page_convert_commands_and_descriptive_verdict(
    alternative: int, sources: dict[str, str], tmp_path: Path
) -> None:
    separate, prompts, providers, verdict, _ = shell_blocks()
    for name, source in sources.items():
        shutil.copyfile(REAL / "promptfoo" / source, tmp_path / name)
    baseline, candidate = (separate, prompts, providers)[alternative]
    for index, command in enumerate((baseline, candidate)):
        assert command[:4] == ["arci", "convert", "--from", "promptfoo"]
        assert command[command.index("--out") + 1] == ("old.jsonl", "new.jsonl")[index]
        if alternative == 1:
            assert command[command.index("--prompt") + 1] == str(index)
        if alternative == 2:
            assert command[command.index("--provider") + 1] == ("old", "new")[index]
        result = run_arci(command, tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr

    rule, compare = verdict
    assert rule[:2] == ["arci", "verdict-rule"]
    result = run_arci(rule, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert compare == [
        "arci",
        "verdict",
        "rule.yaml",
        "--baseline",
        "old.jsonl",
        "--candidate",
        "new.jsonl",
    ]
    result = run_arci(compare, tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Descriptive verdict" in result.stdout
    assert "INCONCLUSIVE" in result.stdout


def test_d02_round_cap_covers_the_repeated_export(tmp_path: Path) -> None:
    _, _, providers, (rule, compare), _ = shell_blocks()
    shutil.copyfile(REAL / "promptfoo" / "two-providers.json", tmp_path / "providers.json")
    for command in providers:
        result = run_arci(command, tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr

    # Apply the 200-task example's caps to the unmodified four-task export.
    # A wider margin makes both plans valid for this small fixture.
    assert default_max_rounds(200) == 2
    cap = re.search(r"`(--max-rounds \d+)`", PROMPTFOO.read_text())
    assert cap and shlex.split(cap[1]) == ["--max-rounds", "3"]
    for option, expected_status, message in (
        (["--max-rounds", "2"], 3, "round 3 is outside 1 to 2"),
        (shlex.split(cap[1]), 0, "both arms cover rounds 1 to 3"),
    ):
        work = tmp_path / option[1]
        work.mkdir()
        for name in ("old.jsonl", "new.jsonl"):
            shutil.copyfile(tmp_path / name, work / name)
        result = run_arci([*rule, "--margin", "3/4", *option], work)
        assert result.returncode == 0, result.stdout + result.stderr
        result = run_arci(compare, work)
        assert result.returncode == expected_status, result.stdout + result.stderr
        assert message in result.stdout + result.stderr


def test_d02_page_check_change_runs_with_saved_exports(tmp_path: Path) -> None:
    (command,) = shell_blocks()[-1]
    assert command[:4] == ["arci", "check-change", "--format", "promptfoo"]
    # Stand in for the promptfoo executable at the child-process boundary.
    # Check the arguments and serve the export for that config and round.
    program = tmp_path / "promptfoo"
    program.write_text(f"""#!{sys.executable}
import os, shutil, sys
from pathlib import Path

arm = os.environ["ARCI_CHANGE_ARM"]
config = "old.yaml" if arm == "baseline" else "new.yaml"
out = Path(sys.argv[-1])
assert sys.argv[1:-1] == [
    "eval", "-c", config, "--no-cache", "--no-table", "--no-progress-bar", "--no-share", "-o"
]
assert out.is_absolute() and out.suffix == ".json"
name = "discovery" if os.environ["ARCI_CHANGE_ROUND"] == "0" else f"r1-{{arm}}"
shutil.copyfile(Path({str(REAL / "promptfoo")!r}) / f"e2e-{{name}}.json", out)
sys.exit(100 if arm == "candidate" else 0)
""")
    program.chmod(0o755)
    result = run_arci(command, tmp_path, env={**os.environ, "PATH": str(tmp_path)})
    assert result.returncode == 1, result.stdout + result.stderr
    assert "BLOCK:" in result.stdout
    assert (tmp_path / "promptfoo-comparison" / "round-001" / "decision.json").is_file()


def test_d03_how_tested_and_caveats() -> None:
    recipe = " ".join(PROMPTFOO.read_text().split())
    for fact in (
        "tested with JSON exports",
        "the scripted provider tested exports containing two prompts or two providers",
        "Separate runs used a local HTTP server to check cache behavior",
        "descriptive verdict",
        "defaultTest.vars",
        "file://",
        "PROMPTFOO_CACHE_ENABLED=false",
        "refuses a file with repeats",
        "exit statuses 0 and 100",
        "Exit status 1",
        "400 to 599",
        "assertion that throws counts as a failure",
    ):
        assert fact in recipe
    index = INDEX.read_text()
    for tool, details in {
        "promptfoo": ("scripted provider", "HTTP stub"),
        "deepeval": ("Pytest", "ContainsWord"),
        "opik": ("Pytest", "@opik.llm_unit()"),
        "mlflow": ("mlflow.genai.evaluate", "local SQLite"),
        "langfuse": ("Python SDK", "run_experiment", "tracing off", "no live server"),
    }.items():
        row = next(line for line in index.splitlines() if f"]({tool}.md)" in line)
        for detail in details:
            assert detail in row.split("|")[4]

    for page in (index, recipe):
        assert "repeatStability" in page and "per-test pass-rate ranges" in page
        assert "mlflow.genai.compare_evaluations" in page
        assert not re.search(r"\b(first|only)\b", page, re.I)
    assert "```" not in index
