"""Shared, deterministic HTML styling and escaping helpers."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from html import escape

__all__ = ["_CSS", "_heading", "_p", "_table", "_text", "_wrap_class", "visible_text"]

_CSS = """
:root { color-scheme: light dark; --paper: #fff; --ink: #17202a; --line: #677583; }
@media (prefers-color-scheme: dark) {
  :root { --paper: #141a20; --ink: #edf2f7; --line: #9aaaba; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink);
  font: 16px/1.6 system-ui, sans-serif; }
main { max-width: 1100px; margin: auto; padding: clamp(16px, 4vw, 48px); }
h1 { font-size: clamp(24px, 5vw, 38px); line-height: 1.2; }
h2 { margin-top: 2em; font-size: 1.25em; }
.long-value { overflow-wrap: anywhere; }
.verdict { border: 2px solid currentColor; padding: 16px; font-weight: bold; }
.table { overflow-x: auto; margin: 1em 0; }
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { border-bottom: 1px solid var(--line); text-align: left; padding: 8px; }
th { vertical-align: bottom; } td { vertical-align: top; min-width: 6ch; }
svg { display: block; width: 100%; height: auto; color: var(--ink); }
pre { white-space: pre-wrap; }
@media print { .table { overflow: visible; } body { font-size: 10pt; } }
"""


def visible_text(value: object) -> str:
    """Keep stored data on one visible line, including invisible/bidi controls."""
    return "".join(
        f"\\u{ord(char):04x}"
        if unicodedata.category(char) in {"Cc", "Cf", "Zl", "Zp", "Cs"}
        else char
        for char in str(value)
    )


def _text(value: object) -> str:
    return escape(visible_text(value), quote=True)


def _wrap_class(value: object) -> str:
    # Preserve ordinary words' min-content widths, especially the arm names.
    return (
        ' class="long-value"' if any(len(word) > 24 for word in visible_text(value).split()) else ""
    )


def _p(value: object) -> str:
    return f"<p{_wrap_class(value)}>{_text(value)}</p>"


def _heading(value: str) -> str:
    return f"<h2>{_text(value)}</h2>"


def _table(name: str, headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    return (
        f'<div class="table" tabindex="0" role="region" aria-label="{_text(name)}"><table>'
        f"<caption{_wrap_class(name)}>{_text(name)}</caption><thead><tr>"
        + "".join(f'<th scope="col">{_text(h)}</th>' for h in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td{_wrap_class(v)}>{_text(v)}</td>" for v in row) + "</tr>"
            for row in rows
        )
        + "</tbody></table></div>"
    )
