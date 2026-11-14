# 0015: v2.2.0, a verdict from imported outcomes

Record by the orchestrator (Claude Fable 5.2), 2026-11-14. Implementation by Codex from briefs
under `plan/exec/v2/tasks/`. Plan approved by the maintainer on 2026-11-14. Revised twice the same
day after two read-only reviews (`plan/exec/v2/consults/V0-records-review.md`, 14 findings, and
`V0b-records-recheck.md`, which cut the scope). Release parts follow 0014. No frozen file is
changed by this record; the re-freeze below is made at the release.

## Why

A person who already has pass/fail results from another evaluation tool gets ARCI's
baseline-against-candidate verdict from them with one command, without writing tools, tasks or a
checker. Four feature releases brought no users and the set-up cost is the barrier. `evalsig` on
PyPI already offers a verdict from imported results; ARCI does not claim to be the only one and
compares nothing. What this path has: one rule in one file, exact rational arithmetic, a margin for
"not worse", and a path to ARCI's own runner.

## Decision

1. **A new record kind, `arci-outcomes/1`.** The suite store is not used: a `SuiteManifest` needs
   arm specs, a toolset or MCP server and a contract, and a sealed `TrialEnvelope` is the record of
   a trial ARCI ran. Fabricating those would forge recorded trials, so imported outcomes get their
   own sealed decision record and no store. `docs/STATISTICS_OUTCOMES.md` states the statistical
   contract and cites the proof in `docs/STATISTICS_SUITE.md`.

2. **The decision rule is the suite rule, unchanged.** `SuiteRule` with alpha default 1/20, margin
   `delta` default 1/10, stakes (1/4, 1/2), threshold 2/alpha; two one-sided betting tests in exact
   rational arithmetic; looks only at complete round ends; the verdict ladder of
   `suite_gate._round_verdict` without its hard-violation step. PASS means "not worse by the margin
   or more"; it cannot show an improvement is real and no output or release text may say it does.

3. **Preregistration, declared in the rule.** The bound requires that the rule and its task list
   were in fact fixed before either evaluated arm ran. The author declares that in a required
   boolean `fixed_before_runs`; ARCI does not verify it and a false declaration leaves no trace.
   `arci verdict-rule` always writes `false`, because it derives the rule from files that already
   exist; the author edits the file when the rule really did come first. With `true`, F3's
   conditions, F5 and F6 print and the verdict reasons are the suite's. With `false`, F1 is the
   first line of every output, F5 and F6 do not print, and the two crossing reasons render as F15
   and F16, at the top level and in each history entry; this is a rendering rule for this path
   only and `walk_rounds` is untouched. The verdict
   and the exit code are identical either way. The rule digest and the decision seal are not: the
   declaration is a rule field, so the two cases are different registrations.

4. **Mapping.** A cell is a task id, a string; a user with fault conditions or variants puts them
   in the id, and ARCI does not parse ids. A round is one complete pass of every registered task by
   both arms. A format carrying its own round label supplies the round from that label; file
   position supplies it only for a format carrying none, and then F12 prints. Statistical
   parameters come only from the rule.

5. **The rule file.** YAML, modelled exactly in "Record models". Every value that can change a
   verdict is in it. Defaults are expanded before hashing and the rule digest is `hash_record` of
   the expanded rule. A malformed rule gives the fixed empty template, an ERROR decision whose
   `rule_sha256` is null (E15), so no output may promise a digest unconditionally.

6. **Validation precedes inference; the stop bounds inference only.** Every supplied input is read,
   hashed, parsed and structurally validated before any wealth is advanced, and a structural fault
   anywhere is ERROR. Inference then runs round by round to the first non-INCONCLUSIVE round. The
   errored-pair tolerance is an inference-time rule, checked at each complete round end to the
   stopping round and nowhere else; it is not a structural check. Rounds after that round
   contribute to no count and the record keeps only their `outcomes_sha256`; F10 says how many were
   excluded. A round label outside 1 to `max_rounds` is E3: excess rounds are refused, not
   truncated. Every count in the record and in a report, per round and per task, covers rounds 1
   through `last_round_evaluated`, and F11 labels the errored-pair count with that round so it
   cannot be read as a total over everything supplied.

