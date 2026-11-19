# Log-signals study, second reported half: the check of step 6

20 November 2026. A note of procedure. It states no result and adds no number to the page.

## What ran

- Step 7 of the registration: the second half ran after the first half's result was
  committed (commit `e1c1b03`) and after the first half's check of step 6
  (`STEP6-first-half.md`).
- Stage 1 on the second half: every one of the twelve check counts equals its registered
  figure (`checks_discovery.json`, commit `a9d9920`).
- Stage 2 ran twice from the same inputs with one start time. The two files are equal byte
  for byte. `result_discovery.json` is the result file (commit `b055669`);
  `result_discovery.second.json` is the second run's file, kept as it was written. Two equal
  files show equality. That two runs happened rests on the orchestrating agent.
- `check_result.py` accepts the result file.
- The same unchanged code ran: the code digest in both result files is the one in the
  implementation record.

## What the separate agent checked

A second agent that did not run the analysis read the committed files and a draft of the
whole page, both halves.

- **Recount.** 105 checks, none failed. Every number on the page outside the registration's
  fixed texts comes from the result file or the checks file of its half, in the registered
  format. Each headline equals the registered sentence filled from its own half's file. The
  second half stands under its registered label. The page follows the registered order.
- **Condition 1 for the second half**, on `v2/phase0`: the chain of commits holds, the code
  digest matches the implementation record, and the start time is later than the
  implementation record's commit date. The check counts were committed before the start. The
  two commit dates are 2 seconds apart: in order, with no margin, and they are dates the
  committer wrote.
- **Conditions 2, 3 and 4**, as far as committed files show them: met.
- **Wording.** No sentence outside the fixed texts. Nothing compares the two halves.
- **The withheld figures.** Nothing on the page or in the result files gives away how many
  repositories of the second half show two or more identified user ids, or the largest number
  of user ids in one repository.
- **Verdict:** every condition met for the second half.

What it could not do: recompute any `rho_bar`, the sign count, the weight share, the
leave-one-out range or the number without shared users. The paired table is private. It did
not run the tests.

## The disclosure check

The agent's verdict is a pass on the rules as written. The three leftovers of the first
half's note apply here in the same way. It named two more. The consultant judged both to be
inside the registered rules.

4. **The number with and the number without the shared-user repositories.** The page prints
   the repository-block number of the first measure with its weight, and the number without
   the repositories that share an identified user with the other half. Leaving out whole
   repositories does not change the other blocks. So the two printed numbers, the floor that
   must have held for the second one to be printed, and the fact that no such number can
   exceed 1 in size together bound the number over the repositories that were left out. The
   registration's facts say how many repositories hold the shared user ids, and in the second
   half that is fewer than 10. The bound is one-sided. The value itself cannot be recovered,
   because the weight of the kept repositories is not printed; that is why rule 4 has this
   number printed alone. Rule 4 forbids isolating a number for fewer than 10 repositories, and
   no number is isolated. This leftover applies to the first half too. Whether a bound says
   anything at all depends on the printed numbers and their rounding.
5. **The two measures inside the third block definition.** A block carries weight for a
   measure only if that measure is not constant inside it, and the two measures are different
   signals. Where their printed weights and session counts differ, the difference shows the
   net number of blocks, and of sessions, that carry weight for one measure and not for the
   other. It is a net figure: blocks that count for only one measure can offset each other.
   These are counts of structure. No value of a session and no identity follows.

Neither note computes the figures a reader could derive, and neither sets the two halves side
by side.

## What follows

The page, the post and the README sentence, as the registration fixes them, in one pull
request that the maintainer opens and merges.
