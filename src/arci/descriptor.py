"""The `arci.yaml` experiment descriptor: a thin, declarative front end to `Manifest`.

A descriptor is deserialised into `Descriptor`, then compiled by `Descriptor.to_manifest()` into
the frozen `Manifest` and sealed with `Manifest.create`, exactly as a Python builder does. Keys are
the Manifest's field names; the few documented shorthands (`oracle`, condition `id`, fault `fault`
and `occurrence`, a bare-string arm) are expanded here and nowhere else. There is no decision logic
in this layer: every rule the Manifest enforces is enforced by the Manifest itself.

Pydantic is authoritative. `arci schema` prints `Descriptor.model_json_schema()` for editors; it
cannot express the cross-field rules (mutual exclusions, the experiment kind, decision faults), so
the model and field descriptions state them.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    JsonValue,
    Tag,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from arci.contracts import validate_contract
from arci.perturb import REGISTRY
from arci.schema import (
    N_PER_ARM_MAX,
    N_PER_ARM_MIN,
    AgentRef,
    ArmSpec,
    Bucket,
    Budgets,
    Condition,
    ContractSpec,
    DecisionSpec,
    FaultSpec,
    Manifest,
    McpServerSpec,
)

SCHEMA_TITLE = "ARCI experiment descriptor"
SCHEMA_ID = (
    "https://raw.githubusercontent.com/ajaysurya1221/agent-reliability-ci/"
    "v0.8.0/docs/schema/arci.schema.json"
)
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
DESCRIPTOR_SUFFIXES = (".yaml", ".yml")

# The frozen `module:function` pattern, read from the schema rather than restated.
REF_PATTERN: str = TypeAdapter(AgentRef).json_schema()["pattern"]
BUILT_IN_FAULTS: tuple[str, ...] = tuple(sorted(REGISTRY))

SourcePath = tuple[str | int, ...]


class DescriptorError(ValueError):
    """A descriptor that cannot be loaded, as one line: `descriptor <file>:<path>: <message>`.

    `path` is the source path inside the file, written with the keys the file used (aliases
    included) and zero-based indices, for example `conditions[0].fault.name`. An empty path means
    the file as a whole.
    """

    def __init__(self, message: str, path: SourcePath = (), source: str = "<descriptor>") -> None:
        self.message = message
        self.path = path
        self.source = source
        super().__init__(self._render())

    def _render(self) -> str:
        where = format_path(self.path)
        location = f"{self.source}:{where}" if where else self.source
        return _escape(f"descriptor {location}: {self.message}")

    def with_source(self, source: str) -> DescriptorError:
        return DescriptorError(self.message, self.path, source)


class _PathError(ValueError):
    """Raised inside a validator to report at a path below the model being validated."""

    def __init__(self, path: SourcePath, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(message)


def _quote(value: object) -> str:
    return json.dumps(value, ensure_ascii=False) if isinstance(value, str) else repr(value)


def _escape(text: str) -> str:
    """Keep a message on one line: control and other non-printable characters are escaped."""
    return "".join(ch if ch.isprintable() else json.dumps(ch)[1:-1] for ch in text)


_SIMPLE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def format_path(path: SourcePath) -> str:
    """`conditions[0].fault.name`; keys that are not plain words are quoted in brackets."""
    out = ""
    for segment in path:
        if isinstance(segment, bool):
            out += f"[{json.dumps(segment)}]"
        elif isinstance(segment, int):
            out += f"[{segment}]"
        elif _SIMPLE_KEY.match(segment):
            out += f".{segment}" if out else segment
        else:
            out += f"[{_quote(segment)}]"
    return out


# --- the three settled open items (plan/exec/decisions/E2-ruling.md) ----------------------------


def default_task_id(experiment_id: str) -> str:
    """Ruling 1: an omitted `task_id` is the experiment id (what `arci init` writes)."""
    return experiment_id


def bare_arm_label(ref: str) -> str:
    """Ruling 2: a bare-string arm `app.v1:run` is labelled `v1.run` (last module segment)."""
    module, _, function = ref.partition(":")
    return f"{module.rpartition('.')[2]}.{function}"


_STR_TAG = "tag:yaml.org,2002:str"
_INT_TAG = "tag:yaml.org,2002:int"
_FLOAT_TAG = "tag:yaml.org,2002:float"
_BOOL_TAG = "tag:yaml.org,2002:bool"
_NULL_TAG = "tag:yaml.org,2002:null"
_MAP_TAG = "tag:yaml.org,2002:map"
_SEQ_TAG = "tag:yaml.org,2002:seq"
_MERGE_TAG = "tag:yaml.org,2002:merge"
_YAML_PREFIX = "tag:yaml.org,2002:"
_SCALAR_TAGS = frozenset({_STR_TAG, _INT_TAG, _FLOAT_TAG, _BOOL_TAG, _NULL_TAG})
_DROPPED_TAGS = frozenset(
    {_BOOL_TAG, _INT_TAG, _FLOAT_TAG, "tag:yaml.org,2002:timestamp", "tag:yaml.org,2002:value"}
)
_INT_FORMS = (("0x", 16), ("0o", 8), ("0b", 2))
# Deepest nesting of mappings and lists (strict JSON validation itself stops at 200 levels).
MAX_DEPTH = 100
# Most values that alias re-uses may add to the document once expanded ("billion laughs").
MAX_ALIAS_NODES = 100_000

INT_PATTERN = r"^(?:[-+]?[0-9]+|0x[0-9a-fA-F]+|0o[0-7]+|0b[01]+)$"

# A float is written with a `.`: `1.5`, `-0.25`, `2.`, `.5`, `1.0e+3` (an exponent needs its
# sign, as in YAML 1.1). YAML 1.1's base-60 form (`1:30.5`) and underscores are dropped, so those
# stay strings; `.inf` and `.nan` resolve to floats only to be rejected as non-finite.
FLOAT_PATTERN = (
    r"^(?:[-+]?[0-9]+\.[0-9]*(?:[eE][-+][0-9]+)?|\.[0-9]+(?:[eE][-+][0-9]+)?"
    r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"
)


class DescriptorLoader(yaml.SafeLoader):
    """Ruling 3: a SafeLoader with its OWN resolver tables (the global SafeLoader is untouched).

    Booleans are only `true` and `false`; integers are decimal (`010` is 10), `0x`, `0o` or `0b`;
    floats follow `FLOAT_PATTERN`; timestamps stay strings. Null and merge keys are the
    SafeLoader's YAML 1.1 behaviour. `yes`, `no`, `on`, `off`, dates and `1:30.5` are therefore
    strings. `parse_yaml` also refuses every tag but str, int, float, bool, null, map and seq.
    Explicit `!!int` and `!!float` scalars must be written in the implicit forms (no underscores,
    no padding), and an explicit `!!null` only as an empty value, `null` or `~`.
    """

    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        # Scalars whose tag the file wrote (`!!null x`), by node identity; see `_check_scalar`.
        self.explicit: set[int] = set()

    def compose_scalar_node(self, anchor: dict[Any, yaml.Node]) -> yaml.ScalarNode:
        tag = self.peek_event().tag
        node = super().compose_scalar_node(anchor)
        if tag is not None and tag != "!":
            self.explicit.add(id(node))
        return node


DescriptorLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag not in _DROPPED_TAGS]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
DescriptorLoader.add_implicit_resolver(_BOOL_TAG, re.compile(r"^(?:true|false)$"), list("tf"))
DescriptorLoader.add_implicit_resolver(
    _INT_TAG,
    re.compile(INT_PATTERN),
    list("-+0123456789"),
)
DescriptorLoader.add_implicit_resolver(_FLOAT_TAG, re.compile(FLOAT_PATTERN), list("-+0123456789."))


def _too_large() -> str:
    limit = sys.get_int_max_str_digits()
    return f"integer too large to seal: more than {limit} decimal digits"


def _int_value(text: str) -> int:
    """An integer the seal can write: `json.dumps` refuses more than Python's digit limit.

    Only the implicit forms (`INT_PATTERN`), also under an explicit `!!int`: no underscores, no
    padding.
    """
    if not re.fullmatch(INT_PATTERN, text):
        raise ValueError(f"invalid integer {_quote(text)}")
    digits = text
    sign = -1 if digits.startswith("-") else 1
    digits = digits[1:] if digits[:1] in "+-" else digits
    base = next((b for prefix, b in _INT_FORMS if digits.startswith(prefix)), 10)
    body = digits[2:] if base != 10 else digits
    try:
        value = sign * int(body, base)
    except ValueError:
        if base == 10 and body.isascii() and body.isdigit():  # only the digit limit refuses it
            raise ValueError(_too_large()) from None
        raise ValueError(f"invalid integer {_quote(text)}") from None
    try:
        str(value)  # a 0x/0o/0b literal converts freely; writing it in decimal may not
    except ValueError:
        raise ValueError(_too_large()) from None
    return value


_NON_FINITE = {".inf": math.inf, "+.inf": math.inf, "-.inf": -math.inf, ".nan": math.nan}


def _float_value(text: str) -> float:
    """Only `FLOAT_PATTERN` or a decimal integer (`!!float 1`): no underscores, no padding."""
    if not re.fullmatch(FLOAT_PATTERN, text) and not re.fullmatch(r"[-+]?[0-9]+", text):
        try:
            spelled = float(text)  # `!!float inf`: reported as non-finite by `_check_scalar`
        except ValueError:
            spelled = 0.0
        if math.isfinite(spelled):
            raise ValueError(f"invalid number {_quote(text)}")
        return spelled
    lowered = text.lower()
    try:
        return _NON_FINITE[lowered] if lowered in _NON_FINITE else float(lowered)
    except ValueError:
        raise ValueError(f"invalid number {_quote(text)}") from None


def _bool_value(text: str) -> bool:
    if text in ("true", "false"):
        return text == "true"
    raise ValueError(f"invalid boolean {_quote(text)}; write true or false")


_SCALAR_VALUES: dict[str, Callable[[str], object]] = {
    _INT_TAG: _int_value,
    _FLOAT_TAG: _float_value,
    _BOOL_TAG: _bool_value,
}


def _constructor(
    convert: Callable[[str], object],
) -> Callable[[yaml.SafeLoader, yaml.ScalarNode], object]:
    def construct(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> object:
        try:
            return convert(str(loader.construct_scalar(node)))
        except ValueError as exc:
            raise yaml.constructor.ConstructorError(None, None, str(exc), node.start_mark) from None

    return construct


for _tag, _convert in _SCALAR_VALUES.items():
    DescriptorLoader.add_constructor(_tag, _constructor(_convert))


class _SourceError(yaml.YAMLError):
    """A problem the YAML layer finds at a source path (PyYAML itself would accept it)."""

    def __init__(self, path: SourcePath, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(message)


def _short_tag(tag: str) -> str:
    return "!!" + tag.removeprefix(_YAML_PREFIX) if tag.startswith(_YAML_PREFIX) else tag


def _check_tag(node: yaml.Node, path: SourcePath) -> None:
    """Only JSON shapes: plain mappings, lists and scalars. `!!set`, `!!omap`, `!!pairs`,
    `!!binary`, `!!timestamp` and every custom tag are refused before anything is built."""
    if isinstance(node, yaml.ScalarNode):
        allowed = node.tag in _SCALAR_TAGS
    elif isinstance(node, yaml.MappingNode):
        allowed = node.tag == _MAP_TAG
    else:
        allowed = node.tag == _SEQ_TAG
    if not allowed:
        raise _SourceError(
            path,
            f"not a JSON value: YAML tag {_short_tag(node.tag)} is not allowed; use a mapping, "
            "a list, a number, true/false, null or a quoted string",
        )


_SURROGATE = re.compile("[\ud800-\udfff]")
_EXPLICIT_NULLS = frozenset({"", "null", "~"})


def _check_text(text: str, path: SourcePath) -> None:
    """A lone surrogate (from a `\\uD800` escape) is not text JSON or UTF-8 can carry."""
    found = _SURROGATE.search(text)
    if found:
        raise _SourceError(
            path,
            f"lone surrogate U+{ord(found.group()):04X} is not valid text; write the character "
            "itself or a \\U escape of its code point",
        )


def _check_scalar(loader: DescriptorLoader, node: yaml.ScalarNode, path: SourcePath) -> None:
    value_text = str(node.value)
    _check_text(value_text, path)
    if node.tag == _NULL_TAG and id(node) in loader.explicit:
        if value_text not in _EXPLICIT_NULLS:
            raise _SourceError(path, f"invalid null {_quote(value_text)}; write null, ~ or nothing")
        return
    convert = _SCALAR_VALUES.get(node.tag)
    if convert is None:
        return
    try:
        value = convert(str(node.value))
    except ValueError as exc:
        raise _SourceError(path, str(exc)) from None
    if isinstance(value, float) and not math.isfinite(value):
        raise _SourceError(path, f"not a finite number: {node.value}; JSON has no NaN or infinity")


def _check_key(loader: DescriptorLoader, key_node: yaml.Node, path: SourcePath) -> str:
    if not isinstance(key_node, yaml.ScalarNode) or key_node.tag != _STR_TAG:
        shown = key_node.value if isinstance(key_node, yaml.ScalarNode) else "a collection"
        raise _SourceError(path, f"key {shown} is not a string; quote it")
    key = str(loader.construct_scalar(key_node))
    _check_text(key, (*path, key))
    return key


@dataclass
class _Walk:
    """`_check_node`'s state: the nodes being walked, and per node its height and expanded size."""

    active: set[int] = field(default_factory=set[int])
    heights: dict[int, int] = field(default_factory=dict[int, int])
    sizes: dict[int, int] = field(default_factory=dict[int, int])
    reused: int = 0  # values that alias re-use has added so far


