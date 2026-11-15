"""A closed import allow-list, including lazy/dynamic imports and relative paths."""

import ast
from pathlib import Path

STDLIB = frozenset(
    {
        "__future__",
        "argparse",
        "collections",
        "contextlib",
        "dataclasses",
        "datetime",
        "fractions",
        "functools",
        "html",
        "importlib",
        "itertools",
        "json",
        "math",
        "os",
        "pathlib",
        "re",
        "sys",
        "textwrap",
        "typing",
        "compression",
    }
)
ARCI = frozenset({"arci.hashing", "arci.html_base", "arci.outcome_report", "arci.__version__"})
ROOT = Path(__file__).resolve().parents[4] / "src/arci/logs"


def permitted(name: str) -> bool:
    return (
        name.split(".")[0] in STDLIB
        or name == "pydantic"
        or name.startswith("pydantic.")
        or name in ARCI
        or name == "arci.logs"
        or name.startswith("arci.logs.")
    )


def test_import_allow_list() -> None:
    paths = sorted(ROOT.rglob("*.py"))
    assert paths
    for path in paths:
        relative = path.relative_to(ROOT).with_suffix("").parts
        package = "arci.logs" + ("." + ".".join(relative[:-1]) if len(relative) > 1 else "")
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = ".".join(package.split(".")[: len(package.split(".")) - node.level + 1])
                    module = base + ("." + node.module if node.module else "")
                else:
                    module = node.module or ""
                names = (
                    [module + "." + alias.name for alias in node.names]
                    if module == "arci"
                    else [module]
                )
            elif isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Name) and node.func.id == "__import__")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
            ):
                assert node.args and isinstance(node.args[0], ast.Constant), (path, node.lineno)
                name = node.args[0].value
                assert isinstance(name, str), (path, node.lineno)
                names = [name]
            for name in names:
                assert permitted(name), (path, name)
