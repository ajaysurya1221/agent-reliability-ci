# Pull request text: `v2/logsignals` into `main`

Prepared for the maintainer, who opens and merges the pull request.

**Title**

```
Log-signals study: code, result page, post and README sentence
```

**Text**

```
## What changed

One registered study, run once per half. It adds no feature, changes no file under `src/`,
and makes no release.

- `bench/logsignals/`: the study's programs, a note on file formats, the comparison with a
  second implementation on simulated data, and the simulation files of the design rounds.
- `tests/unit/logsignals/`: their tests, among them the test that re-derives the published
  page from the files beside it.
- `docs/results/log-signals-study/`: the result page, the check counts and result files of
  both halves, and a data notice.
- `docs/results/log-signals-study-first-registration-ended.md`: the note that ended the first
  registration before any run.
- `docs/blog/2026-11-log-signals-study.md`: the post. It holds the page's headline sentences,
  the yardstick table, the limits, the README sentence and a link, and nothing else.
- `README.md`, under "What it does not do": the registered sentence and the reader's limit.
- `docs/results/README.md`: a pointer to the page.

The result is stated on the page, in the sentences the registration fixed before the data
were paired. This text repeats none of it.

Records, on branch `v2/phase0` under `plan/exec/v2/study/logsignals/`: the first registration
and the note that ended it, the second registration (commit `f0ef8db`), the implementation
record (commit `3f7ae3c`), the committed run files, and two notes on the check of step 6.

## How it was checked

- Whole suite: 5538 passed, 21 skipped. Study tests: 266 passed.
- `ruff format --check`, `ruff check`, `basedpyright` (strict): clean.
- The page was rendered again by a separate agent from the committed result files: the same
  bytes. The files in the published folder are byte for byte the ones on the records branch.
- Two separate agents recounted the page from the committed files and checked the
  registration's conditions for each half. They cannot recompute the numbers themselves: the
  paired table is private, as the registration says.
- The dataset is not in the repository. No agent other than the orchestrating agent opened a
  real file.

## Pinned files touched

None. `shasum -a 256 -c FROZEN.sha256`: 77 files, all the same.

- [x] This pull request does not change any file listed in `FROZEN.sha256`, or it links the
      design record that authorizes the change.

## Privacy

- [x] No session logs, log lines or log file paths are attached anywhere in this pull request.
```
