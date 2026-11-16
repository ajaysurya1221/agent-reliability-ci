"""An audit hook observes a full CLI run; only explicitly requested writes pass."""

import importlib.util
import io
import os
import sys
from pathlib import Path

import pytest

from arci.logs.cli import run
from tests.unit.logs.privacy.test_canary import arguments
from tests.unit.logs.synth_logs import generate

_active = False
_EVENTS: list[tuple[str, tuple[object, ...]]] = []


def _audit(event: str, args: tuple[object, ...]) -> None:
    if _active:
        _EVENTS.append((event, args))
        if event == "fcntl.flock" and isinstance(args[0], int):
            info = os.fstat(args[0])
            _EVENTS.append(("locked_inode", (info.st_dev, info.st_ino)))


sys.addaudithook(_audit)


@pytest.mark.parametrize("keep", [False, True])
def test_full_run_has_no_network_process_or_unrequested_write(tmp_path: Path, keep: bool) -> None:
    global _active
    logs = generate(tmp_path / "input", compressed=False)
    targets = [tmp_path / "result.json", tmp_path / "result.md", tmp_path / "result.html"]
    argv = arguments(logs, "both")
    for flag, target in zip(("--json", "--markdown", "--html"), targets, strict=True):
        argv.extend([flag, str(target)])
    table_dir = tmp_path / ".realornoise"
    if keep:
        argv.append("--keep")
        targets.append(table_dir / "days-1.json")
        table_dir.mkdir()
        (table_dir / ".realornoise-leftover").write_text("old temporary")
        (table_dir / "unrelated").write_text("keep")
    output, error = io.StringIO(), io.StringIO()
    _EVENTS.clear()
    _active = True
    try:
        code = run(argv, now=logs.now, env={}, home=tmp_path, out=output, err=error)
    finally:
        _active = False
    assert code == 2 and not error.getvalue()
    writes: set[Path] = set()
    placeholders: set[Path] = set()
    moved: set[Path] = set()
    locked = False
    removed: set[Path] = set()
    for event, args in _EVENTS:
        assert not event.startswith(("socket.", "os.exec", "os.posix_spawn")), event
        assert event not in {"subprocess.Popen", "os.system", "urllib.Request"}, event
        if event == "open":
            name, mode, flags = args
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int)
                and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            )
            if writing:
                assert isinstance(name, str), (event, args)
                path = Path(name).absolute()
                if path in targets:
                    assert isinstance(flags, int)
                    assert flags & os.O_CREAT and flags & os.O_EXCL
                    assert not flags & (os.O_TRUNC | os.O_APPEND)
                    placeholders.add(path)
                    continue
                assert (
                    path.parent in {target.parent for target in targets[:3]}
                    and path.name.startswith(".realornoise.out-")
                ) or (
                    keep and path.parent == table_dir and path.name.startswith(".realornoise-")
                ), path
                writes.add(path)
        if event == "os.chmod":
            assert Path(str(args[0])) in writes | ({table_dir} if keep else set())
        if event == "os.mkdir":
            assert keep and Path(str(args[0])) == table_dir
        if event == "locked_inode":
            info = table_dir.stat()
            assert keep and args == (info.st_dev, info.st_ino)
            locked = True
        if event == "os.remove":
            path = Path(str(args[0]))
            assert path in placeholders | writes or (
                keep and path.parent == table_dir and path.name.startswith(".realornoise-")
            )
            removed.add(path)
        if event == "os.rename":
            source, target, *_ = args
            assert isinstance(source, str) and isinstance(target, str)
            assert Path(source) in writes and Path(target) in targets
            moved.add(Path(target))
    assert moved == set(targets)
    assert placeholders == set(targets)
    assert all(not path.exists() for path in writes)
    if keep:
        if importlib.util.find_spec("fcntl") is not None:
            assert locked
        assert table_dir / ".realornoise-leftover" in removed
        assert (table_dir / "unrelated").read_text() == "keep"
        assert {p.name for p in table_dir.iterdir()} == {"days-1.json", "unrelated"}
