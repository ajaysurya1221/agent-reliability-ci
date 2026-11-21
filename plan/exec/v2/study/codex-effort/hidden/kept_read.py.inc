def test_table_installed_during_open(tmp_path: Path) -> None:
    """CPython's open audit event covers builtin, io, pathlib and os.open."""
    import sys

    path = tmp_path / kept.FILENAME
    path.write_bytes(b"")
    completed = tmp_path / "replacement"
    completed.write_text(table("gpt-5"))
    pending = True

    def transition(event: str, arguments: tuple[object, ...]) -> None:
        nonlocal pending
        if event == "open" and pending and arguments[0] == str(path):
            pending = False
            completed.replace(path)
            raise FileNotFoundError(path)

    sys.addaudithook(transition)
    assert kept.read(path) == ("read", (row(model="gpt-5"),))
