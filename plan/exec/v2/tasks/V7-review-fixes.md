# V7: fixes from the adversarial review (ARCI v2.2.0)

You are the implementer. Work only in `/Users/ajay/Developer/.arci-worktrees/wt-v2.2`
(branch `v2.2/integration`). `AGENTS.md` rules as before: no frozen file edited, no git
commands that change state, no network, no new dependencies, `.venv/bin/*` directly.

Do not edit anything under `docs/`, `README.md`, `CHANGELOG.md`, `tests/acceptance/` or
`examples/`: the orchestrator and a documentation writer own those and are working in them now.

Files you own: `src/arci/outcomes.py`, `src/arci/outcome_report.py`, `src/arci/importers/*.py`,
`src/arci/cli.py` (the verdict commands only), `bench/export_outcomes.py` if a fix needs it,
and tests under `tests/unit/outcomes/` (not `real/`).

Four reviewers, each checked by a skeptic who reproduced the finding, confirmed the defects
below. Fix each, and add a unit test that fails before the fix and passes after.

## Blockers

B1. **An output can overwrite an input.** `_outcome_paths` in `cli.py` compares
    `Path(...).resolve()` values. On a case-insensitive volume `--json B.CSV` is not seen as
    `b.csv`, and the baseline file is overwritten with the decision; the same holds for
    `--markdown RULE.YAML`, for `--previous`, and for hard links. Fix: an output collides (E17)
    when its resolved path equals another output's or any input's (rule, every baseline and
    candidate file, `--previous`), OR when the output path exists and `os.path.samefile` says it
    is one of those inputs, OR when two paths' resolved strings are equal after `casefold()`.
    The casefold rule may refuse two distinct files on a case-sensitive volume; that is accepted.
    Nothing may be written before this check has passed. Apply the same check to
    `verdict-rule --out` against its `--tasks` files.
B2. **A numeric Inspect score with a huge exponent hangs the command.** `inspect_log._outcome`
    turns a `Decimal` such as `1e999999999` into a `Fraction`. Fix: a numeric score that is not
    finite, or whose `Decimal.adjusted()` exponent is outside -400 to 400, or that has more than
    400 digits, is E10 for that sample (it cannot be read as pass, fail or error). Apply the same
    bound to the rule's `pass_at_least` (E15) and to `verdict-rule --pass-at-least`. Check every
    other place a number from a file becomes a `Fraction` or a big integer (rule rationals,
    `max_rounds`, `round` labels in CSV and JSONL, Inspect `epoch`) and bound each: a round or
    epoch label must be a plain decimal integer of at most 9 digits, else E6 for that file.
B3. **Control characters from task ids and paths reach the terminal.** A task id containing
    ESC sequences can clear the screen and print a fake `VERDICT: PASS`. Fix: one function,
    used for every user-supplied string printed on stdout or stderr in terminal mode (task ids,
    paths, option values, any `<value>` placeholder): every character whose
    `unicodedata.category` starts with `C` (controls, format characters including bidirectional
    overrides, surrogates, unassigned) and U+2028 and U+2029 is replaced by a visible escape
    (`\xNN`, `\uNNNN` or `\UNNNNNNNN`); a backslash already in the string is doubled so the
    escape is unambiguous. The JSON artifact keeps the original strings unchanged (JSON escaping
    already makes them safe).
B4. **Markup in task ids breaks the Markdown report.** An id beginning `<!--` hides every
    statement after it; an id beginning `#` becomes a heading. Fix, in Markdown mode: every
    user-supplied string is passed through the control-character escape of B3 and then every
    ASCII punctuation character in it is backslash-escaped; every table row, header and
    separator starts with `| ` and ends with ` |`; there is a blank line before and after every
    table and after every heading. Fixed statements and notices stay verbatim (they contain no
    user text; where a notice or reason does carry user text, only that part is escaped).
    Add a test that renders ids `<!--`, `# VERDICT: PASS (exit 0)`, `a|b`, a backtick id and an
    id with a newline, and asserts that each fixed statement still appears on its own line after
    the table and that no line of the output other than line 1 or 2 starts with `VERDICT:` or `#`.

## Major

M1. **E26 is raised too early.** `decide_outcomes` calls `_prospective_round_count` and raises
    E26 before the E27 check and before input validation, so a longer predecessor hides E1 to
    E6 and E27. The record's order is: step 3 `--previous` structure (E24, E25, E27); step 4
    input files; step 5 across files; step 6 the comparison, E26 first, then E23 and E28. Delete
    the early check (and `_prospective_round_count` if nothing else needs it) and correct the two
    unit tests that assert the wrong order (`test_e26_precedes_e27`,
    `test_e26_precedes_input_outcome_error`).

## Minor, fix as well

m1. CSV: a completely blank line (as `echo >> file` leaves at the end) is skipped, as blank
    lines already are in JSONL. A line that has delimiters but too few fields is still E6.
m2. CSV: when the header has `round` and some rows have an empty `round` cell while others have
    a value, that is E14 (round on some rows and not others), as in JSONL. All rows empty is E14
    too (the header promises a label the rows do not carry).
m3. The terminal overflow line must not point at outputs that were not requested. New text:
    `<n> more such tasks: add --markdown PATH or --json PATH for the full table`.
m4. `arci verdict --help` and `arci verdict-rule --help`: give every option a one-line help
    string, and set the usage line of each to the record's grammar (so RULE, `--baseline` and
    `--candidate` read as required unless `--example` is given). Help text must not claim more
    than the record does; `--example` is described as "run on the packaged order-desk outcomes".
    Running `arci verdict` with no arguments prints one stderr line that names what is missing
    (the existing E16 text is fine) and exits 3.
m5. The rule loader accepts only plain decimal integers: `010`, `0b1000`, `0x10`, `1_000` and
    the YAML 1.1 sexagesimal form must not be read as integers. Implement by restricting the
    custom loader's implicit integer resolver to `[-+]?(0|[1-9][0-9]*)`, so those spellings
    arrive as strings and fail the field's type check (E15).

## Not to change

The validation order otherwise, every fixed text of the record other than the overflow line,
the JSON artifact's fields, verdicts and digests for inputs that were accepted before.

## Acceptance criteria

- `.venv/bin/pytest tests/acceptance/test_outcomes.py tests/unit/outcomes tests/unit/docs
  tests/unit/cli tests/acceptance/test_cli.py -q` passes. If an acceptance test in
  `tests/acceptance/test_outcomes.py` now fails because of a ruling above, do not edit it and do
  not weaken the fix: report the test name and why.
- One new unit test per item B1 to B4, M1, m1 to m5. For B1 the test must work on both
  case-sensitive and case-insensitive volumes (use a hard link for the same-file case and a
  case-variant name for the casefold case). For B2 the test must finish in under two seconds.
- `arci verdict --example` still begins with F1 then `VERDICT: BLOCK (exit 1)`, and both
  exported study runs still reproduce their stored verdicts (`tests/unit/outcomes/test_export.py`).
- `.venv/bin/ruff format --check`, `.venv/bin/ruff check`, `.venv/bin/basedpyright` clean;
  `shasum -a 256 -c FROZEN.sha256` all OK.

## Final message

Files changed; test command and last lines; for each item one line saying what you did; any
acceptance test that now fails and why; anything unclear; risks.