def _check_node(loader: DescriptorLoader, node: yaml.Node, path: SourcePath, walk: _Walk) -> int:
    """Walk the composed node graph before anything is constructed; the first problem raises.

    Problems: a tag that is not plain JSON (`_check_tag`), a malformed or non-finite number or
    boolean, an explicit `!!null` with a value, a lone surrogate in a string or key, a non-string
    key, a repeated key, a self-referencing alias, nesting deeper than `MAX_DEPTH`, more than
    `MAX_ALIAS_NODES` values added by re-using aliased nodes.

    Keys a merge key (`<<`) brings in may be overridden by an explicit key, as YAML
    intends, and `<<: [*a, *b]` merges several mappings; but `<<` itself given twice in ONE
    mapping is a repeated key like any other.

    Returns the node's height (levels of nesting below it; a scalar or an empty collection is 0).
    A node reached twice through an alias is walked once and its height cached by node identity;
    every later use still checks that its own path plus that height stays within `MAX_DEPTH`, so a
    chain of shared aliases cannot nest deeper than the limit. Each such use also adds the node's
    expanded size (values below it, itself included) to `walk.reused`, which may not pass
    `MAX_ALIAS_NODES`.
    """
    if id(node) in walk.active:
        raise _SourceError(path, "a YAML alias contains itself; recursive values are not JSON")
    known = walk.heights.get(id(node))
    if known is not None:
        if len(path) + known > MAX_DEPTH:
            raise _SourceError(path, f"nested more than {MAX_DEPTH} levels deep")
        walk.reused += walk.sizes[id(node)]
        if walk.reused > MAX_ALIAS_NODES:
            raise _SourceError(
                path, f"aliases expand to more than {MAX_ALIAS_NODES} values; write less reuse"
            )
        return known
    if len(path) > MAX_DEPTH:
        raise _SourceError(path, f"nested more than {MAX_DEPTH} levels deep")
    _check_tag(node, path)
    walk.active.add(id(node))
    height = 0
    size = 1
    if isinstance(node, yaml.ScalarNode):
        _check_scalar(loader, node, path)
    elif isinstance(node, yaml.MappingNode):
        keys: set[str] = set()
        merged = False
        for key_node, value_node in cast(list[tuple[yaml.Node, yaml.Node]], node.value):
            if key_node.tag == _MERGE_TAG:
                if merged:
                    mark = key_node.start_mark
                    raise _SourceError(
                        path,
                        f"duplicate merge key {_quote('<<')} at line {mark.line + 1}, column "
                        f"{mark.column + 1}; merge several mappings with <<: [*a, *b]",
                    )
                merged = True
                height = max(height, _check_node(loader, value_node, path, walk))
                size += walk.sizes[id(value_node)]
                continue
            key = _check_key(loader, key_node, path)
            if key in keys:
                mark = key_node.start_mark
                raise _SourceError(
                    (*path, key),
                    f"duplicate key {_quote(key)} at line {mark.line + 1}, column "
                    f"{mark.column + 1}; give each key once",
                )
            keys.add(key)
            below = _check_node(loader, value_node, (*path, key), walk)
            height = max(height, 1 + below)
            size += 1 + walk.sizes[id(value_node)]  # the key and its value
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(cast(list[yaml.Node], node.value)):
            height = max(height, 1 + _check_node(loader, item, (*path, index), walk))
            size += walk.sizes[id(item)]
    walk.active.discard(id(node))
    walk.heights[id(node)] = height
    walk.sizes[id(node)] = size
    return height


