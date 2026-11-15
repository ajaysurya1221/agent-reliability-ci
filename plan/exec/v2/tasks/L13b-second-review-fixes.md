# L13b: fixes after the second review (of the L13a fixes)

Read `AGENTS.md`. Work only in `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs` (branch
`v2/logs`; the L13a changes are in the working tree, uncommitted: build on them). Change no
git state. Never open anything under `~/.claude` or `~/.codex`. Do not edit files listed in
`FROZEN.sha256`, `tests/acceptance/`, `bench/selfcheck_logs.py` or
`docs/results/logs-selfcheck.md`, and do not run the full self-check again (its report is
final). You are the only agent in the worktree. Plain words, short sentences, no sales
wording, no em dashes.

The review is `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/L13b-review-workflow.json`
(22 findings; 12 confirmed by a second agent, 10 minor and unverified). Every item below was
decided by the orchestrator. From now on `docs/design/0016-logs.md` and
`docs/STATISTICS_LOGS.md` in the worktree are the records of authority (the drafts under
`plan/` are history); you edit them here exactly as stated.

## You own

`src/arci/logs/cli.py`, `report.py`, `html.py`, `schema.py` (and `decide.py` only if item 7
needs a function moved), their unit tests and snapshots under `tests/unit/logs/`,
`tests/unit/docs/test_logs_docs.py`, `README.md`, `docs/design/0016-logs.md`,
`docs/STATISTICS_LOGS.md`, `docs/LOG_FORMATS.md`, `docs/recipes/logs.md`,
`docs/RELEASING.md`, `plugins/realornoise/skills/realornoise/SKILL.md`,
`integrations/codex/skills/realornoise/SKILL.md`, `integrations/codex/README.md`,
`packages/realornoise/README.md`, and the tests that compare those files.

## Code

1. **The same output file under two spellings.** Two output options that name one file must
   give the usage error `Two output options name the same file.` (exit 3, nothing written,
   nothing left behind) also when the file does not exist yet and the two spellings differ
   only in letter case or Unicode form on a file system that folds them (the default macOS
   volume: `out.txt` and `OUT.txt`; `café.txt` in NFC and NFD). On a file system that keeps
   them apart they are two files and both are written. Do not guess the file system from
   the platform. One way that is exact everywhere: before installing, create each target
   that does not exist with an exclusive create (`O_CREAT | O_EXCL`); a second exclusive
   create that fails because the file exists, or a created file that `samefile`s another
   target, is the duplicate; remove the placeholders you created and report the usage
   error. Tests: the two macOS cases, skipped with a stated reason when a probe in
   `tmp_path` shows the volume keeps the spellings apart; a test that two distinct new files
   are both written; no placeholder or temporary file remains after the error.
2. **Permissions.** An existing output file keeps its permission bits after a successful
   run. A new output file gets what the process's umask gives a new file (0644 under umask
   022), not 0600. Use `os` calls; no subprocess. Tests for both.
3. **Rollback.** When installing fails, every target is restored in its own `try`, so one
   failed restore does not stop the others; a backup whose restore failed is kept on disk,
   not deleted. Test with two injected failures.
4. **Rendering errors.** Render every output before the block that maps failures to
   `Requested output could not be written.`; only a failure while staging, installing or
   restoring files gives that text. A failure in rendering gives `Internal error.` as it
   does without output options. Test.
5. **ERROR and its notices.** Under ERROR there is no result, so F9 and F17 print without
   their second sentence: `Compressed Codex files not read (Python 3.14 is needed): {k}.`
   (followed by the existing next line `To read them: uvx --python 3.14 realornoise`) and
   `Files that could not be read: {k}.` This holds in text, Markdown and HTML. The HTML page
   shows these notices for an ERROR tool (today it shows none). Tests in all three formats;
   regenerate the snapshots concerned.
6. **`no_logs` when a directory was given.** When the tool's directory option was given
   (`--claude-dir` or `--codex-dir`), the F5 `no_logs` text is
   `No session logs found for {Tool} under the directory given with {flag}. Or try: realornoise --example`
   (`{flag}` is `--claude-dir` or `--codex-dir`). Without the option the text stays as it
   is. The directory itself is never printed. Tests for both tools.
7. **The day-table digest is checked.** `ToolDecision` validation recomputes the day-table
   digest from the stored fields (the same content `decide.day_table_digest` hashes) and
   rejects a record whose `day_table_sha256` differs, with a named reason in the style of
   the existing `inconsistent_*` reasons. A tool with no day table (ERROR) is unchanged.
   Avoid an import cycle (move the digest function if needed and keep
   `decide.day_table_digest` importable). Tests: a changed day value with unchanged
   statistics, a changed day count, and a replaced digest are each rejected; every record
   the existing tests and the example produce still validates.
8. **Fixed texts are constants.** `Two output options name the same file.` becomes a named
   constant in `report.py` beside `WRITE_ERROR`, `USAGE_ERROR` and `INTERNAL_ERROR`.
9. **The agreement test covers more than one table.**
   `test_gate_tables_match_full_path_for_both_dependence_cases` (in
   `tests/unit/logs/test_selfcheck_quick.py`) runs for 10 seeds per design (5/10, 7/21,
   14/42, 28/84) and both dependence cases, with a second, unusable setting present in the
   full path, and requires identical day tables and identical results. If it is too slow
   for 28/84, use 3 seeds there and say so. `bench/selfcheck_logs.py` is not edited; if the
   test cannot be written without editing it, stop and say why.

## Records and documents (edit exactly; keep everything else word for word)

