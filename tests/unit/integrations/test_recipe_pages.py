"""ADR 0020 D1-D3. Compare the four recipes with the saved generators and exports."""

import re
import shlex
import shutil
import sys
from pathlib import Path

import pytest

from arci.cli import main
from arci.outcome_schema import OutcomeDecision
from arci.schema import Verdict

REAL = Path(__file__).with_name("real")
ROOT = REAL.parents[3]
TOOLS = ("deepeval", "opik", "mlflow", "langfuse")
SCRIPTS = {"mlflow": "evaluate_agent.py", "langfuse": "run_experiment.py"}


def page(tool: str) -> Path:
    return ROOT / "docs" / "recipes" / f"{tool}.md"


def blocks(tool: str, language: str) -> list[bytes]:
    pattern = rb"^```" + language.encode() + rb"\n(.*?)^```$"
    return re.findall(pattern, page(tool).read_bytes(), flags=re.M | re.S)


@pytest.mark.parametrize("tool", TOOLS)
def test_d01_versions_match_fixture_readme(tool: str) -> None:
    readme = (REAL / "README.md").read_text()
    row = next(line for line in readme.splitlines() if line.startswith(f"| `{tool}/` |"))
    versions = r"([\w]+(?: Python SDK)?) (\d+\.\d+(?:\.\d+)*)\b"
    tested = dict(re.findall(versions, row.split("|")[2]))
    content = page(tool).read_text()
    assert set(re.findall(versions, content)) == set(tested.items())
    assert set(re.findall(r"\b\d+\.\d+\.\d+\b", content)) == set(tested.values())


def junit_program(tool: str, work: Path, commands: list[list[str]]) -> None:
    generator = (REAL / "generate_pytest_tools.sh.txt").read_text()
    runner = "deepeval" if tool == "deepeval" else "pytest"
    executable = f"$E/{tool}/.venv/bin/{runner}"
    run_line = next(
        line
        for line in generator.splitlines()
        if executable in line and "test_agent.py" in line and "$1.xml" in line
    )
    # Remove the fixture sandbox and log redirections. Bind the same mode and
    # output path that the shell loop supplied to the real tool.
    tokens = shlex.split(run_line.split(" > ")[0])
    flags = tokens[tokens.index(executable) + 1 :]
    assert flags[-1] == f"--junitxml=$O/{tool}/$1.xml"
    settings = tokens[: tokens.index("sandbox-exec")]
    for mode, args in zip(("pass", "fail"), commands, strict=True):
        env = [setting.replace("$2", mode) for setting in settings]
        assert args == ["env", *env, runner, *flags[:-1], "--junitxml={out}"]

    # ARCI launches the page's exact argv. Substitute saved XML at the tool
    # boundary so this test needs neither optional SDK nor a server.
    program = work / runner
    program.write_text(f"""#!{sys.executable}
import os, shutil, sys
from pathlib import Path
mode = os.environ["AGENT_MODE"]
discovery = os.environ["ARCI_CHANGE_ROUND"] == "0"
name = "discovery" if discovery else "r1-baseline" if mode == "pass" else "r1-candidate"
out = sys.argv[-1].removeprefix("--junitxml=")
shutil.copyfile(Path({str(REAL / tool)!r}) / f"e2e-{{name}}.xml", out)
sys.exit(int(mode == "fail"))
""")
    program.chmod(0o755)


