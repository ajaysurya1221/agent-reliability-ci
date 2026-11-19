# Log-signals study, first reported half: the check of step 6

19 November 2026. A note of procedure. It states no result and adds no number to the page.

## What ran

- Stage 1 on the first half: every one of the twelve check counts equals its registered
  figure (`checks_confirmation.json`, commit `7b46061`).
- Stage 2 ran twice from the same inputs with one start time. The two files are equal byte
  for byte. `result_confirmation.json` is the result file (commit `e1c1b03`).
  `result_confirmation.second.json` is the second run's file, kept as it was written; it is
  the same bytes. Two equal files show equality. They do not prove by themselves that two
  runs happened; that rests on the orchestrating agent.
- `check_result.py` accepts the result file.

## What the separate agent checked

An agent that did not run the analysis read the committed files only.

- **Recount.** Every number on a draft of the page comes from the result file or the checks
  file, in the registered format. The headline equals the registered sentence with its
  brackets filled. Nothing the registration lists as printed is missing.
- **Condition 1.** On `v2/phase0`: the registration commit is an ancestor of the
  implementation-record commit, and that one of the commit that holds the result file. The
  code digest in the result file is the one in the implementation record. The start time is
  later than the implementation record's commit date, and the check counts were committed
  before the start.
- **Conditions 2, 3 and 4**, as far as committed files show them: met.
- **Verdict:** every condition met for the first half.

What it could not do: recompute any `rho_bar`, the sign count, the weight share or the
leave-one-out range. The paired table is private, as the registration says. It did not run the
tests again.

## The disclosure check

The result file holds nothing per session and nothing per repository. The agent's verdict is
a pass on the rules as written. It named three leftovers. The consultant (a second model, read
only) judged all three to be inside the registered rules. They are written here so that a
reader does not have to find them.

1. **More than one block without weight.** Rule 5 accepts that the possible weight minus the
   printed `W` shows the size of the blocks that carry no weight. Its sharper sentence speaks
   of exactly one repository block. When the difference in weight equals the difference in the
   number of repositories, a reader learns the session count of each of those repositories,
   not of one. That is the same residual, and rule 2 names it as its exception.
2. **The weight of one side of the sign count.** The printed `W` and the printed share of
   weight above 0 give, by subtraction, the approximate weight of the repositories below 0.
   When fewer than 10 repositories are on a side, that is a figure for fewer than 10
   repositories. Rule 5 does not name it. It is a number of units of weight, which the rules
   call structure, and it gives no `rho` for those repositories. Both inputs are on the
   registered list of printed numbers.
3. **The sessions inside weight-carrying blocks.** This printed count enters the same
   arithmetic as the weight. Together with counts the registration prints, it can show how
   many cells without weight there are and how many sessions they hold. Rule 5 speaks of the
   weight and not of this count. It shows no value of any session.

One more limit. The number without the repositories that share an identified user is printed
alone, as rule 4 requires. So nothing committed shows the weight behind it. The code prints
that number only if its floor is met; no reader can check that from the result file.

## What follows

Step 7 of the registration: the same unchanged code runs on the second half.

The maintainer set, on 19 November 2026, a working date of 21 November 2026 for finishing
the study. The registered dates are unchanged; finishing earlier is inside them.