10. `docs/design/0016-logs.md`:
    - The scope sentence near the top that says outputs "hold only counts, rates and the
      names of the model and effort compared" becomes "hold only counts, rates, dates and
      the names of the model and effort compared".
    - Decision 6, reading faults: replace "A file that cannot be opened or decoded is
      counted and left out, with notice F17." with "A file that cannot be opened, or that
      fails while being read or decompressed, is counted and left out, with notice F17. A
      path that is not a regular file (a pipe, a device, a directory) is not discovered and
      is counted nowhere."
    - Decision 6, formats: replace "Lines carrying `isApiErrorMessage` count as unused
      types." with "Lines with `isApiErrorMessage` set to `true` count as unused types;
      `false` does not exclude a line."
    - Fixed texts: under F5 add the second `no_logs` text of item 6 with its condition; in
      the usage-error list add `Two output options name the same file.`; add
      `Internal error.` with "printed alone on the error stream when the program fails in a
      way no other text covers; exit 3". After F9 and after F17 add: "Under ERROR the
      second sentence is left out, since there is no result."
    - Markdown: replace "ERROR: the tool name, `ERROR` and the F5 text, and nothing else."
      with "ERROR: the tool name, `ERROR` and the F5 text, then F9 (with its next line) and
      F17 in their ERROR wording when they apply, and nothing else."
    - Text output, item 2: after "then F9 and F17 when they apply" add "in their ERROR
      wording".
    - HTML: after the sentence that the page holds the same information as the text output
      add "This includes the notices of an ERROR tool."
    - Command line and layout, after the sentence about two output options: "Two spellings
      of one file (letter case or Unicode form on a file system that folds them, a symbolic
      link, a relative and an absolute path) are the same file. An existing output file
      keeps its permission bits; a new one gets what the process's umask gives a new file."
    - Record model: add the digest rule of item 7 in one sentence.
11. `docs/STATISTICS_LOGS.md`:
    - "Checks that agents run", item 3: replace "Null simulation with the final rule,
      including setting selection, usable-day rules and the streak check:" with "Null
      simulation with the final rule, including the streak check:" and add at the end of
      the item: "The day tables are built directly from the generator. A unit test checks,
      for several seeds per design and both dependence cases, that the same generator
      passed through response and edit records and the day reduction, with a second
      unusable setting present, gives the same day table and the same result. Setting
      selection and the usable-day boundaries are checked exactly by a separate gate."
    - Power paragraph: replace "Claude Code's measures pass through response and edit
      records, day reduction, and the production decision rule." with "The day tables are
      built directly from the generator and decided by the production decision rule; a
      unit test checks them against the path through response and edit records and the day
      reduction."
    - Copy every table that comes from the self-check again from the final
      `docs/results/logs-selfcheck.md`, row for row, with every column it has. No number
      may differ, be rounded or be left from the earlier run. Check every figure quoted in
      the prose of "What the method cannot see" against the same file and correct it.
12. `README.md`: the first-screen sentence becomes "Nothing leaves your machine, and the
    output holds counts, rates, dates and the names of the model and effort compared."
    wrapped at 100 columns like its neighbours; the first screen stays at or under 250
    words (`python plan/exec/scripts/first_screen_words.py README.md` prints the count; its
    own limit of 200 is old). Every percentage in "New in 2.3" must be in the final
    self-check file; correct any that is not.
13. The same privacy wording ("counts, rates, dates and the names of the model and effort
    compared") in both `SKILL.md` files, `integrations/codex/README.md` and
    `packages/realornoise/README.md` wherever they describe what the output holds.
14. `docs/LOG_FORMATS.md`: `files_unreadable` is "Files that could not be opened, or that
    failed while being read or decompressed". State once that paths that are not regular
    files are not discovered and are counted nowhere. Remove the contradiction.
15. `docs/recipes/logs.md`: the `--tool` row says that a tool whose directory option is
    given is always requested, also when the directory does not exist. Mention the second
    `no_logs` text where the recipe explains ERROR, if it explains it.
16. `docs/RELEASING.md`, step 1: add that the five HTML goldens under
    `tests/unit/html_report/golden/` hold the version in their footer and are regenerated
    at a bump (name the exact command; read `tests/unit/html_report/` to find it), and
    correct the sentence that calls the list complete.
17. `tests/unit/docs/test_logs_docs.py`: `test_percentages_have_a_source` and
    `test_published_selfcheck_tables_are_copied_without_rounding` pass without being
    weakened. Add: every table row in `docs/STATISTICS_LOGS.md` that carries a seed appears
    as a whole line in `docs/results/logs-selfcheck.md`; neither record contains the
    sentences replaced in items 10 and 11.

## Acceptance tests

`tests/acceptance/test_logs.py` is not yours. If one of its tests fails only because of a
record change named in items 5, 6 or 10, do not work around it: list the test and the
sentence it still expects. A separate agent updates those tests from the record.

## Done when

`.venv/bin/pytest -o addopts='' -q tests/unit/logs tests/unit/docs tests/unit/plugin tests/unit/packaging tests/acceptance/test_logs.py`
passes except for `test_every_release_version_matches` (the orchestrator bumps the version
next) and the acceptance tests you listed; `.venv/bin/ruff format --check .`,
`.venv/bin/ruff check .` and `.venv/bin/basedpyright` are clean;
`.venv/bin/python bench/make_log_example.py --check` passes;
`shasum -a 256 -c FROZEN.sha256` passes. Final message: one line per item with what
changed, the commands and their last lines, the listed acceptance tests, anything you could
not do.