7. **Fewer rounds than `max_rounds` may be supplied.** With no crossing the verdict is INCONCLUSIVE
   and the report prints F7, which every decision reached by inference prints, then F8 or F9: the
   smallest number of further complete rounds of non-errored ties that would cross, computed
   exactly from the current counts, or that no such round exists inside the registered rounds. F8
   and F9 print for INCONCLUSIVE only. Ties are not the fastest route, so the figure is neither a
   floor nor a ceiling, and the arithmetic threshold and the next permitted look are different
   numbers.

8. **`--previous DECISION.json`.** Re-running later with more rounds under the same rule is the
   intended use, and this option binds the earlier rounds. Every supplied round gets
   `outcomes_sha256`, defined exactly as

       hash_record({"normalisation": 1, "outcomes": [[arm, task_id, outcome_or_null], ...]})

   over every registered arm and task position of that round, `null` where an outcome is absent,
   sorted by arm then task id, so a missing outcome differs from an explicit `error`. Any change to
   id canonicalisation, scorer selection or outcome mapping raises `normalisation`, which the
   decision records. The predecessor is validated before anything is compared: readable, sealed,
   rounds contiguous from 1, a digest present for every round it supplied, same `normalisation`
   (E24, E27); not an ERROR decision (E25). Once this call's inputs are validated it must not hold
   more rounds than this call (E26), its rule digest, recomputed from its embedded rule, must equal
   this call's (E23), and every round it supplied must have the same digest here (E28). It
   establishes nothing else: not that any run happened, not preregistration, not that the
   predecessor is authentic, not that another campaign was not run and discarded. Without it
   nothing binds the earlier rounds.

9. **Outcome values** are `pass`, `fail` and `error`. Infrastructure failures must be `error`;
   recording one as `fail` breaks condition (e) and ARCI cannot detect it. A missing outcome in a
   supplied round is an errored pair, scored as the suite scores errored pairs, against both tests,
   to `max_errored_pairs`, then ERROR. Nothing is averaged, picked or dropped.

10. **Commands.** `arci verdict`, `arci verdict-rule` and `arci verdict --example`, with the
    grammar in "Command grammar". The example reads packaged data: the outcomes of the order-desk
    study's run 1, exported from its store, 96 task ids, `max_rounds` 5, round-1 counts 26 / 70 / 0,
    BLOCK at round 1. Its rule declares `fixed_before_runs: false` and prints F14: the study's own
    suite rule was registered before its run (`docs/results/order-desk-study.md`), but this
    outcomes rule was written afterwards. A second console command `agent-reliability-ci` shares
    the entry point, so `uvx agent-reliability-ci verdict --example` works. One snippet reproduces
    the example's round-1 wealths and item 7's two numbers:

        .venv/bin/python - <<'PY'
        from fractions import Fraction as F
        from arci.suite_stats import (SuiteRule, crossed, default_max_errored_pairs,
                                      default_max_rounds, wealth, wealth_text)
        def rule(n, r):
            return SuiteRule(F(1, 20), F(1, 10), (F(1, 4), F(1, 2)), n, r,
                             default_max_errored_pairs(n, r))
        ex = rule(96, default_max_rounds(96))
        p, b = wealth(26, 70, 0, ex)
        print("example:", ex.max_rounds, ex.max_errored_pairs, wealth_text(p), crossed(p, ex),
              wealth_text(b), crossed(b, ex))
        ru, done = rule(50, 8), 50
        ties = next(m for m in range(351) if crossed(wealth(0, done + m, 0, ru)[0], ru))
        look = next((r - 1, r * 50 - done) for r in range(2, 9)
                    if crossed(wealth(0, r * 50, 0, ru)[0], ru))
        print("ties:", ties, "next look:", look)
        PY

    It prints `example: 5 5 1.92124e-03 False 1.56229e+02 True`, matching the study's published
    0.0019 and 156.2, then `ties: 29 next look: (1, 50)`: with 50 tasks, eight registered rounds and
    50 ties, 29 further ties cross arithmetically but the next permitted look is one more complete
    round of 50 pairs, and F8 reports the look.

