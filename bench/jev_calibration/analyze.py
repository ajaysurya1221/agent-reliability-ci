"""Turn the sealed audit records into the pre-registered measures.

    .venv/bin/python -m bench.jev_calibration.analyze --runs runs/jev-calibration/2026-10-03 \
        --out docs/results/jev-calibration/2026-10-03

Verifies every store's hash chain, then writes `metrics.json`, `report.md`, one reliability
diagram per dataset (SVG) and `records.compact.jsonl.gz`, a per-record summary that keeps each
record's hash so it can be checked against the raw store.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from bench.jev_calibration import metrics
from bench.jev_calibration.data import BANKING, CLINC, OOS_LABEL
from bench.jev_calibration.questions import CLOSED_ID, NOUL_ID, OOS_OPTION, OPEN_ID, JsonValue
from bench.jev_calibration.run import PROTOCOL_BUNDLED, PROTOCOL_CLOSED_ONLY, canonical, sha256_text

PRICE_PER_MTOK = 0.042
COVERAGES = (1.0, 0.95, 0.9, 0.8, 0.7)
THRESHOLDS = (0.5, 0.6, 0.85, 0.9)
BINS = 15


@dataclass(frozen=True)
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]

    @property
    def p_max(self) -> float:
        return max(self.probabilities.values()) if self.probabilities else math.nan

    def p_of(self, option: str) -> float:
        return self.probabilities.get(option, 0.0)

    def top(self, k: int) -> list[tuple[str, float]]:
        return sorted(self.probabilities.items(), key=lambda kv: (-kv[1], kv[0]))[:k]


@dataclass(frozen=True)
class Record:
    dataset: str
    item_id: str
    label: str
    domain: str | None
    pass_no: int
    protocol: str
    status: int | None
    error: str | None
    request_id: str | None
    latency_ms: float
    model: str | None
    input_tokens: int
    output_tokens: int
    closed: ChoiceAnswer | None
    opened: ChoiceAnswer | None
    noul: float | None
    record_sha256: str

    @property
    def ok(self) -> bool:
        return self.error is None and self.status is not None and self.status < 400

    @property
    def in_scope(self) -> bool:
        return self.label != OOS_LABEL


def _choice(raw: JsonValue) -> ChoiceAnswer | None:
    if not isinstance(raw, dict) or raw.get("type") != "choice":
        return None
    probabilities = cast(dict[str, float], raw.get("probabilities") or {})
    return ChoiceAnswer(
        choice=str(raw.get("choice")),
        confidence=float(cast(float, raw.get("confidence", math.nan))),
        probabilities={str(k): float(v) for k, v in probabilities.items()},
    )


def _noul(raw: JsonValue) -> float | None:
    if not isinstance(raw, dict) or raw.get("type") != "noul":
        return None
    return float(cast(float, raw["noul"]))


def load_store(path: Path) -> tuple[list[Record], dict[str, JsonValue]]:
    """Parse a store and verify its hash chain; the second value is the chain report."""
    records: list[Record] = []
    prev = "0" * 64
    verified = 0
    broken: list[int] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = cast(dict[str, JsonValue], json.loads(line))
            claimed = str(raw["record_sha256"])
            without = {k: v for k, v in raw.items() if k != "record_sha256"}
            expected = sha256_text(prev + "\n" + canonical(without))
            if claimed != expected or str(raw["prev_sha256"]) != prev:
                broken.append(int(cast(int, raw["seq"])))
            else:
                verified += 1
            prev = claimed
            answers = cast(dict[str, JsonValue], raw.get("answers") or {})
            usage = cast(dict[str, int], raw.get("usage") or {})
            domain = raw.get("domain")
            status = raw.get("status")
            error = raw.get("error")
            request_id = raw.get("request_id")
            model = raw.get("model")
            records.append(
                Record(
                    dataset=str(raw["dataset"]),
                    item_id=str(raw["item_id"]),
                    label=str(raw["label"]),
                    domain=str(domain) if isinstance(domain, str) else None,
                    pass_no=int(cast(int, raw["pass"])),
                    protocol=str(raw["protocol"]),
                    status=int(status) if isinstance(status, int) else None,
                    error=str(error) if isinstance(error, str) else None,
                    request_id=str(request_id) if isinstance(request_id, str) else None,
                    latency_ms=float(cast(float, raw["latency_ms"])),
                    model=str(model) if isinstance(model, str) else None,
                    input_tokens=int(usage.get("input_tokens", 0)),
                    output_tokens=int(usage.get("output_tokens", 0)),
                    closed=_choice(answers.get(CLOSED_ID)),
                    opened=_choice(answers.get(OPEN_ID)),
                    noul=_noul(answers.get(NOUL_ID)),
                    record_sha256=claimed,
                )
            )
    report: dict[str, JsonValue] = {
        "store": path.name,
        "records": len(records),
        "verified": verified,
        "broken_seqs": cast(JsonValue, broken[:20]),
        "chain_ok": not broken,
    }
    return records, report


def by_pass(records: Iterable[Record], protocol: str) -> dict[int, dict[str, Record]]:
    out: dict[int, dict[str, Record]] = defaultdict(dict)
    for record in records:
        if record.protocol == protocol and record.ok:
            out[record.pass_no][record.item_id] = record
    return out


def interval_dict(correct: Sequence[bool]) -> dict[str, JsonValue]:
    rate, low, high = metrics.accuracy_interval(correct)
    return {"n": len(correct), "rate": rate, "low": low, "high": high}


def calibration_block(scores: Sequence[float], correct: Sequence[bool]) -> dict[str, JsonValue]:
    def ece_of(indices: Sequence[int]) -> float:
        return metrics.ece([scores[i] for i in indices], [correct[i] for i in indices], BINS)

    low, high = metrics.bootstrap_interval(ece_of, len(scores), resamples=1000, seed=0)
    bins: list[JsonValue] = [
        {
            "lower": b.lower,
            "upper": b.upper,
            "count": b.count,
            "mean_score": None if math.isnan(b.mean_score) else b.mean_score,
            "accuracy": None if math.isnan(b.accuracy) else b.accuracy,
        }
        for b in metrics.reliability_bins(scores, correct, BINS)
    ]
    return {
        "n": len(scores),
        "ece": metrics.ece(scores, correct, BINS),
        "ece_low": low,
        "ece_high": high,
        "mce": metrics.mce(scores, correct, BINS),
        "brier": metrics.brier(scores, correct),
        "auroc_correct": metrics.auroc(scores, correct),
        "mean_score": sum(scores) / len(scores),
        "bins": bins,
    }


def selective_block(scores: Sequence[float], correct: Sequence[bool]) -> dict[str, JsonValue]:
    by_coverage: dict[str, JsonValue] = {}
    for coverage in COVERAGES:
        threshold = metrics.threshold_for_coverage(scores, coverage)
        result = metrics.selective(scores, correct, threshold)
        covered = [c for s, c in zip(scores, correct, strict=True) if s >= threshold]
        _, low, high = metrics.accuracy_interval(covered)
        by_coverage[f"{coverage:.2f}"] = {
            "threshold": result.threshold,
            "covered": result.covered,
            "coverage": result.covered / len(scores),
            "accuracy_covered": result.accuracy_covered,
            "accuracy_covered_low": low,
            "accuracy_covered_high": high,
            "accuracy_rest": None if math.isnan(result.accuracy_rest) else result.accuracy_rest,
        }
    by_threshold: dict[str, JsonValue] = {}
    for threshold in THRESHOLDS:
        result = metrics.selective(scores, correct, threshold)
        covered = [c for s, c in zip(scores, correct, strict=True) if s >= threshold]
        if covered:
            _, low, high = metrics.accuracy_interval(covered)
        else:
            low = high = math.nan
        by_threshold[f"{threshold:.2f}"] = {
            "covered": result.covered,
            "coverage": result.covered / len(scores),
            "accuracy_covered": None
            if math.isnan(result.accuracy_covered)
            else result.accuracy_covered,
            "accuracy_covered_low": None if math.isnan(low) else low,
            "accuracy_covered_high": None if math.isnan(high) else high,
            "accuracy_rest": None if math.isnan(result.accuracy_rest) else result.accuracy_rest,
        }
    return {"by_coverage": by_coverage, "by_threshold": by_threshold}


def oos_block(scores: Sequence[float], positives: Sequence[bool]) -> dict[str, JsonValue]:
    return {
        "n_in_scope": sum(1 for p in positives if not p),
        "n_out_of_scope": sum(1 for p in positives if p),
        "auroc": metrics.auroc(scores, positives),
        "average_precision": metrics.average_precision(scores, positives),
        "fpr_at_95_tpr": metrics.fpr_at_tpr(scores, positives, 0.95),
    }


def latency_block(records: Sequence[Record]) -> dict[str, JsonValue]:
    values = [r.latency_ms for r in records if r.ok]
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "p50": metrics.percentile(values, 0.5),
        "p90": metrics.percentile(values, 0.9),
        "p99": metrics.percentile(values, 0.99),
        "mean": sum(values) / len(values),
    }


def usage_block(records: Sequence[Record]) -> dict[str, JsonValue]:
    ok = [r for r in records if r.ok]
    input_tokens = sum(r.input_tokens for r in ok)
    return {
        "requests": len(records),
        "ok": len(ok),
        "failed": len(records) - len(ok),
        "statuses": cast(JsonValue, dict(Counter(str(r.status) for r in records))),
        "models": cast(JsonValue, dict(Counter(str(r.model) for r in ok))),
        "input_tokens": input_tokens,
        "output_tokens": sum(r.output_tokens for r in ok),
        "estimated_cost_usd": input_tokens * PRICE_PER_MTOK / 1e6,
    }


def closed_in_scope_block(items: Sequence[Record]) -> dict[str, JsonValue]:
    """Accuracy, calibration and selective accuracy of `intent_closed` on in-scope items."""
    rows = [(r, r.closed) for r in items if r.in_scope and r.closed is not None]
    correct = [a.choice == r.label for r, a in rows]
    p_max = [a.p_max for _, a in rows]
    confidence = [a.confidence for _, a in rows]
    p_true = [a.p_of(r.label) for r, a in rows]
    confusions = Counter((r.label, a.choice) for r, a in rows if a.choice != r.label)
    return {
        "accuracy": interval_dict(correct),
        "log_loss_true_label": metrics.log_loss(p_true),
        "calibration_p_max": calibration_block(p_max, correct),
        "calibration_confidence": calibration_block(confidence, correct),
        "selective_p_max": selective_block(p_max, correct),
        "selective_confidence": selective_block(confidence, correct),
        "top_confusions": [
            {"label": label, "predicted": predicted, "count": count}
            for (label, predicted), count in confusions.most_common(10)
        ],
    }


def domain_block(items: Sequence[Record]) -> dict[str, JsonValue]:
    groups: dict[str, list[bool]] = defaultdict(list)
    for r in items:
        if r.in_scope and r.closed is not None and r.domain is not None:
            groups[r.domain].append(r.closed.choice == r.label)
    return {domain: interval_dict(correct) for domain, correct in sorted(groups.items())}


def clinc_oos_blocks(items: Sequence[Record]) -> dict[str, JsonValue]:
    rows = [
        r for r in items if r.closed is not None and r.opened is not None and r.noul is not None
    ]
    positives = [not r.in_scope for r in rows]
    closed_score = [1.0 - cast(ChoiceAnswer, r.closed).p_max for r in rows]
    open_score = [cast(ChoiceAnswer, r.opened).p_of(OOS_OPTION) for r in rows]
    noul_score = [cast(float, r.noul) for r in rows]
    opened_in = [(r, cast(ChoiceAnswer, r.opened)) for r in rows if r.in_scope]
    opened_oos = [cast(ChoiceAnswer, r.opened) for r in rows if not r.in_scope]
    in_scope_correct = [a.choice == r.label for r, a in opened_in]
    in_scope_abstained = sum(1 for _, a in opened_in if a.choice == OOS_OPTION)
    oos_recalled = sum(1 for a in opened_oos if a.choice == OOS_OPTION)
    absorbed = Counter(cast(ChoiceAnswer, r.closed).choice for r in rows if not r.in_scope)
    oos_predictions = in_scope_abstained + oos_recalled
    return {
        "detection": {
            "one_minus_p_max_closed": oos_block(closed_score, positives),
            "p_out_of_scope_open": oos_block(open_score, positives),
            "noul_is_oos": oos_block(noul_score, positives),
        },
        "open_question_read_literally": {
            "in_scope_accuracy": interval_dict(in_scope_correct) if in_scope_correct else None,
            "in_scope_answered_out_of_scope": in_scope_abstained,
            "oos_recall": interval_dict([a.choice == OOS_OPTION for a in opened_oos])
            if opened_oos
            else None,
            "oos_precision": oos_recalled / oos_predictions if oos_predictions else None,
        },
        "noul_summary": {
            "mean_in_scope": sum(s for s, p in zip(noul_score, positives, strict=True) if not p)
            / max(1, sum(1 for p in positives if not p)),
            "mean_out_of_scope": sum(s for s, p in zip(noul_score, positives, strict=True) if p)
            / max(1, sum(1 for p in positives if p)),
        },
        "intents_absorbing_oos": [
            {"intent": intent, "count": count} for intent, count in absorbed.most_common(10)
        ],
    }


def consistency_block(passes: dict[int, dict[str, Record]]) -> dict[str, JsonValue]:
    out: dict[str, JsonValue] = {}
    numbers = sorted(passes)
    if 1 not in passes:
        return out
    base = passes[1]
    for other in numbers:
        if other == 1:
            continue
        shared = [i for i in base if i in passes[other] and base[i].closed is not None]
        shared = [i for i in shared if passes[other][i].closed is not None]
        if not shared:
            continue
        a = [cast(ChoiceAnswer, base[i].closed) for i in shared]
        b = [cast(ChoiceAnswer, passes[other][i].closed) for i in shared]
        in_scope = [k for k, i in enumerate(shared) if base[i].in_scope]
        confident = [k for k in in_scope if a[k].p_max >= 0.6]
        entry: dict[str, JsonValue] = {
            "items": len(shared),
            "top1_agreement_all": metrics.agreement([x.choice for x in a], [x.choice for x in b]),
            "top1_agreement_in_scope": metrics.agreement(
                [a[k].choice for k in in_scope], [b[k].choice for k in in_scope]
            )
            if in_scope
            else None,
            "top1_agreement_in_scope_p_max_ge_0.6": metrics.agreement(
                [a[k].choice for k in confident], [b[k].choice for k in confident]
            )
            if confident
            else None,
            "confident_share": len(confident) / len(in_scope) if in_scope else None,
            "mean_abs_diff_p_max": metrics.mean_abs_diff(
                [x.p_max for x in a], [x.p_max for x in b]
            ),
        }
        nouls = [
            (cast(float, base[i].noul), cast(float, passes[other][i].noul))
            for i in shared
            if base[i].noul is not None and passes[other][i].noul is not None
        ]
        if nouls:
            entry["noul_mean_abs_diff"] = metrics.mean_abs_diff(
                [x for x, _ in nouls], [y for _, y in nouls]
            )
            entry["noul_crossing_0.5_share"] = sum(
                1 for x, y in nouls if (x >= 0.5) != (y >= 0.5)
            ) / len(nouls)
        out[f"pass_1_vs_{other}"] = entry
    if all(p in passes for p in (1, 2, 3)):
        shared = [
            i
            for i in base
            if all(i in passes[p] and passes[p][i].closed is not None for p in (2, 3))
            and base[i].closed is not None
        ]
        if shared:
            unanimous = sum(
                1
                for i in shared
                if len({cast(ChoiceAnswer, passes[p][i].closed).choice for p in (1, 2, 3)}) == 1
            )
            out["all_three_passes_agree"] = {"items": len(shared), "share": unanimous / len(shared)}
    return out


def independence_block(
    bundled: dict[str, Record], closed_only: dict[str, Record]
) -> dict[str, JsonValue]:
    shared = [
        i
        for i in closed_only
        if i in bundled and bundled[i].closed is not None and closed_only[i].closed is not None
    ]
    if not shared:
        return {"items": 0}
    a = [cast(ChoiceAnswer, bundled[i].closed) for i in shared]
    b = [cast(ChoiceAnswer, closed_only[i].closed) for i in shared]
    in_scope_correct_bundled = [
        a[k].choice == bundled[i].label for k, i in enumerate(shared) if bundled[i].in_scope
    ]
    in_scope_correct_alone = [
        b[k].choice == bundled[i].label for k, i in enumerate(shared) if bundled[i].in_scope
    ]
    return {
        "items": len(shared),
        "top1_agreement": metrics.agreement([x.choice for x in a], [x.choice for x in b]),
        "mean_abs_diff_p_max": metrics.mean_abs_diff([x.p_max for x in a], [x.p_max for x in b]),
        "in_scope_accuracy_bundled": interval_dict(in_scope_correct_bundled)
        if in_scope_correct_bundled
        else None,
        "in_scope_accuracy_alone": interval_dict(in_scope_correct_alone)
        if in_scope_correct_alone
        else None,
    }


def pooled_block(passes: dict[int, dict[str, Record]]) -> dict[str, JsonValue]:
    rows = [r for p in sorted(passes) for r in passes[p].values() if r.in_scope and r.closed]
    if not rows:
        return {}
    correct = [cast(ChoiceAnswer, r.closed).choice == r.label for r in rows]
    p_max = [cast(ChoiceAnswer, r.closed).p_max for r in rows]
    return {
        "passes": cast(JsonValue, sorted(passes)),
        "accuracy": interval_dict(correct),
        "ece_p_max": metrics.ece(p_max, correct, BINS),
        "note": "passes pooled as if independent; a sensitivity check, not a primary measure",
    }


def hypotheses(result: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    def get(path: str) -> JsonValue:
        node: JsonValue = result
        for key in path.split("."):
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        return node

    def number(path: str) -> float:
        value = get(path)
        if isinstance(value, bool) or not isinstance(value, int | float):
            return math.nan
        return float(value)

    rows: list[dict[str, JsonValue]] = []

    def add(name: str, claim: str, measure: str, value: float, rule: str, met: bool) -> None:
        rows.append(
            {
                "id": name,
                "claim": claim,
                "measure": measure,
                "value": value,
                "rule": rule,
                "met": met,
            }
        )

    v = number("clinc150.pass_1.closed_in_scope.accuracy.low")
    add(
        "H1",
        "zero-shot accuracy",
        "CLINC150 closed top-1 accuracy, lower 95% bound",
        v,
        ">= 0.85",
        v >= 0.85,
    )
    v = number("clinc150.pass_1.closed_in_scope.calibration_p_max.ece_high")
    add(
        "H2",
        "calibration",
        "CLINC150 in-scope ECE of p_max, upper 95% bootstrap bound",
        v,
        "<= 0.05",
        v <= 0.05,
    )
    low = number(
        "clinc150.pass_1.closed_in_scope.selective_confidence.by_threshold.0.90.accuracy_covered_low"
    )
    coverage = number(
        "clinc150.pass_1.closed_in_scope.selective_confidence.by_threshold.0.90.coverage"
    )
    add(
        "H3",
        "gating is useful",
        "CLINC150 accuracy at confidence >= 0.9, lower 95% bound (coverage)",
        low,
        ">= 0.95 with coverage >= 0.5",
        low >= 0.95 and coverage >= 0.5,
    )
    v = number("clinc150.pass_1.oos.detection.p_out_of_scope_open.auroc")
    add(
        "H4",
        "out-of-scope detection",
        "AUROC of the open question's out_of_scope probability",
        v,
        ">= 0.90",
        v >= 0.90,
    )
    v = number("clinc150.consistency.pass_1_vs_2.top1_agreement_in_scope")
    add(
        "H5",
        "consistency",
        "CLINC150 in-scope top-1 agreement, pass 1 vs 2",
        v,
        ">= 0.95",
        v >= 0.95,
    )
    v = number("clinc150.pass_1.latency.p50")
    add("H6", "speed", "CLINC150 p50 latency from this container, ms", v, "<= 500", v <= 500)
    v = number("banking77.pass_1.closed_in_scope.accuracy.low")
    add(
        "H7",
        "the harder benchmark",
        "Banking77 top-1 accuracy, lower 95% bound",
        v,
        ">= 0.70",
        v >= 0.70,
    )
    return rows


def dataset_result(
    name: str, records: Sequence[Record], closed_only: Sequence[Record]
) -> dict[str, JsonValue]:
    passes = by_pass(records, PROTOCOL_BUNDLED)
    out: dict[str, JsonValue] = {"usage": usage_block(records)}
    for pass_no in sorted(passes):
        items = list(passes[pass_no].values())
        block: dict[str, JsonValue] = {
            "closed_in_scope": closed_in_scope_block(items),
            "latency": latency_block(items),
        }
        if name == CLINC:
            block["by_domain"] = domain_block(items)
            block["oos"] = clinc_oos_blocks(items)
            opened_in = [(r, r.opened) for r in items if r.in_scope and r.opened]
            block["open_in_scope_accuracy"] = interval_dict(
                [a.choice == r.label for r, a in opened_in]
            )
        out[f"pass_{pass_no}"] = block
    out["consistency"] = consistency_block(passes)
    out["pooled"] = pooled_block(passes)
    if closed_only and 1 in passes:
        alone = by_pass(closed_only, PROTOCOL_CLOSED_ONLY).get(1, {})
        out["bundling_independence"] = independence_block(passes[1], alone)
        out["usage_closed_only"] = usage_block(closed_only)
    return out


def compact_record(r: Record) -> dict[str, JsonValue]:
    def summary(a: ChoiceAnswer | None, label: str) -> JsonValue:
        if a is None:
            return None
        return {
            "choice": a.choice,
            "confidence": a.confidence,
            "p_max": a.p_max,
            "p_true": a.p_of(label),
            "p_out_of_scope": a.p_of(OOS_OPTION) if OOS_OPTION in a.probabilities else None,
            "top5": cast(JsonValue, [[k, v] for k, v in a.top(5)]),
        }

    return {
        "dataset": r.dataset,
        "item_id": r.item_id,
        "label": r.label,
        "domain": r.domain,
        "pass": r.pass_no,
        "protocol": r.protocol,
        "status": r.status,
        "error": r.error,
        "request_id": r.request_id,
        "latency_ms": r.latency_ms,
        "model": r.model,
        "input_tokens": r.input_tokens,
        "output_tokens": r.output_tokens,
        "closed": summary(r.closed, r.label),
        "open": summary(r.opened, r.label),
        "noul": r.noul,
        "record_sha256": r.record_sha256,
    }


def reliability_svg(bins: Sequence[JsonValue], title: str) -> str:
    size, margin = 420, 48
    plot = size - 2 * margin
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size + 24}" '
        f'viewBox="0 0 {size} {size + 24}" font-family="sans-serif" font-size="11">',
        f'<rect width="{size}" height="{size + 24}" fill="white"/>',
        f'<text x="{size / 2}" y="20" text-anchor="middle" font-size="13">{title}</text>',
        f'<line x1="{margin}" y1="{margin + plot}" x2="{margin + plot}" y2="{margin}" '
        'stroke="#999" stroke-dasharray="4 3"/>',
    ]
    total = sum(int(cast(int, cast(dict[str, JsonValue], b)["count"])) for b in bins)
    for raw in bins:
        b = cast(dict[str, JsonValue], raw)
        count = int(cast(int, b["count"]))
        if not count:
            continue
        lower, upper = float(cast(float, b["lower"])), float(cast(float, b["upper"]))
        accuracy = float(cast(float, b["accuracy"]))
        x = margin + lower * plot
        width = (upper - lower) * plot
        height = accuracy * plot
        parts.append(
            f'<rect x="{x:.1f}" y="{margin + plot - height:.1f}" width="{width:.1f}" '
            f'height="{height:.1f}" fill="#3b6ea5" fill-opacity="0.75" stroke="white"/>'
        )
        parts.append(
            f'<text x="{x + width / 2:.1f}" y="{margin + plot + 14}" text-anchor="middle" '
            f'font-size="8">{100 * count / total:.0f}%</text>'
        )
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        px = margin + tick * plot
        py = margin + plot - tick * plot
        parts.append(
            f'<text x="{px:.1f}" y="{margin + plot + 26}" text-anchor="middle">{tick:.2f}</text>'
        )
        parts.append(f'<text x="{margin - 6}" y="{py + 4:.1f}" text-anchor="end">{tick:.2f}</text>')
    parts.append(
        f'<text x="{size / 2}" y="{size + 14}" text-anchor="middle">top probability '
        "(bars: accuracy in the bin; labels: share of items)</text>"
    )
    parts.append(
        f'<text transform="translate(14 {size / 2}) rotate(-90)" '
        'text-anchor="middle">accuracy</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def fmt(value: JsonValue, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return "n/a" if math.isnan(value) else f"{value:.{digits}f}"
    return str(value)


def interval(block: JsonValue) -> str:
    if not isinstance(block, dict):
        return "n/a"
    return f"{fmt(block['rate'])} [{fmt(block['low'])}, {fmt(block['high'])}] (n={block['n']})"


def render_report(result: dict[str, JsonValue], chains: Sequence[JsonValue]) -> str:
    lines: list[str] = ["# Calibration audit: measures from the sealed records", ""]
    lines.append(
        "Generated by `bench/jev_calibration/analyze.py`; "
        "the pre-registration is `bench/jev_calibration/PROTOCOL.md`."
    )
    lines.append("")
    lines.append("## Hash chains")
    lines.append("")
    lines.append("| Store | Records | Verified | Chain |")
    lines.append("|---|---:|---:|---|")
    for raw in chains:
        c = cast(dict[str, JsonValue], raw)
        lines.append(
            f"| `{c['store']}` | {c['records']} | {c['verified']} | "
            f"{'ok' if c['chain_ok'] else 'BROKEN'} |"
        )
    lines.append("")
    lines.append("## Pre-registered expectations")
    lines.append("")
    lines.append("| # | Claim | Measure | Value | Rule | Met |")
    lines.append("|---|---|---|---:|---|---|")
    for raw in cast(list[JsonValue], result["hypotheses"]):
        h = cast(dict[str, JsonValue], raw)
        lines.append(
            f"| {h['id']} | {h['claim']} | {h['measure']} | {fmt(h['value'])} | "
            f"{h['rule']} | {fmt(h['met'])} |"
        )
    lines.append("")
    for name in (CLINC, BANKING):
        if name not in result:
            continue
        ds = cast(dict[str, JsonValue], result[name])
        lines.append(f"## {name}")
        lines.append("")
        usage = cast(dict[str, JsonValue], ds["usage"])
        lines.append(
            f"Requests {usage['requests']}, ok {usage['ok']}, failed {usage['failed']}; "
            f"models {usage['models']}; "
            f"input tokens {usage['input_tokens']}, output tokens {usage['output_tokens']}, "
            f"estimated USD {fmt(usage['estimated_cost_usd'], 3)} at list price."
        )
        lines.append("")
        lines.append(
            "| Pass | Closed accuracy [95% CP] | Log loss | ECE p_max [95% boot] | MCE | Brier "
            "| AUROC(correct) | Latency p50 / p90 / p99 ms |"
        )
        lines.append("|---|---|---:|---|---:|---:|---:|---|")
        for key in sorted(k for k in ds if k.startswith("pass_")):
            p = cast(dict[str, JsonValue], ds[key])
            c = cast(dict[str, JsonValue], p["closed_in_scope"])
            cal = cast(dict[str, JsonValue], c["calibration_p_max"])
            lat = cast(dict[str, JsonValue], p["latency"])
            lines.append(
                f"| {key.removeprefix('pass_')} | {interval(c['accuracy'])} | "
                f"{fmt(c['log_loss_true_label'])} | "
                f"{fmt(cal['ece'])} [{fmt(cal['ece_low'])}, {fmt(cal['ece_high'])}] | "
                f"{fmt(cal['mce'])} | "
                f"{fmt(cal['brier'])} | {fmt(cal['auroc_correct'])} | "
                f"{fmt(lat.get('p50'), 0)} / {fmt(lat.get('p90'), 0)} / {fmt(lat.get('p99'), 0)} |"
            )
        lines.append("")
        p1 = cast(dict[str, JsonValue], ds["pass_1"])
        c1 = cast(dict[str, JsonValue], p1["closed_in_scope"])
        for score_name, key in (
            ("confidence", "selective_confidence"),
            ("p_max", "selective_p_max"),
        ):
            sel = cast(dict[str, JsonValue], c1[key])
            lines.append(f"### Pass 1, selective accuracy on `{score_name}`")
            lines.append("")
            lines.append(
                "| Threshold | Coverage | Accuracy covered [95% CP] | Accuracy of the rest |"
            )
            lines.append("|---:|---:|---|---:|")
            for threshold, raw in cast(dict[str, JsonValue], sel["by_threshold"]).items():
                t = cast(dict[str, JsonValue], raw)
                lines.append(
                    f"| {threshold} | {fmt(t['coverage'])} | {fmt(t['accuracy_covered'])} "
                    f"[{fmt(t['accuracy_covered_low'])}, {fmt(t['accuracy_covered_high'])}] | "
                    f"{fmt(t['accuracy_rest'])} |"
                )
            lines.append("")
            lines.append(
                "| Target coverage | Threshold | Accuracy covered [95% CP] | Accuracy of the rest |"
            )
            lines.append("|---:|---:|---|---:|")
            for coverage, raw in cast(dict[str, JsonValue], sel["by_coverage"]).items():
                t = cast(dict[str, JsonValue], raw)
                lines.append(
                    f"| {coverage} | {fmt(t['threshold'], 2)} | {fmt(t['accuracy_covered'])} "
                    f"[{fmt(t['accuracy_covered_low'])}, {fmt(t['accuracy_covered_high'])}] | "
                    f"{fmt(t['accuracy_rest'])} |"
                )
            lines.append("")
        lines.append("### Pass 1, reliability of `p_max` (15 equal-width bins)")
        lines.append("")
        lines.append("| Bin | Items | Mean p_max | Accuracy |")
        lines.append("|---|---:|---:|---:|")
        for raw in cast(
            list[JsonValue], cast(dict[str, JsonValue], c1["calibration_p_max"])["bins"]
        ):
            b = cast(dict[str, JsonValue], raw)
            if b["count"]:
                lines.append(
                    f"| [{fmt(b['lower'], 2)}, {fmt(b['upper'], 2)}) | {b['count']} | "
                    f"{fmt(b['mean_score'])} | {fmt(b['accuracy'])} |"
                )
        lines.append("")
        lines.append("### Pass 1, most frequent confusions (label → predicted)")
        lines.append("")
        for raw in cast(list[JsonValue], c1["top_confusions"]):
            t = cast(dict[str, JsonValue], raw)
            lines.append(f"- `{t['label']}` → `{t['predicted']}`: {t['count']}")
        lines.append("")
        if name == CLINC:
            oos = cast(dict[str, JsonValue], p1["oos"])
            lines.append(
                "### Pass 1, out-of-scope detection (1,000 out-of-scope vs 4,500 in-scope)"
            )
            lines.append("")
            lines.append("| Score | AUROC | Average precision | FPR at 95% OOS recall |")
            lines.append("|---|---:|---:|---:|")
            for score, raw in cast(dict[str, JsonValue], oos["detection"]).items():
                d = cast(dict[str, JsonValue], raw)
                lines.append(
                    f"| `{score}` | {fmt(d['auroc'])} | {fmt(d['average_precision'])} | "
                    f"{fmt(d['fpr_at_95_tpr'])} |"
                )
            lines.append("")
            lit = cast(dict[str, JsonValue], oos["open_question_read_literally"])
            lines.append(
                "Open question read literally: in-scope accuracy "
                f"{interval(lit['in_scope_accuracy'])}, in-scope items answered `out_of_scope` "
                f"{lit['in_scope_answered_out_of_scope']}, "
                f"OOS recall {interval(lit['oos_recall'])}, "
                f"OOS precision {fmt(lit['oos_precision'])}."
            )
            lines.append("")
            ns = cast(dict[str, JsonValue], oos["noul_summary"])
            lines.append(
                f"Noul mean: in-scope {fmt(ns['mean_in_scope'])}, "
                f"out-of-scope {fmt(ns['mean_out_of_scope'])}."
            )
            lines.append("")
            absorbing = [
                cast(dict[str, JsonValue], t)
                for t in cast(list[JsonValue], oos["intents_absorbing_oos"])
            ]
            lines.append(
                "Intents absorbing out-of-scope queries (closed question): "
                + ", ".join(f"`{t['intent']}` ({t['count']})" for t in absorbing)
            )
            lines.append("")
            lines.append("### Pass 1, accuracy by domain")
            lines.append("")
            lines.append("| Domain | Accuracy [95% CP] |")
            lines.append("|---|---|")
            for domain, raw in cast(dict[str, JsonValue], p1["by_domain"]).items():
                lines.append(f"| {domain} | {interval(raw)} |")
            lines.append("")
        lines.append("### Consistency across passes")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(ds["consistency"], indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")
        if "bundling_independence" in ds:
            lines.append("### Bundling independence (closed question alone vs bundled, pass 1)")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(ds["bundling_independence"], indent=2, sort_keys=True))
            lines.append("```")
            lines.append("")
        lines.append("### Pooled passes (sensitivity)")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(ds["pooled"], indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    runs = cast(Path, args.runs)
    out = cast(Path, args.out)
    out.mkdir(parents=True, exist_ok=True)
    result: dict[str, JsonValue] = {}
    chains: list[JsonValue] = []
    compact: list[Record] = []
    for name in (CLINC, BANKING):
        store = runs / f"{name}.{PROTOCOL_BUNDLED}.jsonl"
        if not store.exists():
            continue
        records, chain = load_store(store)
        chains.append(chain)
        compact.extend(records)
        closed_only: list[Record] = []
        check = runs / f"{name}.{PROTOCOL_CLOSED_ONLY}.jsonl"
        if check.exists():
            closed_only, chain_check = load_store(check)
            chains.append(chain_check)
            compact.extend(closed_only)
        result[name] = dataset_result(name, records, closed_only)
        p1 = cast(dict[str, JsonValue], cast(dict[str, JsonValue], result[name])["pass_1"])
        bins = cast(
            list[JsonValue],
            cast(
                dict[str, JsonValue],
                cast(dict[str, JsonValue], p1["closed_in_scope"])["calibration_p_max"],
            )["bins"],
        )
        (out / f"reliability-{name}.svg").write_text(
            reliability_svg(bins, f"{name}: reliability of the top probability (pass 1)"),
            encoding="utf-8",
        )
    result["chains"] = chains
    result["hypotheses"] = cast(JsonValue, hypotheses(result))
    (out / "metrics.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "report.md").write_text(render_report(result, chains) + "\n", encoding="utf-8")
    with gzip.open(out / "records.compact.jsonl.gz", "wt", encoding="utf-8") as handle:
        for record in compact:
            handle.write(canonical(compact_record(record)) + "\n")
    print(f"wrote {out / 'metrics.json'}, report.md, {len(compact)} compact records")
    for raw in cast(list[JsonValue], result["hypotheses"]):
        h = cast(dict[str, JsonValue], raw)
        print(f"  {h['id']}: {fmt(h['value'])} {h['rule']} -> {'met' if h['met'] else 'NOT met'}")
    return 0 if all(cast(dict[str, JsonValue], c)["chain_ok"] for c in chains) else 1


if __name__ == "__main__":
    raise SystemExit(main())