def parse_yaml(text: str) -> object:
    """Ruling 3: one YAML document through `DescriptorLoader`, checked by `_check_node` first.

    What comes back is plain JSON: dicts with string keys, lists, strings, ints, finite floats,
    booleans and None, with no cycles. Raises `yaml.YAMLError` (a `_SourceError` with a path for
    the checks above).
    """
    loader = DescriptorLoader(text)  # a SafeLoader subclass: safe
    try:
        node = loader.get_single_node()
        if node is None:
            return None
        _check_node(loader, node, (), _Walk())
        return loader.construct_document(node)
    except RecursionError:
        raise _SourceError((), f"nested more than {MAX_DEPTH} levels deep") from None
    finally:
        loader.dispose()


# --- the shorthand rules -----------------------------------------------------------------------
# One function per model, over the keys the input gave: the models' after-validators apply them to
# a validated model, and `shorthand_problems` applies them to the raw input, so that a conflict is
# reported together with the field errors (see `loads_descriptor`).

Problem = tuple[SourcePath, str]


def _both(alias: str, name: str) -> str:
    return f"{_quote(alias)} and {_quote(name)} are the same key; give one, not both"


def _fault_rule(given: Mapping[str, object]) -> list[Problem]:
    if "occurrence" in given and "at_occurrence" in given:
        return [(("occurrence",), _both("occurrence", "at_occurrence"))]
    return []