## Formats

Four. JUnit and Inspect were read from real outputs of the tools themselves
(`tests/unit/outcomes/real/README.md`); CSV and JSONL are ARCI's own, so their fixtures are written
with the implementation and are evidence about nothing else.

**Inspect AI logs, JSON form.** Exactly one log per arm; more than one is E9. Its rounds are its
epochs and it supplies `eval.config.epochs` of them. A path ending `.eval` is E7. The pairing id is
the sample `id`; an integer id is canonicalised to its decimal string, and an id appearing as both
an integer and a string is E13. One scorer serves the whole import: the rule's `score` names it, a
log with more than one scorer and no `score` is E11, a `score` absent from `eval.scorers` is E12,
and the first score present is never chosen. The header's `eval.config.epochs`,
`eval.dataset.sample_ids` and `eval.scorers[].name` must be present and must agree with the samples.
A sample with an `error` object is `error`; an absent selected score on a sample that did not error
is a missing outcome. `"C"` is pass, `"I"` is fail, a boolean is itself, a number is read only
through `pass_at_least`, anything else is E10. A duplicate (sample, epoch) is E2, never resolved as
a retry; a registered sample absent from an epoch is a missing outcome.

**JUnit XML.** Root `<testsuite>` or `<testsuites>`, every test case below it visited recursively
once. The file is decoded as UTF-8, a byte-order mark allowed; bytes that are not valid UTF-8, or
an XML declaration naming another encoding, are E6, and the refusal of `<!DOCTYPE` and `<!ENTITY`,
also E6, runs on the decoded text. The id is `classname::name`, both parts non-empty (E29), unique
in the file including delimiter collisions (E2). One file is one round for its arm, from file
position. `<failure>` is fail, `<error>` is `error` and a `<skipped>` case is `error`; when status
children coexist `<error>` or `<skipped>` outranks `<failure>`, which outranks a pass. There is no
exception for an unregistered id: an id not in the rule is E1 wherever it occurs, skipped or not.
`verdict-rule` lists every id it finds, skipped ones included, and the recipe says to deselect
tests at the source rather than in the rule. Repeat suffixes such as pytest-repeat's `[i-n]` stay
literal ids: pairing fails against an unsuffixed inventory, and suffixes discovered into the rule
become distinct cells.

**Neutral CSV and JSONL.** UTF-8, a byte-order mark allowed. CSV is comma-delimited with standard
double-quote escaping and a header row; JSONL is one object per non-blank newline-delimited record.
The fields are `task_id`, `outcome` and optionally `round`; nothing else is read, so the rule's
`score` and `pass_at_least` are Inspect-only. `outcome` is exactly `pass`, `fail` or `error` in
lower case, anything else E10, and ids must be strings and are not coerced. Within one file either
every row carries `round` or none does, and a mixture is E14; when none does, the file's position
among its arm's files is its round. A duplicate header, a duplicate key in one record, a malformed
row and a non-finite number are E6.

**An input with no records** is E6 in every format: an empty or whitespace-only file, a CSV with
a header and no rows, a JSONL file with no object, a JUnit file with no test case, an Inspect log
with no samples. A file that has records but lacks some registered tasks is not this case; those
are missing outcomes.

**Choosing the parser.** `--format auto`, the default, maps by extension only: `.csv` csv, `.jsonl`
jsonl, `.xml` junit, `.json` inspect, `.eval` E7, any other extension E8. Nothing inspects content.
An explicit `--format` applies to every file in the call.

## Validation and errors

One ordered list. Validation stops at the first failure and reports it, exit 3, with its fixed
reason on stderr and no traceback.

1. **Command line and paths.** A repeated option (E20); `--example` with any other input (E21); a
   missing or empty `--baseline` or `--candidate` (E16); an output path equal to another output path
   or to any input path, compared after resolution (E17); an output whose parent directory does not
   exist (E18); for `verdict-rule`, an `--out` that exists (E22).
