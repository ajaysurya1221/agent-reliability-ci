"""An audit hook observes a full CLI run; only explicitly requested writes pass."""

import io
import os
import sys
from pathlib import Path

from arci.logs.cli import run
from tests.unit.logs.privacy.test_canary import arguments
from tests.unit.logs.synth_logs import generate

_active = False
_EVENTS: list[tuple[str, tuple[object, ...]]] = []


def _audit(event: str, args: tuple[object, ...]) -> None:
    if _active:
        _EVENTS.append((event, args))


sys.addaudithook(_audit)


def test_full_run_has_no_network_process_or_unrequested_write(tmp_path: Path) -> None:
    global _active
    logs = generate(tmp_path / "input", compressed=False)
    targets = [tmp_path / "result.json", tmp_path / "result.md", tmp_path / "result.html"]
    argv = arguments(logs, "both")
    for flag, target in zip(("--json", "--markdown", "--html"), targets, strict=True):
        argv.extend([flag, str(target)])
    output, error = io.StringIO(), io.StringIO()
    _EVENTS.clear()
    _active = True
    try:
        code = run(argv, now=logs.now, env={}, home=tmp_path, out=output, err=error)
    finally:
        _active = False
    assert code == 2 and not error.getvalue()
    writes: set[Path] = set()
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
                assert path in targets, path
                writes.add(path)
    assert writes == set(targets)
