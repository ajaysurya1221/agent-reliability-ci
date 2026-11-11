You are a read-only technical consultant. Change no file and no git state.

Review, before any implementation starts, the phase 1 contract for ARCI's suite gate:
- plan/exec/v2/tasks/P1-CONTRACT.md  (the contract under review)
- plan/exec/v2/tasks/P1a-suite-schema-schedule-stats.md  (the first task brief)
- plan/exec/v2/adr-0011-draft.md  (the accepted design record it must implement)
- plan/exec/v2/DECISIONS.md  (D-03 lists the orchestrator's readings of open points)
- frozen code it must fit: src/arci/schema.py, src/arci/schedule.py, src/arci/hashing.py,
  src/arci/interfaces.py; and unfrozen src/arci/gate.py, src/arci/stats.py
- reviewed reference code: plan/exec/v2/spikes/s1/suite_stats.py,
  plan/exec/v2/spikes/s1c/balanced.py, plan/exec/v2/spikes/s1c/PROOF.md, RESULTS.md

Two parties will work from the contract without seeing each other: an implementer and an
acceptance-test author. Find what would make them diverge or build the wrong thing:
1. Contradictions between the contract and ADR 0011, or between the contract and frozen code.
2. Anything that breaks the statistical guarantee as proved in PROOF.md (for example the
   errored-pair scoring, the round verdict order, the stopping rule, reading D-03 item 5).
3. Statements of fact that are wrong. Verify numerically with exact arithmetic where you
   can (the 79-pair floor; never_differs_pass_round values; that check (b) accepts the
   default tolerance at the minimum 20-cell budget; that PASS and BLOCK cannot both cross
   with errored pairs scored as specified; the 53-bit seed mask; wealth_text example).
4. Behaviour left ambiguous enough that two careful implementations would differ in an
   observable way (digest content, ids, reason strings, ERROR-decision field values,
   history contents, what evaluate_rounds returns).
5. Anything unimplementable, or needlessly complex for what v2.0 needs. Name the simpler form.
6. Does the digest rule in section 3 really bind the rule into every trial with no frozen
   edit, and is it free of circularity?

Output, under 90 lines: a verdict line `P1 CONTRACT: ACCEPT` or `P1 CONTRACT: REVISE`;
then blocking findings (each: where, what is wrong, the exact fix); then non-blocking
findings; then what you verified numerically. Label each finding KNOWN (published or
proved), CODE (read from the repository) or OPINION. Do not restate the contract.