2. **Rule fields**, in the order of "Record models" (E15 for any of them).
3. **`--previous` structure** (E24, E25, E27).
4. **Input files**, in argument order, baseline before candidate, each file's records in file
   order: E1, E2, E6, E7, E8, E9, E10, E11, E12, E13, E14, E29 as the format sections define them.
5. **Across files**: a round label outside 1 to `max_rounds` (E3); rounds not contiguous from 1
   (E4); arms not supplying the same set of rounds 1 to k (E5).
6. **The `--previous` comparison**: E26, which needs this call's round count, then E23 and E28.

W1 is printed, not fatal. The errored-pair tolerance is not on this list: it is checked during
inference and gives the inherited ERROR reason. Artifacts are written after the decision is
complete, `--json` then `--markdown`; a write failure is E19, exit 3, and any artifact already
written is left on disk as it is.

## Record models

Both live in `src/arci/outcome_schema.py`. In the rule file, unknown keys, duplicate keys and
explicit nulls are refused, and defaults are expanded before the digest, so two spellings of one
rule give one digest. The decision record may hold null exactly where the model says so. The rule,
`OutcomeRule`:

| Field | Type | Default | Constraint |
|---|---|---|---|
| `schema_version` | string | none | exactly `arci-outcomes/1` |
| `suite_id` | string | none | the frozen `SuiteId` pattern |
| `fixed_before_runs` | boolean | none, required | a declaration, never verified |
| `alpha` | rational string | `1/20` | lowest terms, 1/1000000 to 1/2 |
| `margin` | rational string | `1/10` | lowest terms, strictly between 0 and 1 |
| `stakes` | list of rational strings | `[1/4, 1/2]` | 1 to 8, increasing, each in (0, 1) |
| `max_rounds` | integer | `ceil(400 / n)` | at least 1, and `n * max_rounds <= 100000` |
| `max_errored_pairs` | integer | `ceil(n * max_rounds / 100)` | 0 to `n * max_rounds` |
| `tasks` | list of strings | none | at least 1, non-empty, unique, stored sorted |
| `score` | string | absent | non-empty when present; Inspect only |
| `pass_at_least` | rational string | absent | a finite rational, sign allowed; Inspect only |

Field order, first failure reported: `schema_version`, `suite_id`, `tasks`, `alpha`, `margin`,
`stakes`, `max_rounds` with the 100,000-pair cap, `max_errored_pairs`, `score`, `pass_at_least`,
`fixed_before_runs`, then `check_rule_plan`. `tasks` is early because `n` gives two defaults; the
cap belongs to `max_rounds` as a bound on that field, and is stated here because it lives in the
frozen `SuiteManifest`, not in `SuiteRule`. `pass_at_least` has its own finite-rational parser,
sign allowed, separate from the positive-only suite rationals, and its comparison is inclusive. A
one-round rule gets W1 and nothing else; there is no acknowledgement flag here.

The decision, `OutcomeDecision`, sealed like other ARCI records:

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | exactly `arci-outcomes/1` |
| `rule_sha256` | string or null | null exactly when the rule was malformed |
| `rule` | `OutcomeRule` or null | null with `rule_sha256`; rationals as canonical strings |
| `normalisation` | integer | the version the round digests were taken under |
| `inputs` | list of `OutcomeInput` | argument order, baseline before candidate |
| `rounds_registered` | integer | `max_rounds`; 0 in the fixed empty template |
| `rounds_supplied` | integer | complete rounds found in the inputs |
| `last_round_evaluated` | integer | the last round inference reached, 0 if none |
| `round_digests` | list of `OutcomeRoundDigest` | ascending by round, every supplied round |
| `history` | list of `OutcomeRoundLook` | ascending, rounds 1 to `last_round_evaluated` |
| `tasks` | list of `OutcomeTaskCounts` | sorted by `task_id` |
| `stopped_at_round` | integer | the last round evaluated; 0 for every ERROR, as the suite has |
| `verdict` | Verdict | PASS, BLOCK, INCONCLUSIVE or ERROR |
| `exit_code` | integer | 0, 1, 2, 3 in that order |
| `reasons` | list of strings | the verdict reasons |
| `statements` | list of strings | the standing texts, in print order |
| `notices` | list of strings | the situational texts, in print order |
| `previous_sha256` | string or null | the predecessor's seal, null without `--previous` |

