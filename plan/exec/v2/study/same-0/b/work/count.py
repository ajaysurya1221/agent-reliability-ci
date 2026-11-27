"""Recompute counts from the two input trees. Run from the deliverables folder."""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

INPUT = Path("input")
ARMS = ("baseline", "candidate")
MODELS = ("q2", "q4", "q9", "g12")
THRESHOLDS = {1: 1, 3: 3, 5: 4}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def trials(path):
    for line in path.read_text().splitlines():
        row = json.loads(line)
        require(isinstance(row["outcome"], str), f"Missing outcome in {path}")
        yield row


def size_rounds(path):
    by_round = defaultdict(list)
    ids = set()
    for row in trials(path):
        trial_id = row["trial_id"]
        match = re.match(r"^r(\d+):", trial_id)
        require(match and trial_id not in ids, f"Invalid trial id in {path}: {trial_id}")
        ids.add(trial_id)
        by_round[int(match[1])].append(row)

    require(set(by_round) == set(range(1, len(by_round) + 1)) and len(by_round) >= 3,
            f"Unexpected round sequence in {path}")
    scores = []
    for number in sorted(by_round):
        rows = by_round[number]
        require(Counter(t["arm"] for t in rows) == {"baseline": 8, "candidate": 8},
                f"Unexpected arm counts in {path}, round {number}")
        pairs = [{(t["pair_id"], t["task_id"]) for t in rows if t["arm"] == arm}
                 for arm in ARMS]
        require(pairs[0] == pairs[1] and len({p for p, _ in pairs[0]}) == 8
                and len({task for _, task in pairs[0]}) == 8, f"Unmatched pairs in {path}")
        scores.append(tuple(sum(t["outcome"] == "PASS" for t in rows if t["arm"] == arm)
                            for arm in ARMS))
    return scores


def summarize(rows, threshold):
    d = [r["difference"] for r in rows]
    return dict(blocks=len(d), fewer=sum(v < 0 for v in d), same=d.count(0),
                more=sum(v > 0 for v in d), drop=sum(v <= -threshold for v in d),
                gain=sum(v >= threshold for v in d))


def size_counts():
    runs = {f"size0-{day}-{model}-{cond}": (model, cond)
            for model in MODELS for day in ("d1", "d2") for cond in ("clean", "null")
            if (model, day) != ("g12", "d2")}
    paths = sorted((INPUT / "size0").glob("*/trials.jsonl"))
    require({p.parent.name for p in paths} == runs.keys(), "Unexpected Size-0 runs")
    primary, per_run = [], {}
    blocks = {w: [] for w in THRESHOLDS}
    for path in paths:
        run = path.parent.name
        scores = size_rounds(path)
        per_run[run] = {}
        for width in THRESHOLDS:
            spans = range(0, len(scores) - width + 1, width)
            per_run[run][width] = len(spans)
            for start in spans:
                baseline, candidate = map(sum, zip(*scores[start:start + width]))
                delta = candidate - baseline
                row = dict(run=run, first_round=start + 1, last_round=start + width,
                           baseline_passes=baseline, candidate_passes=candidate, difference=delta)
                blocks[width].append(row)
                if start == 0 and width == 3:
                    label = "drop" if delta <= -3 else "gain" if delta >= 3 else "neither"
                    primary.append(dict(row, result=label))

    secondary = {}
    for width, rows in blocks.items():
        def subset(groups, index):
            return {g: summarize([r for r in rows if runs[r["run"]][index] == g],
                                 THRESHOLDS[width]) for g in groups}

        secondary[width] = dict(threshold_passes=THRESHOLDS[width],
                                total=summarize(rows, THRESHOLDS[width]),
                                by_condition=subset(("clean", "null"), 1),
                                by_model=subset(MODELS, 0))
    votes = Counter(r["result"] for r in primary)
    return dict(primary=dict(total=len(primary), drop=votes["drop"], gain=votes["gain"],
                             neither=votes["neither"], rows=primary), secondary=secondary,
                blocks_per_run=per_run, three_round_blocks=blocks[3])


def board_counts():
    run_pairs = defaultdict(list)
    base = INPUT / "board0-clean"
    runs = {f"board0-{day}-M{i}-clean" for day in ("d1", "d2") for i in range(1, 6)}
    for path in sorted(base.glob("*/*/trials.jsonl")):
        run, task = path.relative_to(base).parts[:2]
        rows = list(trials(path))
        require(len(rows) == 2 and all(t["task_id"] == task for t in rows)
                and len({t["trial_id"] for t in rows}) == 2, f"Bad Board-0 pair in {path}")
        a, b = (t["outcome"] for t in rows)
        require((a != b) == ((a == "PASS") != (b == "PASS")), f"Outcome readings differ in {path}")
        run_pairs[run].append(a != b)
    require(set(run_pairs) == runs and all(len(v) == 16 for v in run_pairs.values()),
            "Incomplete Board-0 records")

    def tally(group):
        values = [v for run in group for v in run_pairs[run]]
        return dict(pairs=len(values), different=sum(values))

    return dict(total=tally(runs),
                by_day={day: tally(r for r in runs if r.split("-")[1] == day)
                        for day in ("d1", "d2")},
                by_model={m: tally(r for r in runs if r.split("-")[2] == m)
                          for m in (f"M{i}" for i in range(1, 6))},
                by_run={r: tally([r]) for r in sorted(runs)})


