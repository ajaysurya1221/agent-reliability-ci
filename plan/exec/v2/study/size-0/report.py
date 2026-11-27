"""Descriptive rows for each date, pooled over both raw-null labels."""

from math import comb
from pathlib import Path

from check_evidence import PYTHON, inspect_claims
from claims import claims_dir
from descriptors import SLOTS, Row
from records import require


def qualified_ids(clean: Row) -> int:
    return sum(
        r["trials"] > 0 and 2 * r["final_state_passes"] >= r["trials"]
        for r in clean["by_order"].values()
    )


def interval(k: int, n: int) -> tuple[float, float] | None:
    """Two-sided 95% Clopper-Pearson by inversion of the finite binomial tails."""
    require(0 <= k <= n, "invalid binomial counts")
    if not n:
        return None

    def lower(successes: int) -> float:
        if successes == 0:
            return 0.0
        lo, hi = 0.0, 1.0
        for _ in range(55):
            mid = (lo + hi) / 2
            tail = sum(comb(n, i) * mid**i * (1 - mid) ** (n - i) for i in range(successes, n + 1))
            if tail < 0.025:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    return lower(k), 1 - lower(n - k)


def report(root: Path, *, rehearsal: bool = False, python: Path = PYTHON) -> str:
    statuses, verified = inspect_claims(root, claims_dir(), rehearsal, python)
    return render(statuses, verified, rehearsal)


def render(statuses: dict[str, str], verified: dict[str, Row], rehearsal: bool) -> str:
    n_verified = sum(statuses[run] == "finished" for run in verified)
    output = [
        "rehearsal" if rehearsal else "real",
        "complete" if n_verified == 14 else "partial",
        f"starts accounted for: {sum(s != 'not started' for s in statuses.values())}/14",
        f"verified rows: {n_verified}/14",
    ]
    output.extend(f"{r}\t{s}" for r, s in statuses.items())
    for day in (1, 2):
        output.extend(
            [
                f"Day {day}",
                "slot\ttag\tcondition\tround\treached 10\tverdict (check only, not a result)\t"
                "trials\tfinal-state passes\tclean qualifying IDs/8\trated\tdelivered\t"
                "exposed\tunexposed\tread again/exposed\t"
                "percent\texact 95% interval (%)\texposed >=80\tright ID\t"
                "by order (passes/trials, delivered, exposed, read again, right ID)\t"
                "passes read again/no read again/unexposed\t"
                "unexposed trial IDs (wire reason, termination)\tdate verification",
            ]
        )
        for slot in SLOTS if day == 1 else ("q9", "q4", "q2"):
            clean: Row | None = None
            for condition in ("clean", "null"):
                run = f"size0-d{day}-{slot}-{condition}"
                if run not in verified:
                    continue
                row = verified[run]
                data = row["counts"]["pooled"]
                if condition == "clean":
                    clean = data
                r = row["round"]
                n, k = data["exposed"], data["read_again"]
                ci = interval(k, n)
                by_order = "  ".join(
                    f"{oid} {v['final_state_passes']}/{v['trials']},"
                    f"{v['delivered']},{v['exposed']},"
                    f"{v['read_again']},{v['read_again_right_id']}"
                    for oid, v in sorted(data["by_order"].items())
                )
                q = qualified_ids(clean) if clean else None
                output.append(
                    "\t".join(
                        map(
                            str,
                            (
                                slot,
                                row["model"]["tag"],
                                condition,
                                r,
                                int(r == 10),
                                row["verdict"],
                                data["trials"],
                                data["final_state_passes"],
                                f"{q}/8" if q is not None else "NA",
                                int(q >= 6) if q is not None else "NA",
                                data["delivered"],
                                n,
                                data["unexposed"],
                                f"{k}/{n}",
                                f"{100 * k / n:.1f}" if n else "NA",
                                f"{100 * ci[0]:.4f},{100 * ci[1]:.4f}" if ci else "NA",
                                int(n >= 80) if condition == "null" else "NA",
                                data["read_again_right_id"],
                                by_order,
                                "/".join(
                                    str(data[k])
                                    for k in (
                                        "passes_read_again",
                                        "passes_no_read_again",
                                        "passes_unexposed",
                                    )
                                ),
                                ", ".join(
                                    f"{tid} ({detail['reason']}, {detail['termination']})"
                                    for tid, detail in data["unexposed_details"].items()
                                ),
                                "date unverified"
                                if statuses[run] == "date unverified"
                                else "verified",
                            ),
                        )
                    )
                )
    return "\n".join(output)