def _condition_rule(given: Mapping[str, object]) -> list[Problem]:
    """Both independent rules are checked: the condition id, and `fault`/`faults`."""
    found: list[Problem] = []
    if "id" in given and "condition_id" in given:
        found.append((("id",), _both("id", "condition_id")))
    elif "id" not in given and "condition_id" not in given:
        found.append((("id",), 'missing required key "id" (or "condition_id")'))
    else:
        key = "id" if "id" in given else "condition_id"
        if given[key] is None:
            found.append(((key,), "must be a string"))
    if "fault" in given and "faults" in given:
        found.append((("fault",), '"fault" and "faults" both given; give one, not both'))
    elif "fault" in given and given["fault"] is None:
        found.append((("fault",), "must be a mapping; omit it for a clean condition"))
    return found


def _contract_rule(given: Mapping[str, object]) -> list[Problem]:
    if "oracle" in given and "contract" in given:
        return [(("oracle",), '"oracle" and "contract" both given; give one, not both')]
    if "oracle" not in given and "contract" not in given:
        return [(("oracle",), 'missing required key "oracle" (or "contract")')]
    key = "oracle" if "oracle" in given else "contract"
    if given[key] is None:
        return [((key,), "must not be null")]
    return []


def _given(model: BaseModel) -> dict[str, object]:
    return {name: getattr(model, name) for name in model.model_fields_set}


