"""The two benchmarks, fetched from their canonical sources and verified by SHA-256 before use."""

from __future__ import annotations

import csv
import hashlib
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import cast

CLINC_URL = "https://raw.githubusercontent.com/clinc/oos-eval/master/data/data_full.json"
CLINC_SHA256 = "36923c3705a59e08fe9c3883d8bc2dd966ef93e22cb78ac41171782a698d56e0"
CLINC_DOMAINS_URL = "https://raw.githubusercontent.com/clinc/oos-eval/master/data/domains.json"
CLINC_DOMAINS_SHA256 = "b947b579d3b8e74b06f93b01083d8efaff2888b43a3e362533bd88a6e1211b3a"
BANKING_TEST_URL = "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data/test.csv"
BANKING_TEST_SHA256 = "d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d"
BANKING_CATEGORIES_URL = (
    "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data/"
    "categories.json"
)
BANKING_CATEGORIES_SHA256 = "53261da888122daf2d120d925458631d9619e15d82e56052e7a42e535ce32b63"

CLINC = "clinc150"
BANKING = "banking77"
OOS_LABEL = "oos"
DATASETS = (CLINC, BANKING)


@dataclass(frozen=True)
class Item:
    dataset: str
    item_id: str
    text: str
    label: str
    domain: str | None


@dataclass(frozen=True)
class Dataset:
    name: str
    items: tuple[Item, ...]
    intents: tuple[str, ...]
    domain_of: dict[str, str]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str, sha256: str, cache_dir: Path) -> Path:
    """Download `url` into `cache_dir` unless present, then verify its SHA-256 or raise."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{sha256[:12]}-{Path(url).name}"
    if not dest.exists():
        partial = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as out:
            for chunk in iter(lambda: response.read(1 << 20), b""):
                out.write(chunk)
        partial.replace(dest)
    actual = sha256_of(dest)
    if actual != sha256:
        raise ValueError(f"{dest.name}: sha256 {actual} does not match the pinned {sha256}")
    return dest


def load_clinc(cache_dir: Path) -> Dataset:
    raw = cast(
        dict[str, list[list[str]]],
        json.loads(fetch(CLINC_URL, CLINC_SHA256, cache_dir).read_text(encoding="utf-8")),
    )
    domains = cast(
        dict[str, list[str]],
        json.loads(
            fetch(CLINC_DOMAINS_URL, CLINC_DOMAINS_SHA256, cache_dir).read_text(encoding="utf-8")
        ),
    )
    intents = tuple(
        sorted({label for split in ("train", "val", "test") for _, label in raw[split]})
    )
    if len(intents) != 150:
        raise ValueError(f"expected 150 CLINC150 intents, found {len(intents)}")
    domain_of = {intent: domain for domain, names in domains.items() for intent in names}
    missing = [intent for intent in intents if intent not in domain_of]
    if missing:
        raise ValueError(f"intents without a domain: {missing[:5]}")
    items: list[Item] = []
    for index, (text, label) in enumerate(raw["test"]):
        items.append(Item(CLINC, f"{CLINC}-test-{index:04d}", text, label, domain_of[label]))
    for index, (text, label) in enumerate(raw["oos_test"]):
        if label != OOS_LABEL:
            raise ValueError(f"oos_test item {index} carries label {label!r}")
        items.append(Item(CLINC, f"{CLINC}-oos-{index:04d}", text, OOS_LABEL, None))
    return Dataset(CLINC, tuple(items), intents, domain_of)


def load_banking77(cache_dir: Path) -> Dataset:
    categories = cast(
        list[str],
        json.loads(
            fetch(BANKING_CATEGORIES_URL, BANKING_CATEGORIES_SHA256, cache_dir).read_text(
                encoding="utf-8"
            )
        ),
    )
    intents = tuple(sorted(categories))
    if len(intents) != 77:
        raise ValueError(f"expected 77 Banking77 intents, found {len(intents)}")
    known = set(intents)
    items: list[Item] = []
    with fetch(BANKING_TEST_URL, BANKING_TEST_SHA256, cache_dir).open(
        encoding="utf-8", newline=""
    ) as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            label = row["category"]
            if label not in known:
                raise ValueError(f"test row {index} carries an unknown category {label!r}")
            items.append(Item(BANKING, f"{BANKING}-test-{index:04d}", row["text"], label, None))
    return Dataset(BANKING, tuple(items), intents, {})


def load(name: str, cache_dir: Path) -> Dataset:
    if name == CLINC:
        return load_clinc(cache_dir)
    if name == BANKING:
        return load_banking77(cache_dir)
    raise ValueError(f"unknown dataset {name!r}; expected one of {DATASETS}")