def exporter_program(tool: str, work: Path, commands: list[list[str]]) -> None:
    script = SCRIPTS[tool]
    generator = (REAL / tool / (script + ".txt")).read_text()
    assert f"python {script} MODE OUTDIR" in generator and "MODE pass|fail" in generator
    assert commands == [["python", script, mode, "{out}"] for mode in ("pass", "fail")]

    # Supply what the SDK returned, then run the usage snippet with the actual
    # helper beside the script, as a user copying the recipe would.
    preamble = f"""import json, sys
from pathlib import Path
from types import SimpleNamespace
source = Path({str(REAL / tool)!r})
mode = sys.argv[1]
"""
    if tool == "mlflow":
        assert "res = mlflow.genai.evaluate(" in generator
        preamble += """
class Frame:
    def to_dict(self, orient):
        assert orient == "records"
        return json.loads((source / f"result_df-{mode}.json").read_bytes())
res = SimpleNamespace(result_df=Frame())
"""
    else:
        assert "res = client.run_experiment(" in generator
        preamble += """
cases = [{"metadata": {"task_id": f"task-w{n:02d}"}} for n in range(1, 21)]
items = json.loads((source / f"item_results-{mode}.json").read_bytes())["items"]
res = SimpleNamespace(item_results=[
    SimpleNamespace(item=r["item"], evaluations=[SimpleNamespace(**e) for e in r["evaluations"]])
    for r in items
])
"""
    helper = ROOT / "examples" / "integrations" / f"{tool}_rows.py"
    shutil.copyfile(helper, work / helper.name)
    usage, _ = blocks(tool, "python")
    (work / script).write_bytes(preamble.encode() + usage)
    (work / "python").symlink_to(sys.executable)


@pytest.mark.parametrize("tool", TOOLS)
def test_d02_documented_command_runs(
    tool: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (command,) = blocks(tool, "sh")
    argv = shlex.split(command.decode().replace("\\\n", " "))
    fmt = "jsonl" if tool in SCRIPTS else "junit"
    assert argv[:4] == ["arci", "check-change", "--format", fmt]
    assert argv[4::2] == ["--baseline", "--candidate", "--out-dir"]
    assert argv[-1] == f"{tool}-comparison"
    commands = [shlex.split(arm) for arm in (argv[5], argv[7])]
    if tool in SCRIPTS:
        exporter_program(tool, tmp_path, commands)
    else:
        junit_program(tool, tmp_path, commands)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    assert main(argv[1:]) == 1
    report = OutcomeDecision.model_validate_json(
        (tmp_path / argv[-1] / "round-001/decision.json").read_bytes()
    )
    assert report.verdict == Verdict.BLOCK
    assert report.history[0].counts.errored == (2 if tool in SCRIPTS else 0)


@pytest.mark.parametrize(
    ("tool", "facts"),
    [
        (
            "deepeval",
            [
                "pytest",
                "containsword",
                "junit",
                "ids=[",
                "exception in the test body",
                "counts as a failure",
                "pytest.skip(",
            ],
        ),
        (
            "opik",
            [
                "pytest",
                "@opik.llm_unit()",
                "cloud address",
                "by default",
                "ids=[",
                "exception in the test body",
                "counts as a failure",
                "pytest.skip(",
            ],
        ),
        (
            "mlflow",
            [
                "mlflow.genai.evaluate",
                "local sqlite",
                "20 items",
                "scorer",
                "mlflow.genai.compare_evaluations",
                "margin of allowed loss",
                "fresh paired runs",
                "after each round",
                "cannot tell",
                "launches both versions",
            ],
        ),
        (
            "langfuse",
            [
                "`run_experiment`",
                "tracing was off",
                "no server was listening",
                "not tested against a live langfuse",
                "20 word checks",
            ],
        ),
    ],
)
def test_d03_test_scope_and_caveats(tool: str, facts: list[str]) -> None:
    content = " ".join(page(tool).read_text().lower().split())
    assert "tested" in content
    for fact in facts:
        assert fact in content
    assert not re.search(r"\b(first|only)\b", content)


@pytest.mark.parametrize("tool", SCRIPTS)
def test_d03_helper_bytes(tool: str) -> None:
    helper = ROOT / "examples" / "integrations" / f"{tool}_rows.py"
    heading = f"Save this complete block as `{helper.name}`".encode()
    _, after_heading = page(tool).read_bytes().split(heading)
    paragraph, helper_block = after_heading.split(b"\n\n", 1)
    assert b"```" not in paragraph
    assert helper_block.startswith(b"```python\n" + helper.read_bytes() + b"```\n")
