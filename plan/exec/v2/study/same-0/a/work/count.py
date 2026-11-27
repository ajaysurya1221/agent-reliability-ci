"""Run from the current folder with python3 -I -B work/count.py."""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

INPUT = Path("input")
ARMS = ("baseline", "candidate")
MODELS = ("q2", "q4", "q9", "g12")
CONDITIONS = ("clean", "null")
DAYS = ("d1", "d2")
SLOTS = tuple(f"M{i}" for i in range(1, 6))
THRESHOLDS = {1: 1, 3: 3, 5: 4}


def rows(path):
    with path.open() as handle:
        for line in handle:
            yield json.loads(line)


def size_rounds(path):
    paired = defaultdict(lambda: defaultdict(dict))
    seen = set()
    for row in rows(path):
        trial = row["trial_id"]
        assert trial not in seen, (path, trial)
        seen.add(trial)
        number = int(re.match(r"^r([0-9]+):", trial)[1])
        pair = paired[number][row["pair_id"]]
        arm = row["arm"]
        assert arm in ARMS and arm not in pair, (path, trial)
        pair[arm] = (row["task_id"], row["outcome"] == "PASS")
    assert sorted(paired) == list(range(1, len(paired) + 1)), path
    counts = []
    for number in sorted(paired):
        pairs = paired[number].values()
        assert len(pairs) == 8, (path, number)
        assert all(set(pair) == set(ARMS) for pair in pairs), (path, number)
        assert all(pair["baseline"][0] == pair["candidate"][0] for pair in pairs)
        assert len({pair["baseline"][0] for pair in pairs}) == 8
        counts.append(tuple(sum(pair[arm][1] for pair in pairs) for arm in ARMS))
    return counts


def summarize(blocks, threshold):
    deltas = [b["candidate_passes"] - b["baseline_passes"] for b in blocks]
    return dict(blocks=len(deltas), fewer=sum(d < 0 for d in deltas),
                same=deltas.count(0), more=sum(d > 0 for d in deltas),
                drop=sum(d <= -threshold for d in deltas),
                gain=sum(d >= threshold for d in deltas))


def size_counts():
    runs = {f"size0-{day}-{model}-{cond}": (model, cond)
            for day in DAYS for model in MODELS if model != "g12" or day == "d1"
            for cond in CONDITIONS}
    paths = sorted((INPUT / "size0").glob("*/trials.jsonl"))
    assert {p.parent.name for p in paths} == set(runs)
    blocks = defaultdict(list)
    per_run = []
    primary = []
    for path in paths:
        run = path.parent.name
        rounds = size_rounds(path)
        assert len(rounds) >= 3
        run_counts = {}
        for width in THRESHOLDS:
            run_counts[str(width)] = len(rounds) // width
            for start in range(0, len(rounds) - width + 1, width):
                baseline, candidate = map(sum, zip(*rounds[start:start + width]))
                row = dict(run=run, first_round=start + 1, last_round=start + width,
                           baseline_passes=baseline, candidate_passes=candidate)
                blocks[width].append(row)
                if start == 0 and width == 3:
                    d = candidate - baseline
                    result = "drop" if d <= -3 else "gain" if d >= 3 else "neither"
                    primary.append(dict(row, trials_per_side=24, difference=d, result=result))
        per_run.append(dict(run=run, rounds=len(rounds), blocks_by_width=run_counts))
    totals = Counter(r["result"] for r in primary)
    summary = []
    for width, threshold in THRESHOLDS.items():
        by = blocks[width]
        summary.append(dict(
            width=width, trials_per_side=8 * width, threshold_passes=threshold,
            overall=summarize(by, threshold),
            by_condition={c: summarize([r for r in by if runs[r["run"]][1] == c], threshold)
                          for c in CONDITIONS},
            by_model={m: summarize([r for r in by if runs[r["run"]][0] == m], threshold)
                      for m in MODELS}))
    return dict(primary_totals={k: totals[k] for k in ("drop", "gain", "neither")},
                primary_rows=primary, secondary=summary, per_run=per_run,
                three_round_blocks=blocks[3])


