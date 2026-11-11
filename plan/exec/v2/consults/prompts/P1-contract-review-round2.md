You are a read-only technical consultant. Change no file and no git state.

Second round. Your first review is plan/exec/v2/consults/P1-contract-review-codex.md
(REVISE, five blocking findings, three non-blocking). The orchestrator revised
plan/exec/v2/tasks/P1-CONTRACT.md and plan/exec/v2/tasks/P1a-suite-schema-schedule-stats.md.

1. For each of your eight findings: RESOLVED, PARTLY RESOLVED or NOT RESOLVED, one line each
   with the contract line that settles it.
2. Any NEW blocking defect introduced by the revision, or one you missed, judged by the
   same standard: would an implementer and a blind acceptance-test author diverge in an
   observable way, or build something that breaks the guarantee? Read section 5 with care:
   the normalisation step, the eight ordered checks and their skip rules, the field rules
   for every decision, and the five-row outcome table.

Output under 50 lines: first line `P1 CONTRACT: ACCEPT` or `P1 CONTRACT: REVISE`, then the
two lists. Label findings KNOWN, CODE or OPINION.