def _raise(problems: Sequence[Problem]) -> None:
    if problems:
        raise _PathError(*first_problem(problems))


def _mapping(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _items(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def shorthand_problems(data: Mapping[str, object]) -> list[Problem]:
    """Every alias conflict and one-of rule broken anywhere in the raw input, with its path."""
    found: list[Problem] = []

    def check(
        rule: Callable[[Mapping[str, object]], list[Problem]], at: SourcePath, value: object
    ) -> None:
        given = _mapping(value)
        for path, message in rule(given) if given is not None else []:
            found.append(((*at, *path), message))

    check(_contract_rule, (), data)
    for index, condition in enumerate(_items(data.get("conditions"))):
        at: SourcePath = ("conditions", index)
        check(_condition_rule, at, condition)
        given = _mapping(condition) or {}
        check(_fault_rule, (*at, "fault"), given.get("fault"))
        for position, fault in enumerate(_items(given.get("faults"))):
            check(_fault_rule, (*at, "faults", position), fault)
    return found


# --- the models -------------------------------------------------------------------------------


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _not_null(schema: dict[str, Any]) -> None:
    """Schema of an optional key that, when present, must not be null."""
    options = [option for option in schema.pop("anyOf", []) if option.get("type") != "null"]
    schema.pop("default", None)
    if len(options) == 1:
        schema.update(options[0])
    else:
        schema["anyOf"] = options


class DescriptorFault(_Model):
    """One injected fault, compiled to a `FaultSpec`.

    Shorthands: `bucket` may be omitted (it means `falsify`); `occurrence` is an alias of
    `at_occurrence`, and the two may not both be given, even with equal values. Decision faults
    (`decision_low_confidence`, `decision_unavailable`) need top-level `decisions` and
    `tool: decision:systemone`; `decision_low_confidence` accepts only the param `confidence_max`
    (a number in [0, 1]) and `decision_unavailable` accepts none.
    """

    name: str = Field(
        description=(
            "A built-in fault (" + ", ".join(BUILT_IN_FAULTS) + ") or a custom factory "
            "`module:function` (checked for syntax only; imported in the trial process)."
        )
    )
    bucket: Bucket = Field(
        default=Bucket.FALSIFY,
        description="falsify (default): a robust agent should still succeed; benign: must not "
        "change the outcome; ceiling: known unrecoverable, reported and never gated.",
    )
    tool: str | None = Field(default=None, description="Tool to target; null means any tool.")
    occurrence: int | None = Field(
        default=None,
        ge=0,
        description="Alias of `at_occurrence` (give one, not both). Zero-based call count of "
        "`tool`; null means the fault's default.",
    )
    at_occurrence: int | None = Field(
        default=None, ge=0, description="Zero-based call count of `tool`; alias `occurrence`."
    )
    params: dict[str, JsonValue] = Field(
        default_factory=dict, description="Fault parameters, for example `confidence_max`."
    )

    @field_validator("name")
    @classmethod
    def _known_fault(cls, name: str) -> str:
        if name in REGISTRY or re.fullmatch(REF_PATTERN, name):
            return name
        raise ValueError(
            f"unknown fault {_quote(name)}; expected one of {', '.join(BUILT_IN_FAULTS)} "
            "or module:function"
        )

    @model_validator(mode="after")
    def _one_occurrence_key(self) -> Self:
        _raise(_fault_rule(_given(self)))
        return self

    def to_fault_spec(self) -> FaultSpec:
        given = "occurrence" in self.model_fields_set
        return FaultSpec(
            name=self.name,
            bucket=self.bucket,
            tool=self.tool,
            at_occurrence=self.occurrence if given else self.at_occurrence,
            params=dict(self.params),
        )


class DescriptorCondition(_Model):
    """One condition, compiled to a `Condition`.

    Give exactly one of `id` and `condition_id` (the same key). Give at most one of `fault` (one
    mapping) and `faults` (a list, applied in order); a clean condition gives neither.
    """

    id: str | None = Field(
        default=None,
        description="Alias of `condition_id`; exactly one of the two.",
        json_schema_extra=_not_null,
    )
    condition_id: str | None = Field(
        default=None,
        description="Condition name; alias `id`; exactly one of the two.",
        json_schema_extra=_not_null,
    )
    fault: DescriptorFault | None = Field(
        default=None,
        description="One fault; shorthand for a one-element `faults`; not with `faults`.",
        json_schema_extra=_not_null,
    )
    faults: tuple[DescriptorFault, ...] = Field(
        default=(), description="Faults applied together, in order; not with `fault`."
    )

    @model_validator(mode="after")
    def _one_of_each(self) -> Self:
        _raise(_condition_rule(_given(self)))
        return self

    def to_condition(self) -> Condition:
        faults = (self.fault,) if self.fault is not None else self.faults
        return Condition(
            condition_id=self.id if self.id is not None else str(self.condition_id),
            faults=tuple(fault.to_fault_spec() for fault in faults),
        )


_REF_TAG = "module:function"
_ARM_TAG = "arm mapping"


def _arm_kind(value: Any) -> str:
    return _REF_TAG if isinstance(value, str) else _ARM_TAG


Arm = Annotated[
    Annotated[AgentRef, Tag(_REF_TAG)] | Annotated[ArmSpec, Tag(_ARM_TAG)],
    Discriminator(_arm_kind),
]

_ARM_HELP = (
    "A python agent as a bare `module:function` string (label `<last module "
    "segment>.<function>`, empty candidate_id), or a mapping with `label`, exactly one of "
    "`agent` (module:function) or `command` (a CommandSpec), and optional `candidate_id`. Both "
    "arms are python agents (top-level `toolset`, no `mcp_server`) or both commands "
    "(`mcp_server`, no `toolset`)."
)


class Descriptor(_Model):
    """An ARCI experiment (`arci.yaml`), compiled into a sealed `Manifest` before any trial runs.

    Keys are the Manifest's field names. Shorthands: top-level `oracle` stands for
    `contract: {oracle: ...}` (give exactly one of `oracle` and `contract`); an arm may be a bare
    `module:function`; a condition may use `id` for `condition_id` and `fault` for a one-element
    `faults`; a fault may use `occurrence` for `at_occurrence` and omit `bucket` (falsify). An
    alias and its full key may never both be given. Unknown keys are errors everywhere, including
    `schema_version`, `record_sha256` and `created_at`, which the loader and sealer own. Python
    experiments need `toolset` and no `mcp_server`; command experiments need `mcp_server` and no
    `toolset`; `decisions` needs command arms. Placeholders such as `{workdir}` stay literal.
    This schema cannot express the cross-field rules; the pydantic models are authoritative.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title=SCHEMA_TITLE,
        json_schema_extra={"$id": SCHEMA_ID, "$schema": SCHEMA_DIALECT},
    )

    experiment_id: str = Field(description="Names the experiment and its run directory.")
    task_id: str | None = Field(
        default=None, description="Task name; omitted or null means the experiment_id."
    )
    task: dict[str, JsonValue] = Field(
        default_factory=dict, description="The task handed to every trial (any JSON object)."
    )
    toolset: AgentRef | None = Field(
        default=None,
        description="Python experiments: `module:function` (task, seed) -> object with `.tools` "
        "and `.snapshot()`. Not with `mcp_server`.",
    )
    mcp_server: McpServerSpec | None = Field(
        default=None,
        description="Command experiments: the environment as one stdio MCP server. Not with "
        "`toolset`.",
    )
    decisions: DecisionSpec | None = Field(
        default=None,
        description="Command experiments only: a System One decision endpoint. A `fixture` "
        "is required exactly when upstream is `fixture`.",
    )
    oracle: AgentRef | None = Field(
        default=None,
        description="Shorthand for `contract: {oracle: ...}`; give exactly one of `oracle` and "
        "`contract`.",
        json_schema_extra=_not_null,
    )
    contract: ContractSpec | None = Field(
        default=None,
        description="The behaviour contract, including its `oracle`; give exactly one of "
        "`oracle` and `contract`. A non-empty `unobservable` is rejected.",
        json_schema_extra=_not_null,
    )
    baseline: Arm = Field(description=_ARM_HELP)
    candidate: Arm = Field(description=_ARM_HELP)
    conditions: tuple[DescriptorCondition, ...] = Field(
        min_length=1, description="At least one condition; each runs n_per_arm pairs."
    )
    alpha: float = Field(default=0.05, ge=1e-6, le=0.5, description="Family-wise error rate.")
    delta: float = Field(
        default=0.10, gt=0, lt=1, description="Largest tolerated drop in success rate."
    )
    n_per_arm: int = Field(
        default=200, ge=N_PER_ARM_MIN, le=N_PER_ARM_MAX, description="Trials per arm per condition."
    )
    interval_method: Literal["clopper_pearson", "newcombe"] = Field(
        default="clopper_pearson", description="How the bounds on the rate difference are formed."
    )
    looks: tuple[int, ...] = Field(
        default=(),
        description="Group-sequential looks: strictly increasing, the last equal to n_per_arm; "
        "empty means one look at n_per_arm.",
    )
    base_seed: int = Field(default=0, description="Seed from which every trial seed derives.")
    budgets: Budgets = Field(default_factory=Budgets, description="Per-trial budgets.")
    fixtures_sha256: str = Field(
        default="", description="Opaque value sealed into the manifest; never computed."
    )
    prior_runs: tuple[str, ...] = Field(
        default=(), description="Every earlier experiment on the same candidate_id."
    )

    @model_validator(mode="after")
    def _one_contract(self) -> Self:
        _raise(_contract_rule(_given(self)))
        if self.contract is not None:
            try:
                validate_contract(self.contract)
            except ValueError as exc:
                raise _PathError(("contract", "unobservable"), str(exc)) from None
        return self

    def contract_spec(self) -> ContractSpec:
        if self.contract is not None:
            return self.contract
        return ContractSpec(oracle=str(self.oracle))

    def to_manifest(self) -> Manifest:
        """Compile and seal. `created_at` is "", as the Python builders leave it."""
        try:
            return Manifest.create(
                experiment_id=self.experiment_id,
                created_at="",
                task_id=default_task_id(self.experiment_id)
                if self.task_id is None
                else self.task_id,
                task=dict(self.task),
                toolset=self.toolset,
                mcp_server=self.mcp_server,
                decisions=self.decisions,
                contract=self.contract_spec(),
                baseline=_arm(self.baseline),
                candidate=_arm(self.candidate),
                conditions=tuple(condition.to_condition() for condition in self.conditions),
                alpha=self.alpha,
                delta=self.delta,
                n_per_arm=self.n_per_arm,
                interval_method=self.interval_method,
                looks=self.looks,
                base_seed=self.base_seed,
                budgets=self.budgets,
                fixtures_sha256=self.fixtures_sha256,
                prior_runs=self.prior_runs,
            )
        except ValidationError as exc:
            path, message = first_problem(validation_problems(exc, None))
            raise DescriptorError(message, path) from None
        except (ValueError, TypeError, RecursionError) as exc:  # e.g. what hash_record refuses
            raise DescriptorError(f"cannot seal the manifest: {exc}") from None


def _arm(value: str | ArmSpec) -> ArmSpec:
    if isinstance(value, ArmSpec):
        return value
    return ArmSpec(label=bare_arm_label(value), agent=value, candidate_id="")


# --- errors -----------------------------------------------------------------------------------


def _has(node: object, segment: str | int) -> bool:
    if isinstance(node, dict):
        return segment in node
    return isinstance(node, list) and isinstance(segment, int) and 0 <= segment < len(node)


_ARM_FIELDS = frozenset({"baseline", "candidate"})
_ARM_TAGS = frozenset({_REF_TAG, _ARM_TAG})


def _json_root(path: SourcePath) -> bool:
    """`task` and a fault's `params` are `dict[str, JsonValue]`; below them every value is JSON."""
    return path == ("task",) or (len(path) > 2 and path[0] == "conditions" and path[-1] == "params")


def _json_tag(node: object) -> str | None:
    return "dict" if isinstance(node, dict) else "list" if isinstance(node, list) else None


def source_path(loc: Sequence[str | int], data: object, keep_last: bool = False) -> SourcePath:
    """Map a pydantic `loc` onto the input by walking `data` key by key and index by index.

    Pydantic adds synthetic segments that are not keys: the arm union's tag right after
    `baseline`/`candidate` (`module:function` or `arm mapping`), and, below `task` and `params`,
    a `dict`/`list` tag after every JSON container. Those positions are known from the models, so
    a user key spelled like a tag is still a key. Other segments the input lacks (`[key]`) are
    dropped; with `keep_last` the last one (a missing key) is kept.
    """
    path: list[str | int] = []
    node: Any = data
    arm_tag = False  # the next segment is the arm union's tag
    json_tag = False  # the next segment is a JsonValue container tag
    in_json = False
    for index, segment in enumerate(loc):
        if arm_tag and segment in _ARM_TAGS:
            arm_tag = False
            continue
        if json_tag and segment == _json_tag(node):
            json_tag = False
            continue
        arm_tag = json_tag = False
        if _has(node, segment):
            path.append(segment)
            node = node[segment]
            arm_tag = len(path) == 1 and segment in _ARM_FIELDS
            json_tag = in_json
            in_json = in_json or _json_root(tuple(path))
        elif keep_last and index == len(loc) - 1:
            path.append(segment)
    return tuple(path)


_TYPE_ERRORS = frozenset({"int_type", "float_type", "bool_type", "string_type"})


def _message(error: Any) -> str:
    kind: str = error["type"]
    loc: tuple[str | int, ...] = error["loc"]
    context: dict[str, Any] = error.get("ctx") or {}
    if kind == "extra_forbidden":
        return f"unknown key {_quote(loc[-1])}"
    if kind == "missing":
        return f"missing required key {_quote(loc[-1])}"
    if kind == "string_pattern_mismatch" and context.get("pattern") == REF_PATTERN:
        return f"invalid reference {_quote(error['input'])}; expected module:function"
    if kind == "invalid-json-value":
        return "not a JSON value (dates, binary and sets are not JSON; quote the value)"
    if kind in {"model_type", "model_attributes_type", "dict_type"}:
        return "must be a mapping"
    if kind in _TYPE_ERRORS:
        # Strict: a quoted number is a string and true/false are not numbers.
        return f"{error['msg']}, got {json.dumps(error['input'], ensure_ascii=False)}"
    if kind == "value_error" and "error" in context:
        return str(context["error"])
    return str(error["msg"])


def _sort_key(path: SourcePath) -> tuple[tuple[int, int, str], ...]:
    return tuple((0, s, "") if isinstance(s, int) else (1, 0, str(s)) for s in path)


def validation_problems(exc: ValidationError, data: object) -> list[Problem]:
    """Every pydantic error as (source path, message); `data` None keeps the model's own loc."""
    found: list[tuple[SourcePath, str, str]] = []
    for error in exc.errors():
        if data is None:
            path: SourcePath = tuple(error["loc"])
        else:
            path = source_path(error["loc"], data, keep_last=error["type"] == "missing")
        cause = (error.get("ctx") or {}).get("error")
        if isinstance(cause, _PathError):
            found.append(((*path, *cause.path), cause.message, error["type"]))
        else:
            found.append((path, _message(error), error["type"]))
    # A list whose items failed is also reported as too short; the item error is the cause.
    return [
        (path, message)
        for path, message, kind in found
        if kind != "too_short"
        or not any(len(other[0]) > len(path) and other[0][: len(path)] == path for other in found)
    ]


def first_problem(problems: Sequence[Problem]) -> Problem:
    """The reported error: the first by SORTED source path (indices numerically), not file order."""
    return min(problems, key=lambda item: (_sort_key(item[0]), item[1]))


# --- loading ----------------------------------------------------------------------------------


def is_descriptor_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in DESCRIPTOR_SUFFIXES


def loads_descriptor(text: str, source: str = "<descriptor>") -> Descriptor:
    """Parse one YAML document and validate it. Raises `DescriptorError`."""
    try:
        data = parse_yaml(text)
    except _SourceError as exc:
        raise DescriptorError(exc.message, exc.path, source) from None
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise DescriptorError(f"invalid YAML{where}: {exc.problem}", (), source) from None
    except yaml.YAMLError as exc:
        raise DescriptorError(f"invalid YAML: {exc}", (), source) from None
    except (ValueError, TypeError, RecursionError) as exc:  # defence in depth: never bare
        raise DescriptorError(f"invalid YAML: {exc}", (), source) from None
    if not isinstance(data, dict):
        kind = "empty" if data is None else type(data).__name__
        raise DescriptorError(f"must be one YAML mapping, got {kind}", (), source)
    return _validate(cast(dict[str, object], data), source)


def _validate(data: dict[str, object], source: str) -> Descriptor:
    """Strict JSON validation; every problem is collected and the first by sorted path raised.

    The input is parsed JSON (see `parse_yaml`), validated in pydantic's strict JSON mode: lists
    become tuples and strings become enum members as in JSON, but true/false never become numbers
    and a quoted number is never a number, at every level. The shorthand rules are checked on the
    raw input too, so that, for example, `oracle` with `contract` is reported even when an
    unknown key elsewhere stops the after-validators from running.
    """
    problems = shorthand_problems(data)
    try:
        text = json.dumps(data, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:  # parse_yaml already refuses these
        raise DescriptorError(f"not a JSON value: {exc}", (), source) from None
    try:
        descriptor = Descriptor.model_validate_json(text, strict=True)
    except ValidationError as exc:
        problems += validation_problems(exc, data)
    else:
        if not problems:
            return descriptor
    path, message = first_problem(problems)
    raise DescriptorError(message, path, source)


def load_descriptor(path: str | Path) -> Descriptor:
    source = str(path)
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        detail = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        raise DescriptorError(f"cannot read: {detail}", (), source) from None
    return loads_descriptor(text, source)


def compile_descriptor_text(text: str, source: str = "<descriptor>") -> Manifest:
    """`compile_descriptor` for text already in memory."""
    descriptor = loads_descriptor(text, source)
    try:
        return descriptor.to_manifest()
    except DescriptorError as exc:
        raise exc.with_source(source) from None


def compile_descriptor(path: str | Path) -> Manifest:
    """Load `arci.yaml`, compile it and seal it: the manifest `arci run` executes."""
    descriptor = load_descriptor(path)
    try:
        return descriptor.to_manifest()
    except DescriptorError as exc:
        raise exc.with_source(str(path)) from None


def descriptor_schema() -> dict[str, Any]:
    return Descriptor.model_json_schema()


def render_schema() -> str:
    """The bytes of `arci schema` and docs/schema/arci.schema.json."""
    return json.dumps(descriptor_schema(), indent=2, sort_keys=True) + "\n"
