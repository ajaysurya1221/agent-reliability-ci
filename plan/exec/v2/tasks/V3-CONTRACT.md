# V3 contract: what the implementation and the blind acceptance tests both rely on

Source of truth, in this order: `docs/design/0015-imported-outcomes.md` (the record),
`docs/STATISTICS_OUTCOMES.md`, then this file for what those two do not pin. If this file and
the record disagree, the record wins and the disagreement is reported, not worked around.

## Entry point

- Tests call `arci.cli.main(argv: list[str]) -> int` in process, as the existing acceptance
  tests do, and read `capsys` and files. No subprocess is needed.
- `main(["verdict", RULE, "--baseline", F..., "--candidate", F..., ...])`,
  `main(["verdict", "--example", ...])`, `main(["verdict-rule", "--tasks", F..., "--out", P, ...])`
  with the grammar of the record's "Command grammar".
- Return values: 0 PASS, 1 BLOCK, 2 INCONCLUSIVE, 3 ERROR. `verdict-rule` returns 0 when it
  wrote the rule and 3 otherwise. `main` never raises and never prints a traceback.

## Where text goes

- A decision reached by inference (PASS, BLOCK, INCONCLUSIVE, or an ERROR raised at a round
  end) prints its report on stdout and nothing on stderr.
- A validation ERROR (steps 1 to 6 of the record's ordered list) prints exactly one line on
  stderr, `error: <fixed reason>`, and nothing on stdout.
- stdout report, line by line at the top: when the rule declares `fixed_before_runs: false`,
  line 1 is F1 and line 2 is the verdict line; otherwise line 1 is the verdict line. The verdict
  line is `VERDICT: <PASS|BLOCK|INCONCLUSIVE|ERROR> (exit <code>)`. After it, in any layout: the
  reasons, the rule digest, the per-round table, every string in `statements` and every string
  in `notices`, each verbatim on its own line or lines without re-wording. Tests assert the
  first one or two lines exactly and the presence of fixed strings; they do not assert layout.
- `--markdown PATH` writes the same content as Markdown. Its first non-empty line is F1 when
  the declaration is false, and the fixed strings appear verbatim (not split by markup).
- `--json PATH` writes the sealed `OutcomeDecision` as one JSON object with the record's field
  names, plus `record_sha256`. It is written for every decision, ERROR included, once step 1
  (command line and paths) has passed. For a step 1 failure nothing is written.
- `verdict-rule` prints F13 on stdout after writing the rule.

## Statements and notices

- `statements`, in order: F1 (only when a valid rule declares false), F2, F3, F4 (only when
  inputs were validated; `<k>` is `rounds_supplied`), F5 and F6 (only when the declaration is
  true). The fixed empty template for an ERROR before inference holds F2 alone when no input was
  read, and F2 then F4 is NOT used there: the template has no `rounds_supplied`, so a
  pre-inference ERROR after inputs were read holds F2 alone as well. (This narrows the record's
  wording; it is the simplest reading and is reported as such.)
- F6 renders `<alpha>` as the rule's canonical rational string and `<bound>` as alpha/2 in
  lowest terms, for example `at alpha = 1/20, a wrong PASS and a wrong BLOCK each have
  probability at most 1/40`.
- `notices`, in order when they apply: W1; F12; F7; F8 or F9; F10; F14. F11 is a label in the
  report beside the errored-pair count, not a notice.
- F7 is printed for every decision reached by inference; F8 or F9 only for INCONCLUSIVE.

## Rule file

- YAML mapping with the record's fields. `verdict-rule` writes every field explicitly
  (defaults expanded) so that the file reads as a complete registration.
- The rule digest is `arci.hashing.hash_record` of the expanded rule as a mapping of the
  record's field names to canonical values (rationals as lowest-terms strings, `tasks` sorted,
  absent optional fields omitted).

## Python names (for unit tests and reuse; acceptance tests prefer the CLI)

- `arci.outcome_schema`: `OUTCOMES_SCHEMA_VERSION = "arci-outcomes/1"`, `NORMALISATION = 1`,
  models `OutcomeRule`, `OutcomeDecision`, `OutcomeInput`, `OutcomeRoundDigest`,
  `OutcomeRoundLook`, `OutcomeTaskCounts`.
- `arci.outcomes`: `load_rule(path) -> OutcomeRule` (raises `OutcomeError` carrying the fixed
  reason), `rule_sha256(rule) -> str`, `round_outcomes_sha256(tasks, baseline, candidate) -> str`
  where each arm argument maps task id to `"pass" | "fail" | "error" | None`,
  `decide_outcomes(rule_path, baseline, candidate, *, fmt="auto", previous=None)
  -> OutcomeDecision` which never raises.
- `arci.suite_gate.walk_rounds` and `arci.suite_stats.check_rule_plan` exist already (commit
  `d266ceb`); the imported path must decide through them and through nothing else.

## Fixtures

- Real tool outputs: `tests/unit/outcomes/real/` (Inspect JSON, pytest JUnit). The `.eval`
  files and the promptfoo files there are used only to test refusals (E7, E8 or wrong shape).
- Tests write their own CSV and JSONL inputs into `tmp_path`.
