# L13a: fixes from the adversarial review

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` and follow
its rules. You are the only agent in the worktree. The full review, with evidence for every
item, is `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/L13-review-workflow.json`
(23 findings, 22 confirmed by a second reviewer). The two records were updated for the
fixes below: read record 0016 decision 6 ("Reading faults"), "Record model" (last sentence
of `MeasureDecision`), "Command line and layout", and the statistics contract's "Checks
that agents run" item 3, in their current text
(`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/`).

## You own

Everything under `src/arci/logs/`, `bench/selfcheck_logs.py`,
`docs/results/logs-selfcheck.md`, all tests and snapshots under `tests/unit/logs/`,
`tests/unit/packaging/`, `.github/scripts/wheel_smoke.sh`, `.github/workflows/ci.yml` and
`release.yml` (only for item 13), `docs/RELEASING.md`, `docs/LOG_FORMATS.md` and
`docs/design/0016-logs.md` and `docs/STATISTICS_LOGS.md` (only to carry the record changes
named below into the finished documents, word for word from the drafts). Never edit
`tests/acceptance/` or frozen files.

## Fixes (write a failing unit test first for each, then fix)

1. **Self-check gates** (finding 1): the gated null and margin cells run on exactly the
   stated number of day tables (20,000 per design, both dependence cases); no time budget
   may reduce a gated cell, and the script exits non-zero if a gated cell ran on fewer.
   Build day tables directly for these cells if that is what makes it fast enough (as
   section 4 does), and test once that the direct construction and the full path through
   `measures.build` agree. Print the count actually run in every row. Re-run the full
   self-check and rewrite `docs/results/logs-selfcheck.md`.
2. **Codex repeats** (findings 2, 12): within one file, a `token_count` whose cumulative
   usage object equals that of the previous `token_count` is a repeat: skip it and count it
   in `responses_duplicate`, whatever its timestamp and whether or not the file has a
   session id. Keep the cross-file identity rule.
3. **Record validator** (finding 3): `MeasureDecision` recomputes `p_streak`, `p_real`,
   `u_none` and `p_none` from its stored day values (with `rank_test` and the margin move)
   and rejects a mismatch.
4. **`--project`** (findings 4, 10, 14): make the path absolute with
   `os.path.abspath(os.path.expanduser(...))` before use (no other file-system access); a
   relative path then means "relative to the current directory". Test `.`, a relative
   path, `~`, a trailing slash, and a path that is a string prefix but not a parent. Leave
   Windows case rules alone and say in `docs/LOG_FORMATS.md` that `arci logs` is untested
   on Windows.
5. **Timestamps far out of range** (finding 5): a timestamp before 2000-01-01 or after
   2200-01-01 is a missing field (`lines_lacking_field`); no date arithmetic may raise.
   `run` must not exit 3 because of one line.
6. **Output files** (findings 6, 17, 18): render every requested output first; two options
   naming the same file is the usage error `Two output options name the same file.`;
   write each file to a temporary name in the target's directory and move it into place
   only after all were written; on any failure remove the temporary files, leave every
   target as it was, print `Requested output could not be written.` and exit 3.
7. **Unreadable files** (findings 11, 16): a line that is not valid UTF-8 counts in
   `lines_not_json` and the file goes on. A file is unreadable only when it cannot be
   opened, is not a regular file, or fails while being read or decompressed; then nothing
   from that file is used (buffer per file, commit on success) and it counts once in
   `files_unreadable`. F17 must be true.
8. **Symlinks, pipes, devices** (finding 9): discovery returns only regular files
   (`Path.is_file()` true); a FIFO or device is never opened. A test with `os.mkfifo`.
9. **Byte-order mark** (finding 13): a UTF-8 BOM at the start of a file is ignored for both
   tools.
10. **Presence against value** (finding 15): `isApiErrorMessage` skips a line only when it
    is `true`; the effort is the first non-empty string among `effort` and `perTurnEffort`.
11. **ERROR with unread compressed files** (finding 19): for ERROR the text and Markdown
    show F9 and F17 when they apply, as the record now says.
12. **`--tool auto` with a directory option** (finding 20): a tool whose directory option
    was given is requested even when the path does not exist.
13. **Markdown** (finding 21): no line wrapping in the Markdown output.
14. **The wheel test that never runs** (finding 22): the check of the two wheels' file lists
    must run somewhere real. Make `wheel_smoke.sh` (which CI and the release run on built
    wheels) verify that the main wheel contains `arci/logs/example/now.txt` and the two
    example log files, and that the second wheel contains only its own package, licences
    and metadata with the `realornoise` entry point; keep the unit test for local use and
    make its skip reason say where the check really runs.
15. **Version bump list** (finding 23): `docs/RELEASING.md` lists every place the version
    or the pin is written (find them all with a search for the current version), and a new
    unit test fails when any of them disagrees with `arci.__version__`. Snapshots under
    `tests/unit/logs/snapshots/` must not need regenerating at a version bump: compare
    them with the version in the first line replaced by a placeholder.
16. Carry the record changes into `docs/design/0016-logs.md`, `docs/STATISTICS_LOGS.md` and
    `docs/LOG_FORMATS.md` if those files exist in the worktree, and replace "numbers only"
    wherever a document or the README says the output holds numbers only: it holds counts,
    rates and the names of the model and effort compared (for `README.md` say so in your
    final message instead of editing it if you do not own it: you may edit that one phrase).

## Done when

`.venv/bin/pytest -q` passes (list sandbox-blocked tests), including all of
`tests/acceptance/test_logs.py`; if an acceptance test now contradicts the records because
of these fixes, do not edit it: list it with the reason. `.venv/bin/ruff format --check .`,
`.venv/bin/ruff check .`, `.venv/bin/basedpyright` clean; the full self-check passes with
exact counts; `python bench/make_log_example.py --check` passes;
`shasum -a 256 -c FROZEN.sha256` passes. Final message: one line per fix (done, or why
not), the gate table with counts, acceptance tests that fail and why, files changed.
