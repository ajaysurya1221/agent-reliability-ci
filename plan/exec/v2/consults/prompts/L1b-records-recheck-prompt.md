# Read-only recheck: revised record 0016 and session-log statistics contract

You are a reviewer. Change no file. Do not open, list or read anything under `~/.claude` or
`~/.codex`.

Read `plan/exec/v2/consults/L1-records-review-codex.md` (your earlier 13 findings), then the
revised drafts `plan/exec/v2/logs/STATISTICS_LOGS-draft.md` and
`plan/exec/v2/logs/0016-logs-draft.md`, and `plan/exec/v2/spikes/L0-logs/ORCHESTRATOR.md`
(why a streak check replaced the half-split self-check).

1. For each of the 13 findings say RESOLVED, PARTLY or OPEN, with one line of reason. For
   PARTLY and OPEN give the exact text change still needed.
2. Attack the new parts: the streak check (an exact runs test on a measure's usable
   before-days at 1/10, after which a streaky measure is not tested); the result ladder with
   per-measure findings; the claim that the streak check only removes findings so both bounds
   stand; the closed-vocabulary rule for model names; the rule that a measure without enough
   days does not block a REAL DROP from another measure; the exit-code mapping; the record
   model's null rules. Give a concrete counterexample for anything that fails.
3. Check the two drafts against each other: every fixed text, reason code, finding name and
   field named in one must exist in the other with the same meaning. List each mismatch.
4. List anything an implementer would still have to guess.

Output: a numbered list, most serious first, each with where, what, why and the exact change.
End with one line: `OPEN FINDINGS: <n>`. No praise, no summary of the drafts.
