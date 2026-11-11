"""Exact attainable floors, including the terminal partial checkpoint."""

from __future__ import annotations

from suite_stats import Plan, classify, count_wealth


def verdict(n: int, losses: int, wins: int, plan: Plan) -> str:
    return classify(*count_wealth(n, losses, wins, plan), plan.alpha)


def decision_floors(plan: Plan) -> dict[str, int | dict[str, int | None] | None]:
    """Floors are within the plan horizon; None means unattainable by its cap.

    Loss rows mean exactly k differences -1, all remaining differences zero.
    They describe checkpoint wealth, not every ordering's first-stop outcome.
    Loss tolerance at a horizon is reported both with zeros and with all other
    differences +1, avoiding an implicit assumption about compensating wins.
    """
    if plan.rule.name == "adaptive":
        raise ValueError("fixed stakes required")
    looks = [n for n in range(1, plan.max_pairs + 1) if plan.checkpoint(n)]

    def first(losses: int | None, wins: bool, target: str) -> int | None:
        return next(
            (
                n
                for n in looks
                if (losses is None or n >= losses)
                and verdict(n, n if losses is None else losses, n if wins else 0, plan) == target
            ),
            None,
        )

    def tolerance(n: int, gains: bool) -> int | None:
        if verdict(n, 0, n if gains else 0, plan) != "PASS":
            return None
        lo, hi = 0, n + 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if verdict(n, mid, n - mid if gains else 0, plan) == "PASS":
                lo = mid
            else:
                hi = mid
        return lo

    return {
        "earliest_possible_pass": first(0, True, "PASS"),
        "all_zero_pass": first(0, False, "PASS"),
        "pass_with_losses_and_zeros": {str(k): first(k, False, "PASS") for k in (1, 2, 3, 5)},
        "earliest_block": first(None, False, "BLOCK"),
        "max_losses_with_zeros": {str(n): tolerance(n, False) for n in (200, 400)},
        "max_losses_with_wins": {str(n): tolerance(n, True) for n in (200, 400)},
    }


def validate_plan(plan: Plan) -> None:
    if plan.rule.name == "adaptive":
        raise ValueError("fixed stakes required")
    if verdict(plan.max_pairs, 0, 0, plan) != "PASS":
        raise ValueError("max_pairs is below the all-zero PASS floor")