- `OutcomeInput`: `path` as given, `sha256`, `arm`, `format` (`csv`, `jsonl`, `junit` or
  `inspect`), `rounds` (ascending integers).
- `OutcomeRoundDigest`: `round`, `outcomes_sha256`.
- `OutcomeRoundLook`: `round`, `pairs`, `counts` (`minus`, `zero`, `plus`, `errored`),
  `pass_wealth`, `block_wealth`, `pass_crossed`, `block_crossed`, `verdict`, `reasons`.
- `OutcomeTaskCounts`: `task_id`, `pairs`, `baseline_successes`, `candidate_successes`, `counts`.

An ERROR raised during inference, the tolerance exceeded or both tests crossed, keeps the history
through that round, sets `last_round_evaluated` to it and `stopped_at_round` to 0, as the suite has.
The **fixed empty template** carries every ERROR raised before inference: `rule` and `rule_sha256`
null for a malformed rule and filled in otherwise, `normalisation` current, `inputs`,
`round_digests`, `history` and `tasks` empty, `rounds_registered`, `rounds_supplied`,
`last_round_evaluated` and `stopped_at_round` 0, verdict ERROR, exit code 3, `reasons` holding the
one fixed reason, `statements` holding F2 alone, `notices` empty, `previous_sha256` null. F4
never appears in it: the template has no supplied rounds to name.

Only the rule digest and each round's `outcomes_sha256` are the same on every machine for the same
rule and the same normalised outcomes. The decision seal also covers the input file hashes and the
paths as given, so it is machine-specific by design. All are integrity checks, not signatures.

## Command grammar

    arci verdict RULE --baseline FILE... --candidate FILE...
                      [--format auto|csv|jsonl|junit|inspect]
                      [--previous DECISION.json] [--json PATH] [--markdown PATH]
    arci verdict --example [--json PATH] [--markdown PATH]
    arci verdict-rule --tasks FILE... --out RULE
                      [--format ...] [--score NAME] [--pass-at-least RATIONAL]
                      [--suite-id ID] [--alpha RATIONAL] [--margin RATIONAL]
                      [--max-rounds N] [--max-errored-pairs N]

Each option appears at most once. `--example` excludes every other input, `RULE`, `--baseline`,
`--candidate` and `--previous` included. `verdict-rule` writes a rule whose `tasks` are the ids it
found, deduplicated across files and repetitions after duplicate observations in one file have been
refused; whose `suite_id` defaults to `imported-outcomes`; whose `fixed_before_runs` is always
`false`; and whose other values are the defaults or the options given. It applies no round budget to
what it reads, because discovering an inventory is not a run, and there is no option to set
`fixed_before_runs`: the author edits the written file, which is the point of the declaration. CI
invocation is the command, its exit code and `--json`; the recipe shows the verdict in a workflow
step and appends the Markdown to the step summary.

## Fixed text

Each string is printed verbatim; placeholders are in angle brackets, and the strings longer than
this file's line limit are wrapped here and nowhere else. F1 to F6 are the standing texts, placed in
`statements` in that order; the rest are situational and go in `notices`, except F13, which
`verdict-rule` prints, and F15 and F16, which are verdict reasons.

- **F1** `Descriptive verdict: the rule file declares it was written after outcomes existed. The
  error bound is not claimed.`
- **F2** `Imported outcomes: ARCI did not run these trials. No fault injection, fault accounting,
  tool outcomes or replay.`
- **F3** `The error bound depends on six conditions ARCI cannot check: (a) the rule and its task
  list were fixed before either evaluated arm ran, which the author declares in the rule file;
  (b) outcomes are independent across tasks and rounds, with no response cache shared across pairs
  or rounds; (c) each task behaves the same in every round; (d) pairing and logical round order
  were fixed before outcomes were observed, and no registered round was omitted or replaced;
  (e) infrastructure failures are labelled error, not fail; (f) the protocol was fixed before
  execution and both arms were graded by the same criterion.`
