"""Exact ARCI projections for ten tickets and 160 pairs. No trial inputs."""

from dataclasses import replace
from fractions import Fraction as F

from arci.suite_stats import SuiteRule, never_differs_pass_round, operating_characteristics


def main() -> None:
    for margin in (F(1, 20), F(1, 10), F(3, 20)):
        rule = SuiteRule(F(1, 20), margin, (F(1, 4), F(1, 2)), 10, 16, 2)
        ties = never_differs_pass_round(replace(rule, max_rounds=40))
        for base, cand in ((F(9, 10), F(9, 10)), (F(3, 4), F(3, 4)), (F(9, 10), F(7, 10))):
            loss, win = base * (1 - cand), (1 - base) * cand
            result = operating_characteristics([(loss, 1 - loss - win, win)] * rule.n_cells, rule)
            print(
                margin,
                ties,
                base,
                cand,
                *(
                    f"{float(p):.6f}"
                    for p in (result.p_pass, result.p_block, result.p_inconclusive)
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
