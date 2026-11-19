# Rule for choosing the registered blocks, fixed before the SPEC_E results are read

Written 2026-11-19T06:13:19Z (UTC). Private working note, not a public record.
State when written: the SPEC_E calibration (synthetic data only) is still running; none of its
reports or result files has been opened by the orchestrator. No paired real values exist.
Consultant (Astra) answered ACCEPT-WITH-CHANGES; this rule adopts those changes.

Marginal information used to shape the candidates (counts only, no signal or outcome value):
sessions per repository and calendar month in the Codex confirmation half (47 repository-month
cells; weight 376 inside cells against 390 inside repositories).

## Candidates (from SPEC_E)

- P: statistic inside repositories, one sign per repository. Gate JR.
- PM: statistic inside repository x calendar month, one sign per repository. Gate JMR.

## Rule

1. Screening threshold: a test passes a null scenario when its rejection rate is at most 0.065
   at 1,000 data sets. This is a screen with binomial error (about 0.007), not proof of 0.05.
   Where the two implementers differ by more than two standard errors, the reviewer's rerun
   decides the cell.
2. Applicable nulls: E0, E1, E1s, E2, E3, E4, E6, E7, E8. A candidate must pass every one, not
   their average. E5 is a reproduction of an unrealistic layout and E9 is not a null; neither
   decides anything.
3. If PM passes every applicable null: register PM. No power veto: lower power is accepted.
4. Else, if P passes every applicable null: register P.
5. Else: register a description only. No p-value decides a sentence; the page says "described,
   not tested" and gives the measured rates as the reason.
6. Gate: required, joint, signs per repository. PM pairs with JMR when JMR can be formed in at
   least 0.90 of the data sets of every gate scenario; otherwise PM pairs with JR. P pairs with
   JR. If the paired gate's own rate under G0, G0b and G0c is above 0.065 it is still used
   (the pair is what is published), and its own rate is printed as a limit.
7. Whatever is chosen: the "no association as large as 0.15" sentence is dropped. The interval
   stays as an approximate summary and decides nothing. Results that are not an association
   are "cannot tell".
8. Branch A's sentence claims only that the association remains detectable after the fixed
   blocking on model name and session-length tercile (and month, where month blocks are used).
   It states that this does not establish added information beyond length and model. That is an
   amendment to the approved plan's "adds to them" and needs the maintainer's approval.
9. Implementation corrections to SPEC_E are allowed. No new candidate is searched for after the
   results are read.