- **F4** `ARCI checked the rule, the file structure of every input, the task ids against the rule,
  and that both arms cover rounds 1 to <k>. It did not verify execution or any of those conditions.`
- **F5** `Under (a) to (f) and the assumptions of docs/STATISTICS_SUITE.md, a wrong PASS and a
  wrong BLOCK each have probability at most alpha/2.`
- **F6** `at alpha = <alpha>, a wrong PASS and a wrong BLOCK each have probability at most <bound>`
- **F7** `<k> of <N> registered rounds supplied`
- **F8** `if every further pair is a non-errored tie, PASS is reached after <r> more complete rounds
  (<p> more pairs)`
- **F9** `if every further pair is a non-errored tie, PASS is not reached inside the registered
  rounds`
- **F10** `<n> rounds after the stopping round were excluded from inference`
- **F11** `errored pairs through round <k>`
- **F12** `rounds were assigned from the order of the files given`
- **F13** `task ids were extracted from the given files. This does not establish that the rule
  preceded the data. Fix the rule before either evaluated arm is run.`
- **F14** `the packaged example's rule was written from the study's stored outcomes, so it declares
  fixed_before_runs: false; the study's own suite rule was registered before its run.`
- **F15** `PASS threshold crossed`
- **F16** `BLOCK threshold crossed`
- **E1** `unknown task id: <id>`
- **E2** `duplicate outcome for <arm> <id> round <n>`
- **E3** `round <n> is outside 1 to <max_rounds>`
- **E4** `rounds are not contiguous from 1`
- **E5** `arms supply different rounds: baseline <rounds>, candidate <rounds>`
- **E6** `unreadable or unsupported input: <path>`
- **E7** `.eval files are not read: run inspect log dump FILE.eval > FILE.json and pass the JSON`
- **E8** `<path> has no recognised extension: use --format`
- **E9** `<arm> supplies more than one Inspect log`
- **E10** `outcome <value> for <id> cannot be read as pass, fail or error`
- **E11** `<path> reports more than one scorer and the rule sets no score`
- **E12** `the rule's score <name> is absent from <path>`
- **E13** `task id <id> appears as both an integer and a string`
- **E14** `<path> gives round on some rows and not others`
- **E15** `the rule file is not a valid arci-outcomes/1 rule: <reason>`
- **E16** `no input files were given for <arm>`
- **E17** `<path> is both an output and an input, or is named twice`
- **E18** `the directory for <path> does not exist`
- **E19** `cannot write <path>`
- **E20** `<option> was given more than once`
- **E21** `--example takes no other input`
- **E22** `--out already exists: <path>`
- **E23** `the previous decision was made under another rule: <digest>`
- **E24** `the previous decision is not a usable arci-outcomes/1 decision: <reason>`
- **E25** `the previous decision is an ERROR decision: <path>`
- **E26** `the previous decision supplied <k> rounds; this call supplies <j>`
- **E27** `the previous decision used normalisation <v>; this call uses <w>`
- **E28** `round <n> differs from the previous decision`
- **E29** `a test case has an empty classname or name: <path>`

Inherited from the suite kernel and printed unchanged. Verdict reasons: `non-inferiority
established` (PASS), `regression established` (BLOCK), both replaced by F15 and F16 in descriptive
output; `no test crossed` (INCONCLUSIVE); `both tests crossed` and `errored pairs exceed
max_errored_pairs` (ERROR, at a round end). Rule-plan reasons inside E15: `budget cannot establish
PASS for a candidate that never differs` and `PASS unreachable once max_errored_pairs is used`.
Warning **W1**: `max_rounds below 3: few looks`.

## Kernel extraction

One kernel decides both paths. Only the inference loop moves; validation, digests, cell aggregation
and ERROR construction stay with their existing callers.

    def walk_rounds(rule: SuiteRule, per_round_counts: Iterable[RoundIncrement],
                    ) -> tuple[RoundLook, ...]: ...
    def check_rule_plan(rule: SuiteRule) -> tuple[str, ...]: ...

