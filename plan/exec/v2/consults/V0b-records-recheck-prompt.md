# Read-only re-check: design record 0015 and the imported-outcomes contract, after revision

You are a reviewer. Do not edit, create or delete any file. No git commands that change state.

Working directory: `/Users/ajay/Developer/.arci-worktrees/wt-v2.2`. Ignore changes under `src/`
and `tests/unit/suite/`; another task is in progress there.

Your earlier review is at
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/consults/V0-records-review.md`
(14 findings, two of them blockers). The two documents were revised to adopt all fourteen, plus
these rulings by the orchestrator:

- a required rule field `fixed_before_runs` (a declaration by the rule's author, never verified);
  when `false` every output starts with a "Descriptive verdict" text and the error-bound sentence
  is not printed; `arci verdict-rule` always writes `false`;
- a round label above `max_rounds` stays an error, nothing is truncated;
- the per-round digest payload carries a normalisation version;
- errored pairs are counted through the stopping round only;
- promptfoo `testCase.assert` differences stay a hard error.

Re-read `docs/design/0015-imported-outcomes.md` and `docs/STATISTICS_OUTCOMES.md` in full and
answer only these:

1. For each of your 14 findings: CLOSED, PARTLY CLOSED (say what remains) or OPEN. One line each.
2. Contradictions introduced by the revision: any two passages (in either document, including
   the appendix, "Record models", "Command grammar" and "Fixed text") that now specify different
   behaviour for the same case. Quote both.
3. Anything an implementer still cannot build deterministically from these documents. For each,
   the one-sentence rule you would add.
4. Is the `fixed_before_runs` design statistically honest: is anything printed in either state
   false or stronger than the contract supports?
5. Scope check: name the three parts of this specification that cost the most to implement and
   test relative to their value for a first release, and say which you would defer to a later
   release without weakening the statistical contract.

Output: numbered answers, brief, no praise, no restating the documents. Mark any item that must
be fixed before coding starts as BLOCKER.
