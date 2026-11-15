# Read-only review: draft record 0016 and the session-log statistics contract

You are a reviewer. Change no file. Do not open, list or read anything under `~/.claude` or
`~/.codex`. Read these two drafts in this repository:

- `plan/exec/v2/logs/STATISTICS_LOGS-draft.md`
- `plan/exec/v2/logs/0016-logs-draft.md`

For background on how the project writes contracts, skim `docs/STATISTICS_OUTCOMES.md` and
`docs/design/0015-imported-outcomes.md` (use `git show origin/main:<path>` if they are not in
the checkout). Field facts about the two log formats are in
`plan/exec/v2/tasks/L0-logs-spike.md`.

The drafts specify a new command that reads local coding-agent session logs, reduces them to
one value per measure per day, and compares days after a split date with days before it,
answering REAL DROP, NO DROP or CANNOT TELL with a stated bound on each wrong answer. The
project's fixed principles: honest claims only, every assumption that is not checked is
printed, no claim that anything improved, no claim of cause, exact arithmetic in decisions,
no random numbers in decisions.

Try to break the drafts. In particular:

1. **The proof.** Is the p-value with strict counting and the no-ties reference distribution
   valid under exchangeability with arbitrary ties? Is Claim 1 right as stated, including the
   union bound, the usable-day filter (a day is usable when it has enough responses), the
   choice of model and effort by response counts in the after period, the default split that
   depends on the newest day, and the self-check? Is Claim 2 right: the margin move, the
   monotonicity step, the all-must-pass rule, the precedence of REAL DROP? Does assumption A3
   make sense for a median of token counts and for shares bounded in [0, 1]? Give a concrete
   counterexample for anything that fails.
2. **The measures.** `repeated_value_share` uses the most common positive value pooled over
   all usable days of both periods: does that keep the test valid under A1? Does the
   usable-day rule for `edit_failure_share` (its own count) cause trouble when measures have
   different day sets? Is the 5 and 10 minimum-day rule applied per measure or per tool, and
   is that clear? Are any day values undefined (a day with no positive reasoning count), and
   what should happen?
3. **Windows and dates.** Local calendar days, daylight-saving changes, sessions that cross
   midnight, logs with timestamps in the future, a `--since` date with no later day: what is
   ambiguous?
4. **Fixed texts against the contract.** Does every sentence the user reads say exactly what
   the contract supports, no more? Flag any wording that implies cause, quality, or
   improvement, or that a reader would take as "the vendor changed the model".
5. **Privacy contract.** Find a path by which a string from a log could reach an output, an
   error or the sealed record under the rules as written.
6. **Implementability.** Anything an implementer would have to guess: tie handling in the
   median, rounding in the rendered table, the order of tools, exit codes with two tools,
   what "typical day" is, the digest input.
7. **Simpler or stronger.** If a simpler rule gives the same guarantees, or a small change
   gives clearly more power at the stated sizes without weakening the bound, say so
   concretely. Do not propose new features.

Output: a numbered list of findings, most serious first. For each: where (file and section),
what is wrong, a concrete counterexample or reason, and the exact change you recommend. Then a
short list of what you checked and found sound. No praise, no summary of the drafts.