- `RoundIncrement` carries one complete round's five integer increments: `minus`, `zero`, `plus`,
  `errored` and `candidate_hard_violations`. The last is read by the ladder's second step, is
  cumulative, counts violations on errored trials, and is always zero here. `RoundLook` carries the
  round-result fields except `trials_sha256`, and keeps both crossing flags even when ERROR
  overrides the inference.
- `walk_rounds` holds exactly cumulative count accumulation, incremental wealth through one
  `RunningWealth` per direction, the crossing flags, the verdict priority and the stop at the first
  non-INCONCLUSIVE round.
- `evaluate_rounds` keeps its signature and output: group by `pair_round`, build the increments,
  call `walk_rounds`, attach each round's `trials_sha256`. It does not aggregate cells; `_cells`
  stays with `decide_suite` over all supplied trials, or archived ERROR records would change.
- Unchanged after the extraction: an incomplete trailing round produces no look; no complete round
  returns an empty tuple; supplied trials after a stop remain suite ERROR; an inconclusive suite
  stop before the cap remains ERROR; every ERROR has `stopped_at_round` zero. `check_suite_plan`
  keeps its exception type, its order of the two plan errors and its warning tuple, and delegates
  to `check_rule_plan`. Neither file is frozen, and v1 and suite output must stay byte-identical to
  2.1.0 apart from the version string; that is checked at integration.

## Frozen changes in this release

- `pyproject.toml`: version 2.2.0; keywords gain testing, llm, regression, ci, pytest; the second
  console script `agent-reliability-ci`; `authors` with the maintainer's name as it stands in
  `NOTICE`, no email. `uv.lock`: the project's own version entry only.
- `docs/AGENT_SEMANTICS.md`: one added section, proposed in the appendix below. No existing
  sentence changes meaning for v1 or for suites.
- `FROZEN.sha256`: the entries above re-hashed; new entries for `docs/STATISTICS_OUTCOMES.md`,
  `src/arci/outcome_schema.py`, `tests/acceptance/test_outcomes*.py` and this record.
- `src/arci/__init__.py`: `__version__ = "2.2.0"` (not frozen; listed for completeness).

## What is not in 2.2.0

Cut after the second review, because the specification was growing faster than it could be kept
consistent:

- An Inspect `.eval` read directly: its entries are Zstandard-compressed, which Python reads only
  from 3.14, so the JSON form is the supported route (E7).
- Several Inspect logs for one arm: two ways to assign rounds in one format was the contradiction
  the review found, so one log per arm with its epochs as rounds is the only mode (E9).
- promptfoo, JSON and JUnit: identity modes differ between its exports and its JUnit numbers
  repeated rows, more rules than one release should carry. The fixtures stay for a later release.
- The GitHub Action's verdict mode and its pull-request comment: the exit code and `--json` serve
  CI, so a recipe does the job.
- HTML output: terminal, JSON and Markdown already carry identical qualifications.
- Content sniffing for `--format auto`: extension mapping is predictable and testable.
- Score columns in CSV and JSONL: `score` and `pass_at_least` are Inspect-only, so a neutral row
  carries an outcome and nothing that can disagree with it.
- The exception for an unregistered skipped test case: it contradicted the unknown-id rule.

Also not here: Pydantic Evals, LangSmith, DeepEval's own JSON, Phoenix, Braintrust, Langfuse and
OpenAI Evals, each undocumented or needing an account; and no `minimize`, `bundle`, `replay`,
`trace-check`, fault accounting or tool outcomes, since there is no store and no boundary record.
Everything 0013 and 0014 list as not built stays not built.

## What the release may and must not say

As in 0013 and 0014, and the permitted claims of `docs/STATISTICS_OUTCOMES.md`. In addition: never
"ARCI ran" or "ARCI tested" about imported outcomes, in any heading, post or screenshot; never that
an improvement is shown, since the rule is one-sided; no claim about injected faults, fault counts
or replay for an imported verdict. A verdict from a rule declaring `fixed_before_runs: false` may be
shown only with F1 beside it and never beside the bound, and that is what the "you already have two
result files" path always produces, so the label belongs wherever that path is shown. Any statement
that the command "tells you whether a difference is real" must carry the power table of
`docs/STATISTICS_OUTCOMES.md` in the same place, because a 50-pair look catches a 20-point drop
with probability 0.022.

