"""Context row for the audit: TF-IDF + logistic regression trained on each dataset's train split.

Run with:  uv run --isolated --with scikit-learn --with scipy python baseline.py DATA_DIR OUT_JSON
Not part of any hypothesis; it places the zero-shot numbers against a cheap supervised model.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import beta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import FeatureUnion, Pipeline


def clopper_pearson(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    low = beta.ppf((1 - level) / 2, k, n - k + 1) if k > 0 else 0.0
    high = beta.ppf(1 - (1 - level) / 2, k + 1, n - k) if k < n else 1.0
    return float(low), float(high)


def ece(scores: np.ndarray, correct: np.ndarray, bins: int = 15) -> float:
    index = np.minimum((scores * bins).astype(int), bins - 1)
    total = 0.0
    for b in range(bins):
        mask = index == b
        if mask.any():
            total += mask.mean() * abs(correct[mask].mean() - scores[mask].mean())
    return float(total)


def make_model() -> Pipeline:
    features = FeatureUnion(
        [
            ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
        ]
    )
    return Pipeline([("features", features), ("clf", LogisticRegression(C=10.0, max_iter=3000))])


def evaluate(
    name: str, train: list[tuple[str, str]], test: list[tuple[str, str]], oos: list[str]
) -> dict:
    started = time.time()
    model = make_model()
    model.fit([t for t, _ in train], [label for _, label in train])
    fit_seconds = time.time() - started
    classes = list(model.classes_)
    probs = model.predict_proba([t for t, _ in test])
    predicted = np.array([classes[i] for i in probs.argmax(axis=1)])
    labels = np.array([label for _, label in test])
    correct = predicted == labels
    p_max = probs.max(axis=1)
    k, n = int(correct.sum()), len(correct)
    low, high = clopper_pearson(k, n)
    result = {
        "dataset": name,
        "train_items": len(train),
        "test_items": n,
        "fit_seconds": round(fit_seconds, 1),
        "accuracy": k / n,
        "accuracy_low": low,
        "accuracy_high": high,
        "ece_p_max": ece(p_max, correct.astype(float)),
        "mean_p_max": float(p_max.mean()),
        "selective": {},
    }
    for threshold in (0.5, 0.6, 0.85, 0.9):
        mask = p_max >= threshold
        result["selective"][str(threshold)] = {
            "coverage": float(mask.mean()),
            "accuracy_covered": float(correct[mask].mean()) if mask.any() else None,
        }
    if oos:
        oos_probs = model.predict_proba(oos)
        scores = np.concatenate([1 - p_max, 1 - oos_probs.max(axis=1)])
        positives = np.concatenate([np.zeros(n), np.ones(len(oos))])
        result["oos_auroc_one_minus_p_max"] = float(roc_auc_score(positives, scores))
        result["oos_average_precision"] = float(average_precision_score(positives, scores))
    return result


def main() -> None:
    data_dir = Path(sys.argv[1])
    out = Path(sys.argv[2])
    clinc = json.loads((data_dir / "clinc_data_full.json").read_text())
    results = [
        evaluate(
            "clinc150",
            [(t, label) for t, label in clinc["train"]],
            [(t, label) for t, label in clinc["test"]],
            [t for t, _ in clinc["oos_test"]],
        )
    ]
    with (data_dir / "banking77_train.csv").open(newline="") as handle:
        train = [(r["text"], r["category"]) for r in csv.DictReader(handle)]
    with (data_dir / "banking77_test.csv").open(newline="") as handle:
        test = [(r["text"], r["category"]) for r in csv.DictReader(handle)]
    results.append(evaluate("banking77", train, test, []))
    out.write_text(json.dumps(results, indent=2) + "\n")
    for r in results:
        print(
            f"{r['dataset']}: accuracy {r['accuracy']:.4f} "
            f"[{r['accuracy_low']:.4f}, {r['accuracy_high']:.4f}] "
            f"ece {r['ece_p_max']:.4f} fit {r['fit_seconds']}s "
            + (
                f"oos_auroc {r['oos_auroc_one_minus_p_max']:.4f}"
                if "oos_auroc_one_minus_p_max" in r
                else ""
            )
        )


if __name__ == "__main__":
    main()
