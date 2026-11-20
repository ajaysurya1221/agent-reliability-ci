"""The reachability walk of the two separation tests, across the modules of `bench/logsignals`.

MINOR 9 of review 3: a walk that reads one file never enters the bodies of `read_signal`,
`block_keys` or `signal_side_counts` inside `analyze`, so a forbidden call added inside a helper
of `analyze` would not be caught. This walk follows every name a reached function uses: a name the
starting module defines is that module's own function, as Python resolves it, and any other name
is resolved in every sibling module of the package, so one reached name may be followed into more
than one body. That over-counts rather than under-counts, which is what a forbidden-call check
needs.

It reads source files with `ast` and imports nothing from them.
"""

from __future__ import annotations

import ast
from pathlib import Path


def functions_of(module_file: str) -> dict[str, ast.FunctionDef]:
    """Every function of one module by name, the methods of its classes included."""
    tree = ast.parse(Path(module_file).read_text(encoding="utf-8"))
    return {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def names_used(node: ast.AST) -> set[str]:
    """Every name and attribute name one function body mentions."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def _siblings(module_file: str) -> dict[str, list[ast.FunctionDef]]:
    """Every function of the other modules beside this one, by name."""
    here = Path(module_file)
    found: dict[str, list[ast.FunctionDef]] = {}
    for path in sorted(here.parent.glob("*.py")):
        if path.name == here.name:
            continue
        for name, node in functions_of(str(path)).items():
            found.setdefault(name, []).append(node)
    return found


def reachable(module_file: str, roots: list[str]) -> set[str]:
    """Every name reachable from `roots`, following calls into the sibling modules as well."""
    local = functions_of(module_file)
    siblings = _siblings(module_file)
    seen: set[str] = set()
    todo = list(roots)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        bodies = [local[name]] if name in local else siblings.get(name, [])
        for body in bodies:
            for used in names_used(body):
                if used not in seen:
                    todo.append(used)
    return seen