## Divergences from the suite contract

1. Rounds after the stopping round are excluded from inference, where the suite gate makes them
   ERROR; excluding cannot enlarge a crossing event.
2. `max_errored_pairs` is a fraction of the registered budget, not of what was supplied, so an
   early partial import has a looser ERROR gate; the bound holds by worst-case scoring.
3. A partial import exits 2, which fails a CI job treating any non-zero exit as failure; the exit
   codes are the suite's and are not changed.
4. The round-end ladder has no hard-violation step, so every BLOCK here is a statistical BLOCK.
5. `fixed_before_runs` has no counterpart in the suite, which registers its rule before execution
   by construction.

## Appendix: proposed section for `docs/AGENT_SEMANTICS.md`

Added at the re-freeze, after "Suite experiments (`arci-suite/1`)", limited to behaviour the
acceptance tests rely on.

> ## Imported outcomes (`arci-outcomes/1`)
>
> - Not a suite: no `SuiteManifest`, store, `TrialEnvelope` or `spec_sha256`. Statistical parameters
>   come only from the rule file, whose digest is `hash_record` of the expanded rule. A cell is a
>   task id, opaque; a round is one complete pass of every registered task by both arms; a format
>   with its own round label supplies the round from it, and file position is used only for a format
>   carrying none.
> - The rule carries a required boolean `fixed_before_runs`, part of its digest, declared by the
>   author and never verified. False makes the descriptive notice the first line of every output,
>   suppresses the bound sentence and the rendered-alpha line, and renders the two crossing reasons
>   as the threshold-crossed pair of 0015's fixed text. Verdict and exit code are the same either
>   way; the rule digest and the decision seal are not.
> - Read, hash, parse and structurally validate every supplied input before any inference, in the
>   ordered list of ADR 0015, reporting the first failure as exit 3 with its fixed reason and no
>   traceback. A malformed rule reads no input and gives that record's fixed empty template.
> - A supplied round must be complete for both arms and the arms must supply the same set of rounds
>   1 to k. A missing outcome inside a round is an errored pair, scored as -1 in PASS wealth and +1
>   in BLOCK wealth through the registered tolerance, never dropped and never an observed zero. The
>   tolerance is checked at each complete round end, not during validation.
> - Decide only at complete round ends, through `walk_rounds`, and stop at the first
>   non-INCONCLUSIVE round; priority is the suite's without the hard-violation step. Every count,
>   per round and per task, covers rounds 1 to `last_round_evaluated`; later supplied rounds
>   contribute only their `outcomes_sha256`, which is
>   `hash_record({"normalisation": <v>, "outcomes": [[arm, task_id, outcome_or_null], ...]})` over
>   all registered positions sorted by arm then task id. An ERROR during inference keeps the history
>   through its round and has `stopped_at_round` 0. With `--previous`, validate the predecessor's
>   seal and cross-field consistency before comparing the recomputed rule digest and every round it
>   supplied.
> - Outcome values are `pass`, `fail` and `error`. One Inspect JSON log per arm, its epochs its
>   rounds, one selected scorer for the whole import, `"C"` pass, `"I"` fail, a boolean itself, a
>   number only through `pass_at_least`, an `error` object `error`, an absent selected score a
>   missing outcome, anything else exit 3. JUnit `<failure>` is fail while `<error>` and `<skipped>`
>   are `error` and outrank it; input is decoded as UTF-8 before `<!DOCTYPE` and `<!ENTITY` are
>   refused. CSV and JSONL rows carry `task_id`, `outcome` and optionally `round`, every row in one
>   file alike, and `--format auto` maps by extension only.
> - The decision separates `statements`, the standing texts in print order, from `notices`. An ERROR
>   raised before any input is read carries the imported-outcomes notice and its reason only; the
>   sentence naming what ARCI checked prints only when inputs were validated. Exit codes are PASS 0,
>   BLOCK 1, INCONCLUSIVE 2, ERROR 3. Only the rule digest and the round digests are
>   machine-independent; the seal also covers input hashes and the paths as given, and no seal
>   establishes execution.
