"""T04r2 add-ons: lone surrogates, explicit scalar tags in the implicit forms, alias expansion."""

from __future__ import annotations

import pytest

from arci.descriptor import MAX_ALIAS_NODES, DescriptorError, compile_descriptor_text, parse_yaml

MOD = "tests.acceptance.fixture_agents"

SMALL = f"""
experiment_id: exp-yaml
toolset: {MOD}:make_world
oracle: {MOD}:oracle
baseline: {MOD}:good_agent
candidate: {MOD}:fragile_agent
conditions:
  - id: fetch_timeout
    fault: {{name: tool_timeout, tool: fetch, occurrence: 0}}
n_per_arm: 6
"""


def _where(text: str) -> str:
    with pytest.raises(DescriptorError) as caught:
        compile_descriptor_text(text, "arci.yaml")
    assert type(caught.value) is DescriptorError
    rendered = str(caught.value)
    assert "\n" not in rendered
    rendered.encode("utf-8")  # one printable line, whatever the file held
    return rendered.removeprefix("descriptor arci.yaml:")


# --- lone surrogates ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "path", "point"),
    [
        ('task: {x: "a\\ud800b"}\n', "task.x", "D800"),
        ('task: {x: [ok, "\\udfff"]}\n', "task.x[1]", "DFFF"),
        ('task: {"k\\udc00": 1}\n', 'task["k\\udc00"]', "DC00"),
        ('task: {x: "\\ud83d\\ude00"}\n', "task.x", "D83D"),  # YAML has no surrogate pairs
    ],
)
def test_lone_surrogates_are_rejected_at_their_path(extra: str, path: str, point: str) -> None:
    message = _where(SMALL + extra)
    assert message.startswith(f"{path}: lone surrogate U+{point} is not valid text"), message


def test_characters_outside_the_bmp_are_text() -> None:
    loaded = parse_yaml('x: "\\U0001F600 \U0001f600"\n')
    assert loaded == {"x": "\U0001f600 \U0001f600"}


# --- explicit !!int / !!float / !!null ----------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ('!!int "1_000"', 'invalid integer "1_000"'),
        ('!!int " 12"', 'invalid integer " 12"'),
        ('!!int "12 "', 'invalid integer "12 "'),
        ('!!int "0X1F"', 'invalid integer "0X1F"'),
        ('!!float "1_0.5"', 'invalid number "1_0.5"'),
        ('!!float " 1.5"', 'invalid number " 1.5"'),
        ('!!float "1e5"', 'invalid number "1e5"'),
        ('!!null "hello"', 'invalid null "hello"'),
        ("!!null hello", 'invalid null "hello"'),
        ("!!null NULL", 'invalid null "NULL"'),
    ],
)
def test_explicit_scalars_follow_the_implicit_forms(value: str, message: str) -> None:
    assert _where(SMALL + f"task: {{x: {value}}}\n").startswith(f"task.x: {message}")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('!!int "12"', 12),
        ("!!int 0x1F", 31),
        ('!!int "-7"', -7),
        ('!!float "1.5"', 1.5),
        ("!!float 2", 2.0),
        ('!!float ".25"', 0.25),
        ("!!null", None),
        ('!!null ""', None),
        ("!!null null", None),
        ("!!null ~", None),
        ("NULL", None),  # the implicit YAML 1.1 null forms are unchanged
        ("Null", None),
    ],
)
def test_explicit_scalars_in_the_implicit_forms_load(value: str, expected: object) -> None:
    loaded = parse_yaml(f"x: {value}\n")
    assert loaded == {"x": expected}
    assert type(loaded["x"] if isinstance(loaded, dict) else None) is type(expected)


# --- alias expansion cap ------------------------------------------------------------------------


def _laughs(levels: int) -> str:
    lines = ['a0: &a0 ["lol", "lol", "lol", "lol", "lol", "lol", "lol", "lol", "lol", "lol"]']
    for level in range(1, levels + 1):
        items = ", ".join([f"*a{level - 1}"] * 10)
        lines.append(f"a{level}: &a{level} [{items}]")
    return "\n".join(lines) + "\n"


def test_billion_laughs_is_refused_at_a_path() -> None:
    with pytest.raises(Exception) as caught:
        parse_yaml(_laughs(9))
    error = caught.value
    assert getattr(error, "message", "") == (
        f"aliases expand to more than {MAX_ALIAS_NODES} values; write less reuse"
    )
    path = getattr(error, "path", ())
    assert isinstance(path, tuple) and path


def test_billion_laughs_in_a_descriptor_is_one_line_with_a_path() -> None:
    nested = "".join(f"  {line}\n" for line in _laughs(9).splitlines())
    message = _where(SMALL + "task:\n" + nested)
    assert message.startswith("task.a")
    assert message.endswith(
        f"aliases expand to more than {MAX_ALIAS_NODES} values; write less reuse"
    )


def test_moderate_alias_reuse_loads() -> None:
    loaded = parse_yaml(_laughs(3))  # about 1 000 values re-used
    assert isinstance(loaded, dict)
    assert len(loaded) == 4


def test_a_large_document_without_aliases_is_not_capped() -> None:
    items = ", ".join(str(index) for index in range(MAX_ALIAS_NODES + 10))
    loaded = parse_yaml(f"x: [{items}]\n")
    assert isinstance(loaded, dict)
