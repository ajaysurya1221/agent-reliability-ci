# Pull request for the kept-table read (the maintainer merges it)

Branch `v2/kept-read-race` (`074fd7f`), cut from `main` at `901e037`. Compare link:
https://github.com/ajaysurya1221/agent-reliability-ci/compare/main...v2/kept-read-race?expand=1

Title: logs: a kept table that another run installs during the first read is read, not unreadable

---

## What

Two runs of `arci logs --keep` that started together when no kept table existed yet could
leave one run's rows out of the table. That run still succeeded, printed that the table
could not be read, and its JSON record (when `--json` was given) has
`kept_table: "unreadable"`. The rows were not lost for good while the logs were still
there: the next run with `--keep` writes them.

The cause: `kept.read` asked `stat()` and, when the path was missing, `lstat()` to tell an
absent path from a dangling symlink. A table that another run moved into place between the
two calls was taken for a path that exists and cannot be read. The first read of a run
happens before it holds the directory lock, and a run whose first read says unreadable
writes no table.

`kept.read` now reads the path again when it was absent at one call and present at the
next: four attempts at most, with no waiting. A dangling symlink, a path that is not a
regular file, a file over the size limit and invalid content stay unreadable; a missing
path and an empty file stay absent. `_execute` is unchanged.

Seen once in hosted CI (run 44098411894, `check / Python 3.11`), in
`tests/unit/logs/test_logs2.py::test_real_process_writers_preserve_all_successful_rows`.

## Limits

- A path that appears more than three times during one read (a writer interrupted after its
  move and rolled back, followed by another writer; or overlapping writers where there is no
  directory lock) can still be reported unreadable. That is safe: the run writes no table
  and says so.
- Left as it is: when the first read says absent or read and the read under the lock says
  unreadable, the write is dropped without a notice. That needs a table damaged by another
  program; this tool never writes an invalid one.

## How it was checked

- 19 new unit tests place each step of the writer between two calls of the reader by hand
  (no process, thread or sleep). 8 of them fail on the code before this change; the
  three-attempt test fails with two attempts.
- Two separate reviews. One enumerated the interleavings of reader and writer steps; one ran
  30,000 pairs of runs that start together on a fresh keep directory: the old code lost a
  successful run's rows in 17 of them, the changed code in none.
- The test that failed in CI did not fail locally on either version (150 runs each), so its
  passing is not evidence for the fix; the hand-placed tests and the stress run are.
- Not checked: Python 3.11 and 3.14, and Linux; this pull request's CI is the first run
  there.

## Pinned files touched

None.

- [x] This pull request does not change any file listed in `FROZEN.sha256`, or it links the
      design record that authorizes the change.

## Privacy

- [x] No session logs, log lines or log file paths are attached anywhere in this pull request.
      Tests and the stress run used synthetic logs only.