def table(headings, rows):
    def line(row):
        return "| " + " | ".join(map(str, row)) + " |"
    return "\n".join([line(headings), line(["---"] * len(headings)), *map(line, rows)])


def pass_rows(rows, primary=False):
    headings = ["Run", "Rounds", "Baseline passes", "Candidate passes"]
    if primary:
        headings.extend(["Candidate minus baseline", "Result"])
    data = []
    for r in rows:
        row = [r["run"], f'{r["first_round"]}–{r["last_round"]}',
               r["baseline_passes"], r["candidate_passes"]]
        if primary:
            row.extend([r["difference"], r["result"]])
        data.append(row)
    return table(headings, data)


def render(result):
    p = result["primary"]
    b = result["board0_clean"]
    sec = []
    for w, group in result["secondary"].items():
        for name, s in [("All", group["total"]), *group["by_condition"].items(),
                        *group["by_model"].items()]:
            sec.append([w, name, *(s[k] for k in ("blocks", "fewer", "same", "more", "drop", "gain"))])
    board_rows = []
    for model in b["by_model"]:
        days = [b["by_run"][f"board0-{day}-{model}-clean"] for day in ("d1", "d2")]
        board_rows.append([model, *(f'{s["different"]}/{s["pairs"]}' for s in [*days, b["by_model"][model]])])
    board_rows.append(["All", *(f'{s["different"]}/{s["pairs"]}' for s in [*b["by_day"].values(), b["total"]])])
    return "\n\n".join([
        "# Independent Same-0 count",
        f'With identical configurations, {p["drop"]} of 14 three-round comparisons showed the second copy ten points or more behind the first, and {p["gain"]} of 14 showed it ten points or more ahead.',
        f'{p["neither"]} runs showed neither. Each side had 24 trials. A drop or gain required a difference of at least 3 passes.',
        "## Primary rows", pass_rows(p["rows"], True),
        "## Secondary counts",
        "Blocks start at round 1 within each run and omit any incomplete final block. Fewer, same and more compare candidate passes with baseline passes. Drop and gain are the subsets differing by at least ten percentage points, equivalent to 1 of 8, 3 of 24 and 4 of 40 passes. Blocks reuse tasks.",
        table(["Rounds", "Group", "Blocks", "Fewer", "Same", "More", "Drop", "Gain"], sec),
        "## Complete blocks per run",
        "Every round contained exactly eight trials per side, covering the same eight paired task IDs. Round numbers were consecutive in every run.",
        table(["Run", "1 round", "3 rounds", "5 rounds"], [[r, *v.values()] for r, v in result["blocks_per_run"].items()]),
        "## Board-0 clean pairs", "Each cell gives pairs with different outcomes divided by task-pairs.",
        table(["Slot", "Day 1", "Day 2", "Both days"], board_rows),
        "## All three-round blocks", pass_rows(result["three_round_blocks"]),
        "## Interpretation", result["interpretation"],
        "The registration reports the released rule’s verdicts as 7 PASS, 7 INCONCLUSIVE and 0 BLOCK. These figures come from the registration. The rule used a different trial budget."
    ]) + "\n"


if __name__ == "__main__":
    result = size_counts()
    result["board0_clean"] = board_counts()
    result["interpretation"] = ("Board-0’s wording permits comparing the stored outcome labels or comparing "
                                "PASS against all other outcomes. Only PASS and FAIL occurred. Both readings "
                                f'give {result["board0_clean"]["total"]["different"]} differing pairs out of 160, '
                                "with identical splits. The Size-0 thresholds and block boundaries are explicit.")
    result["verdicts_as_reported_in_registration"] = {"PASS": 7, "INCONCLUSIVE": 7, "BLOCK": 0}
    Path("counts.json").write_text(json.dumps(result, indent=2) + "\n")
    report = render(result)
    Path("counts.md").write_text(report)
    print(report.split("## Secondary counts")[1].split("## Complete blocks")[0])
    print(report.split("## Board-0 clean pairs")[1].split("## All three-round blocks")[0])
    print(report.split("\n\n")[1:3])
