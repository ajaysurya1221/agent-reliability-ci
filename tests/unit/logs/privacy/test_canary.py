"""Rejected names and all other free log strings stay out of every output."""

import io
from pathlib import Path

import pytest

from arci.logs.cli import run
from tests.unit.logs.synth_logs import Generated, generate

CANARIES = (
    "CANARY",
    "canary-payroll",
    "98234567.76543210",
    "acme-payroll-secret",
    "gpt-12345678-87654321",
)


def arguments(logs: Generated, tool: str) -> list[str]:
    return [
        "--tool",
        tool,
        "--claude-dir",
        str(logs.claude_root),
        "--codex-dir",
        str(logs.codex_root),
        "--utc",
    ]


@pytest.mark.parametrize("keep", [False, True])
@pytest.mark.parametrize("model", [None, "model-1", "model-2"])
@pytest.mark.parametrize("tool", ["claude-code", "codex", "both"])
@pytest.mark.parametrize("option", ["--json", "--markdown", "--html", "all"])
@pytest.mark.parametrize("fault", ["none", "corrupt", "unwritable"])
def test_canaries(
    tmp_path: Path, tool: str, option: str, fault: str, model: str | None, keep: bool
) -> None:
    logs = generate(tmp_path / "CANARY-input", compressed=False)
    if fault == "corrupt":
        for paths in logs.paths.values():
            paths[0].write_bytes(b"\xff\xfeCANARY acme-payroll-secret")
    options = ("--json", "--markdown", "--html") if option == "all" else (option,)
    destinations = [tmp_path / f"output{flag[2:]}" for flag in options]
    if fault == "unwritable":
        # A directory is unwritable as a file even when tests run as root.
        destinations[-1].mkdir()
    argv = arguments(logs, tool)
    if keep:
        argv.append("--keep")
    if model is not None:
        argv.extend(["--model", model, "--effort", "effort-1"])
    for flag, target in zip(options, destinations, strict=True):
        argv.extend([flag, str(target)])
    out, err = io.StringIO(), io.StringIO()
    code = run(argv, now=logs.now, env={}, home=tmp_path, out=out, err=err)
    if fault == "unwritable":
        assert code == 3 and err.getvalue()
    else:
        assert code == 2 and not err.getvalue()
        assert all(path.is_file() for path in destinations)
    table = tmp_path / ".realornoise" / "days-1.json"
    if keep and fault != "unwritable":
        assert table.is_file()
    if fault == "unwritable":
        assert not table.exists()
    output = out.getvalue() + err.getvalue() + (table.read_text() if table.exists() else "")
    output += "".join(path.read_text() for path in destinations if path.is_file())
    secrets = (
        *CANARIES,
        str(logs.project),
        str(tmp_path),
        *(path.name for paths in logs.paths.values() for path in paths),
    )
    for secret in secrets:
        assert secret not in output
