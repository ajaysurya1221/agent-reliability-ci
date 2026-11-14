# Read-only review: design record 0015 and the imported-outcomes contract (ARCI v2.2.0)

You are a reviewer. Do not edit, create or delete any file. Do not run git commands that change
state. You may run read-only commands and `.venv/bin/python` snippets to check arithmetic.

Working directory: the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2.2` (branch
`v2.2/integration`, `main` at v2.1.0 plus fixtures and two untracked draft documents).

## What to review

1. `docs/design/0015-imported-outcomes.md` (draft design record)
2. `docs/STATISTICS_OUTCOMES.md` (draft statistical contract)

They specify a new command, `arci verdict`, that reads paired pass/fail outcomes produced by
another evaluation tool (Inspect AI logs, neutral JSONL/CSV, JUnit XML, promptfoo JSON), applies
the existing suite decision rule unchanged, and prints PASS, BLOCK, INCONCLUSIVE or ERROR. No code
exists yet. Coding starts from these documents, so anything wrong or vague here becomes a defect.

## Read for context

- `docs/STATISTICS_SUITE.md` (the frozen contract these documents extend)
- `src/arci/suite_stats.py`, `src/arci/suite_gate.py` (lines 1 to 145), `src/arci/suite_schema.py`
- `docs/AGENT_SEMANTICS.md` from "Suite experiments (`arci-suite/1`)" to the end
- `tests/unit/outcomes/real/README.md` and the files beside it (real outputs of Inspect AI
  0.3.289, promptfoo 0.125.1, pytest 9.2.0 with pytest-repeat 0.9.4)
- `AGENTS.md`, `FROZEN.sha256`

## Questions, in order of importance

A. **Statistics.** Is every claim in `STATISTICS_OUTCOMES.md` correct given the proof in
   `STATISTICS_SUITE.md` and the code? In particular:
   - that the alpha/2 bound per direction survives (i) supplying fewer rounds than `max_rounds`,
     (ii) calling the command again later with more rounds under the same rule, (iii) ignoring
     rounds supplied after the first decisive round, (iv) scoring a missing outcome as an errored
     pair, (v) a tolerance `max_errored_pairs` registered against `n * max_rounds` while fewer
     rounds are supplied;
   - whether the five unchecked conditions (a) to (e) are sufficient, or whether a sixth is needed
     (for example: the same task list in both arms' runs; a pass threshold fixed in advance; the
     producing tool's own retries; dependence between baseline and candidate runs that share a
     cache or a seed);
   - whether "the estimand is about that tool's definition of a pass" hides a problem when the two
     arms were graded by different scorer versions or a model-graded scorer;
   - recompute the power table and the wealth factors yourself and report any difference.
B. **The `--previous` check and `outcomes_sha256`.** Does hashing sorted (arm, task id, outcome)
   triples per round, and refusing a call whose earlier rounds differ from a previous decision,
   close the gap it is meant to close? What does it still not catch? Is there a simpler or stricter
   design that costs no more?
C. **Kernel extraction.** Can `walk_rounds` be extracted from `evaluate_rounds` as described with
   byte-identical suite behaviour (every frozen acceptance test in `tests/acceptance/` untouched)?
   Name any behaviour of `evaluate_rounds`, `_round_verdict`, `decide_suite` or
   `check_suite_plan` the description would change, and the exact signature you would give
   `walk_rounds` and `check_rule_plan`.
D. **Formats, checked against the real files.** For each format, is the mapping to
   (task id, round, outcome) well defined and safe on the fixture files? Look for: ids that collide
   or change between arms; Inspect samples with `scores` for only some scorers, `limit` fields,
   or retried samples; promptfoo rows where `success` is false and `failureReason` is neither 1
   nor 2; JUnit files with `<testsuite>` as the root, nested suites, or duplicate
   `classname::name`; CSV dialect and encoding; what `--format auto` should do when it cannot tell.
E. **Under-specification.** List every place where two competent implementers would write
   different behaviour. For each, propose the one-sentence rule to add.
F. **Fixed text.** Is any fixed string false, ambiguous, or stronger than the contract supports?
   Is F2 accurate when alpha is not the default? Is F4's "<m> more pairs (<r> more rounds)" well
   defined when m is not a multiple of the task count?
G. **Frozen-file rules.** Does anything in 0015 require editing a frozen file before the release
   re-freeze? Is the list under "Frozen changes in this release" complete?

## Output

A numbered list of findings, most serious first. For each: severity (BLOCKER: must be fixed before
any code; MAJOR: fix in the documents now; MINOR), the exact passage quoted, what is wrong or
missing, the evidence (file and line, or the command you ran and its output), and the replacement
text or rule you propose. Then a short section "Checked and found correct" naming what you
verified. Be concrete and brief; no praise, no restating the documents.
