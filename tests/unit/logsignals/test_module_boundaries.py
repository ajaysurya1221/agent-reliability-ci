"""What each program may import and name.

The split the registration rests on is that no program holds both sides: the signal extractor
opens no table, the outcome extractor opens no transcript and imports no `arci`, and the
analysis, the result check and the page use the standard library alone.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from bench.logsignals import (
    analyze,
    check_result,
    extract_outcome,
    extract_signal,
    render,
    signal_counts,
)


def _imported_roots(module_file: str) -> set[str]:
    tree = ast.parse(Path(module_file).read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                roots.add(name.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("module", [analyze, check_result])
def test_the_analysis_and_the_check_use_the_standard_library_alone(module: object) -> None:
    file = getattr(module, "__file__", None)
    assert isinstance(file, str)
    roots = _imported_roots(file)
    assert "arci" not in roots
    assert roots <= set(sys.stdlib_module_names)


def _names_of(module_file: str) -> set[str]:
    """Every name the module refers to, through a Name node or an attribute."""
    tree = ast.parse(Path(module_file).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _imported_names(module_file: str, module: str) -> set[str]:
    tree = ast.parse(Path(module_file).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.name for alias in node.names)
    return names


def test_the_page_adds_only_the_studys_own_result_check_and_one_constant() -> None:
    # Step 6 runs the disclosure check before publication, so `render` calls `check_result`
    # itself and writes nothing when it fails (decision 16, finding 18). Decision C adds the one
    # name `REGISTERED_CHECKS` of `analyze`, so that no checks file is copied as it stands;
    # nothing else of `analyze` is used.
    file = getattr(render, "__file__", None)
    assert isinstance(file, str)
    roots = _imported_roots(file)
    assert "arci" not in roots
    assert roots - set(sys.stdlib_module_names) == {"bench"}
    source = Path(file).read_text(encoding="utf-8")
    assert "from bench.logsignals import check_result" in source
    assert "from bench.logsignals.analyze import REGISTERED_CHECKS" in source
    assert _imported_names(file, "bench.logsignals.analyze") == {"REGISTERED_CHECKS"}
    assert "analyze" not in _names_of(file)
    for name in ("describe", "aggregate", "rho_of_block", "read_signal", "read_outcome"):
        assert name not in _names_of(file)


def test_the_signal_counts_use_the_standard_library_and_the_analysis_reader() -> None:
    file = getattr(signal_counts, "__file__", None)
    assert isinstance(file, str)
    roots = _imported_roots(file)
    assert "arci" not in roots
    assert roots - set(sys.stdlib_module_names) == {"bench"}
    assert _imported_names(file, "bench.logsignals.analyze") >= {"read_signal", "block_keys"}


def test_the_signal_extractor_names_no_table_and_no_outcome_column() -> None:
    source = Path(extract_signal.__file__).read_text(encoding="utf-8")
    for word in ("parquet", "pyarrow", "agent_percentage"):
        assert word not in source
    assert _imported_roots(extract_signal.__file__) <= set(sys.stdlib_module_names) | {"arci"}


def test_the_outcome_extractor_imports_no_arci_and_names_no_measure() -> None:
    roots = _imported_roots(extract_outcome.__file__)
    assert "arci" not in roots
    # pyarrow is imported inside `main`, by name, so it is in no import statement.
    assert roots <= set(sys.stdlib_module_names)
    source = Path(extract_outcome.__file__).read_text(encoding="utf-8")
    assert "pyarrow" in source
    for word in ("no_reasoning_share", "reasoning_tokens", "rho"):
        assert word not in source


def test_importing_a_program_has_no_side_effect(capsys: pytest.CaptureFixture[str]) -> None:
    for module in (analyze, check_result, render, extract_signal, extract_outcome, signal_counts):
        file = getattr(module, "__file__", None)
        assert isinstance(file, str)
        tree = ast.parse(Path(file).read_text(encoding="utf-8"))
        for node in tree.body:
            assert not isinstance(node, ast.Expr) or isinstance(node.value, ast.Constant)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