def board_counts():
    by_run = []
    root = INPUT / "board0-clean"
    expected = {f"board0-{d}-{s}-clean" for d in DAYS for s in SLOTS}
    assert {p.parent.parent.name for p in root.glob("*/*/trials.jsonl")} == expected
    for run in sorted(expected):
        _, day, slot, _ = run.split("-")
        paths = sorted((root / run).glob("*/trials.jsonl"))
        assert len(paths) == 16, run
        different = 0
        for path in paths:
            a, b = list(rows(path))
            assert a["task_id"] == b["task_id"] == path.parent.name
            assert a["trial_id"] != b["trial_id"]
            different += a["outcome"] != b["outcome"]
        by_run.append(dict(run=run, day=day, slot=slot, pairs=len(paths), different=different))

    def tally(group):
        return {k: sum(r[k] for r in group) for k in ("pairs", "different")}

    return dict(overall=tally(by_run), by_slot={s: tally([r for r in by_run if r["slot"] == s])
                                                for s in SLOTS},
                by_day={d: tally([r for r in by_run if r["day"] == d]) for d in DAYS},
                per_run=by_run)


def table(headers, data):
    def line(cells):
        return "| " + " | ".join(map(str, cells)) + " |"
    return "\n".join([line(headers), line(["---"] * len(headers)), *map(line, data)])


def markdown(report):
    totals = report["primary_totals"]
    out = ["# Same-0 independent count",
           f'With identical configurations, {totals["drop"]} of 14 three-round comparisons showed the second copy ten points or more behind the first, and {totals["gain"]} of 14 showed it ten points or more ahead.',
           f'{totals["neither"]} of 14 showed neither. Each side had 24 trials. Difference is candidate passes minus baseline passes.',
           "## Primary rows"]
    def block_cells(r):
        return [r["run"], f'{r["first_round"]}–{r["last_round"]}', r["baseline_passes"],
                r["candidate_passes"]]
    cols = ["Run", "Rounds", "Baseline passes", "Candidate passes"]
    out.append(table(cols + ["Difference", "Result"],
                     [block_cells(r) + [f'{r["difference"]:+d}', r["result"]]
                      for r in report["primary_rows"]]))
    out.extend(["## Secondary counts",
                "Each block starts after the previous complete block within that run. Trailing rounds shorter than the chosen width are omitted. Drop and gain use inclusive thresholds of 1, 3 and 4 passes at widths 1, 3 and 5."])
    data = []
    for s in report["secondary"]:
        for label, counts in [("All", s["overall"]), *s["by_condition"].items(),
                              *s["by_model"].items()]:
            data.append([s["width"], label, *counts.values()])
    out.append(table(["Rounds per block", "Group", "Blocks", "Fewer", "Same", "More",
                      "Drop ≥10 pp", "Gain ≥10 pp"], data))
    out.extend(["## Complete blocks per run",
                "Verified eight trials per side in every round, with one trial per side for each of eight paired task IDs.",
                table(["Run", "Rounds", "Width 1", "Width 3", "Width 5"],
                      [[r["run"], r["rounds"], *r["blocks_by_width"].values()]
                       for r in report["per_run"]])])
    b = report["board0_clean"]
    out.extend(["## Board-0 clean task-pairs",
                "Each cell gives pairs with different stored outcomes divided by task-pairs counted."])
    def frac(t):
        return f'{t["different"]}/{t["pairs"]}'
    data = []
    for slot in SLOTS:
        data.append([slot, *[frac(r) for r in b["per_run"] if r["slot"] == slot],
                     frac(b["by_slot"][slot])])
    data.append(["All", *[frac(b["by_day"][d]) for d in DAYS], frac(b["overall"])])
    out.extend([table(["Model slot", "Day 1", "Day 2", "Both days"], data),
                "## Every complete three-round block",
                table(cols, [block_cells(r) for r in report["three_round_blocks"]]),
                "## Interpretation",
                report["interpretation"],
                "The registration reports 7 PASS, 7 INCONCLUSIVE and 0 BLOCK for the released rule. These stored verdicts used different budgets. The block counts are descriptive and reuse tasks across rounds."])
    return "\n\n".join(out) + "\n"


report = size_counts()
report["board0_clean"] = board_counts()
report["round_check"] = dict(rounds_checked=sum(r["rounds"] for r in report["per_run"]),
                             baseline_trials_per_round=8, candidate_trials_per_round=8)
report["registered_stored_verdicts"] = {"PASS": 7, "INCONCLUSIVE": 7, "BLOCK": 0}
report["interpretation"] = ("No ambiguity affects the counts. Size-0 scores a stored PASS as one. "
                            "Board-0 compares the two stored outcomes within each run and task. "
                            "Only PASS and FAIL occur in the supplied Board-0 records, so comparing "
                            "PASS status also gives the same count.")
Path("counts.json").write_text(json.dumps(report, indent=2) + "\n")
Path("counts.md").write_text(markdown(report))
print(report["primary_totals"])
for s in report["secondary"]:
    print(s["width"], s["overall"], s["by_condition"], s["by_model"])
print(report["board0_clean"])
