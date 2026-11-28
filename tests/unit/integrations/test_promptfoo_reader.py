"""ADR 0020 A1-A3. Expected identities and outcomes come from the original JSON."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from arci.importers.promptfoo import PromptfooError, read, task_id

REAL = Path(__file__).parent / "real" / "promptfoo"
OLD = Path(__file__).parents[1] / "outcomes" / "real" / "promptfoo"
FILES = sorted(
    p
    for root in (REAL, OLD)
    for p in root.glob("*.json")
    if p.name not in {"shapes.json", "cache-warm.json"}
)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def raw_rows(
    doc: dict[str, Any], prompt: int | None = None, provider: str | None = None
) -> list[tuple[int | None, str, str]]:
    expected: list[tuple[int | None, str, str]] = []
    for r in doc["results"]["results"]:
        if prompt is not None and r["promptIdx"] != prompt:
            continue
        if provider is not None and r["provider"].get("label", r["provider"]["id"]) != provider:
            continue
        case = r["testCase"]
        desc = case.get("description")
        digest = hashlib.sha256(canonical({"description": desc, "vars": case.get("vars") or {}}))
        key = (desc or "test")[:80] + " #" + digest.hexdigest()[:16]
        result = "error" if r["failureReason"] == 2 else "pass" if r["success"] else "fail"
        index = r.get("repeatIndex")
        expected.append((None if index is None else 1 + index, key, result))
    return expected


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_a01_all_real_rows_and_whole_file_stats(path: Path) -> None:
    raw = path.read_bytes()
    doc = json.loads(raw)
    cells = sorted(
        {
            (r["promptIdx"], r["provider"].get("label", r["provider"]["id"]))
            for r in doc["results"]["results"]
        }
    )
    count: Counter[str] = Counter()
    for prompt, provider in cells:
        parsed = read(raw, prompt=prompt if len(cells) > 1 else None)
        assert parsed.cells == tuple(cells)
        assert parsed.selected_cell == (prompt, provider)
        assert [(r.round, r.task_id, r.outcome) for r in parsed.rows] == raw_rows(
            doc, prompt, provider
        )
        count.update(r.outcome for r in parsed.rows)
        assert parsed.cache is doc["runtimeOptions"].get("cache")
        assert parsed.tool_version == doc["metadata"]["promptfooVersion"]
        assert parsed.run_id == doc["evalId"]
        assert parsed.run_time == doc["results"]["timestamp"]
    stats = doc["results"]["stats"]
    assert (count["pass"], count["fail"], count["error"]) == (
        stats["successes"],
        stats["failures"],
        stats["errors"],
    )


def test_a02_stable_across_versions_arms_repeats_and_row_order() -> None:
    expected = {
        key for _, key, _ in raw_rows(json.loads((REAL / "words-single.json").read_bytes()))
    }
    for path in [*REAL.glob("words-*.json"), *OLD.glob("*.json")]:
        original = path.read_bytes()
        doc = json.loads(original)
        original_ids = [key for _, key, _ in raw_rows(doc)]
        doc["results"]["results"].reverse()
        reordered = json.dumps(doc).encode()
        for raw, ids in ((original, original_ids), (reordered, original_ids[::-1])):
            rows = read(raw).rows
            assert [row.task_id for row in rows] == ids
            rounds: dict[int | None, list[str]] = defaultdict(list)
            for row in rows:
                rounds[row.round].append(row.task_id)
            for tasks in rounds.values():
                assert len(tasks) == len(expected) and set(tasks) == expected


def test_a02_vars_key_order() -> None:
    # The multi-key cases are in shapes.json, which also contains a deliberate duplicate.
    doc = json.loads((REAL / "shapes.json").read_bytes())
    expected = [key for _, key, _ in raw_rows(doc)]
    cases = [r["testCase"] for r in doc["results"]["results"]]
    assert [task_id(case) for case in cases] == expected
    for case in cases:
        variables = case["vars"]
        assert len(variables) > 1
        case["vars"] = dict(reversed(variables.items()))
    assert [task_id(case) for case in cases] == expected


@dataclass(frozen=True)
class Refusal:
    name: str
    reason: str
    file: str = "words-single"
    field: str = ""
    value: Any = None
    prompt: int | None = None

    def source(self) -> bytes:
        raw = (REAL / f"{self.file}.json").read_bytes()
        if self.name == "duplicate JSON key":
            return raw.replace(b'"evalId":', b'"evalId":null,"evalId":', 1)
        if self.name == "invalid JSON":
            return raw[:-10]
        if self.name == "not an object":
            return b"[" + raw + b"]"
        if self.name == "infinite exponent":
            return raw.replace(b'"promptIdx": 0', b'"promptIdx": 1e400', 1)
        if not self.field:
            return raw
        doc = json.loads(raw)
        current = doc
        *parents, field = self.field.split(".")
        for part in parents:
            if isinstance(current, list):
                current = current[int(part)]
            else:
                current = current.setdefault(part, {})
        if self.name == "missing testCase":
            del current[field]
        else:
            current[field] = self.value
        return json.dumps(doc).encode()


ROW = "results.results.0."
REFUSALS = [
    Refusal("not an object", "input must be a JSON object"),
    Refusal("invalid JSON", "input is not valid UTF-8 JSON"),
    Refusal("duplicate JSON key", "duplicate JSON key"),
    Refusal("infinite exponent", "non-finite JSON number"),
    Refusal("lone surrogate", "lone surrogate", field="evalId", value="\udfff"),
    Refusal("version", "results.version", field="results.version", value=2),
    Refusal("missing testCase", "testCase must be a JSON object", field=ROW + "testCase"),
    Refusal("vars array", "testCase.vars", field=ROW + "testCase.vars", value=[]),
    Refusal(
        "description number", "testCase.description", field=ROW + "testCase.description", value=1
    ),
    Refusal("success number", "success must be a boolean", field=ROW + "success", value=1),
    Refusal("prompt bool", "promptIdx must be an integer", field=ROW + "promptIdx", value=False),
    Refusal("prompt float", "promptIdx must be an integer", field=ROW + "promptIdx", value=0.0),
    Refusal(
        "reason bool", "failureReason must be an integer", field=ROW + "failureReason", value=False
    ),
    Refusal(
        "reason float", "failureReason must be an integer", field=ROW + "failureReason", value=0.0
    ),
    Refusal(
        "reason unknown", "failureReason must be an integer", field=ROW + "failureReason", value=3
    ),
    Refusal(
        "0 with false", "failureReason contradicts success", field=ROW + "success", value=False
    ),
    Refusal(
        "1 with true", "failureReason contradicts success", field=ROW + "failureReason", value=1
    ),
    Refusal(
        "2 with true", "failureReason contradicts success", field=ROW + "failureReason", value=2
    ),
    *(
        Refusal(
            k,
            "whole-file recount differs from results.stats." + k,
            "two-prompts",
            "results.stats." + k,
            -1,
            prompt=1,
        )
        for k in ("successes", "failures", "errors")
    ),
    Refusal("actual cache hits", "cache use reported", "cache-warm"),
    Refusal("stats hits", "results.stats.cacheHits", field="results.stats.cacheHits", value=1),
    Refusal(
        "cached row", "response.cached", "two-providers", ROW + "response.cached", True, prompt=0
    ),
    Refusal(
        "prompt hits",
        "testCacheHitCount",
        field="results.prompts.0.metrics.testCacheHitCount",
        value=1,
    ),
    Refusal(
        "repeat hits", "cachedResults", "words-baseline", "results.repeatStability.cachedResults", 1
    ),
    *(
        Refusal(
            f"group hits {v}",
            "cache use reported by results.repeatStability.groups[].cached",
            "words-baseline",
            "results.repeatStability.groups.0.cached",
            v,
        )
        for v in (2, True)
    ),
    Refusal(
        "grader hit",
        "metadata.cachedResponse",
        field=ROW + "gradingResult.metadata.cachedResponse",
        value=True,
    ),
    Refusal(
        "nested grader hit",
        "metadata.cachedResponse",
        field=ROW + "gradingResult.componentResults.0.componentResults",
        value=[{"metadata": {"cachedResponse": True}}],
    ),
    Refusal("actual duplicate", "duplicate task id", "shapes"),
    Refusal(
        "duplicate within repeat", "duplicate task id", "words-baseline", ROW + "repeatIndex", 1
    ),
    Refusal(
        "different tasks",
        "different task ids",
        "words-baseline",
        ROW + "testCase.description",
        "other",
    ),
    Refusal("round gap", "1 to N without gaps", "words-baseline", ROW + "repeatIndex", 4),
    Refusal("round count", "round count differs", "words-baseline", "runtimeOptions.repeat", 4),
    Refusal(
        "unindexed repeats", "rows without repeatIndex", field="runtimeOptions.repeat", value=2
    ),
    Refusal("mixed rounds", "mixes rows", "words-baseline", ROW + "repeatIndex", None),
    *(
        Refusal(
            f"bad repeatIndex {v}",
            "repeatIndex must be a non-negative integer",
            "words-baseline",
            ROW + "repeatIndex",
            v,
        )
        for v in (-1, 0.5, False)
    ),
    *(
        Refusal(
            f"http {v}",
            "HTTP error range",
            "two-providers",
            ROW + "response.metadata.http.status",
            v,
            prompt=0,
        )
        for v in (400, 500, 500.0, 599)
    ),
]


@pytest.mark.parametrize("case", REFUSALS, ids=lambda c: c.name)
def test_a03_refusals(case: Refusal) -> None:
    with pytest.raises(PromptfooError) as exc:
        read(case.source(), prompt=case.prompt)
    assert case.reason in str(exc.value)


def test_a03_null_and_absent_vars_have_same_id() -> None:
    doc = json.loads((REAL / "words-single.json").read_bytes())
    case = doc["results"]["results"][0]["testCase"]
    del case["vars"]
    absent = read(canonical(doc)).rows[0].task_id
    case["vars"] = None
    assert read(canonical(doc)).rows[0].task_id == absent == raw_rows(doc)[0][1]


def test_a03_golden_id() -> None:
    doc = json.loads((REAL / "words-single.json").read_bytes())
    case = doc["results"]["results"][0]["testCase"]
    case.update(description="Row #1", vars={"x": [1, 1.0, True, None, ["é"]]})
    assert read(canonical(doc)).rows[0].task_id == "Row #1 #25722901d99dfa75"


@pytest.mark.parametrize("value", ["2", -1, None, 1.5, False])
def test_malformed_group_cache_count(value: object) -> None:
    doc = json.loads((REAL / "words-baseline.json").read_bytes())
    doc["results"]["repeatStability"]["groups"][0]["cached"] = value
    with pytest.raises(PromptfooError, match=r"groups\[\]\.cached must be a non-negative integer"):
        read(canonical(doc))


def test_absent_and_zero_group_cache_counts() -> None:
    doc = json.loads((REAL / "words-baseline.json").read_bytes())
    group = doc["results"]["repeatStability"]["groups"][0]
    group["cached"] = 0
    expected = read(canonical(doc))
    del group["cached"]
    assert read(canonical(doc)) == expected


def test_non_object_http_metadata_is_ignored() -> None:
    doc = json.loads((REAL / "e2e-discovery.json").read_bytes())
    expected = read(canonical(doc))
    doc["results"]["results"][0]["response"].setdefault("metadata", {})["http"] = "HTTP/2"
    assert read(canonical(doc)) == expected
