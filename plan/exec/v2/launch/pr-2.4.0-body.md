## Why

The first runs of 2.3.0 on a whole machine gave `CANNOT TELL` for a reason the tool could
have avoided: it compared the model and effort used most over the whole window, which was
a model no longer in use. Claude Code also deletes session files after 30 days by default
(`cleanupPeriodDays`), so the before period could never fill.

## What changes

- **The setting compared** is the model and effort with the most main-thread responses
  after the split (method `arci-logs/2`, design record `docs/design/0017-logs-2.md`).
- **`--keep`** (opt-in) saves each day's counts, dates and the setting's names to
  `~/.realornoise/days-1.json`, so that days outlive the vendor's retention. It holds no
  log text, prompt or path. `--keep-dir DIR` moves it; `--ignore-kept` skips reading it.
  The promise holds for runs at most 29 days apart.
- A failed `--keep` write leaves a table directory it created in place, empty. The tool
  never removes a directory.
- **`CANNOT TELL`** now shows the usable days so far and the earliest date a test is
  possible.
- **The printed limit** states one measured figure: the largest wrong `REAL DROP` rate of
  the rule as built in the self-check's correlation, weekly-cycle and regime cells,
  362/2000 = 0.181000 [0.164743, 0.198480], regime-switching days, 14 days after against
  16 before, seed 18112185. Work in phases can break the 2.5% bound.
- **The documented command** is `uvx --python 3.14 realornoise` (Codex compresses sessions
  idle for 7 days; Python 3.14 reads them).
- Nine Codex effort names, client versions after the split, two related tools named in the
  README in their own words.
- A guard against log-format changes: tests for three 2026 format incidents, and a daily
  workflow that compares the latest client versions with the checked ones.
- Trust items: Dependabot, CodeQL, a workflow audit (zizmor), a hash-pinned `uv`, a SciPy
  oracle job for the exact rank test, a threat model page, a contributing guide.

`arci verdict` and `arci run` are unchanged. `arci-logs/1` records stay readable.

## What it cannot show

A cause, answer quality, or a change to a model. With a short history the usual answer is
still `CANNOT TELL`. No published evidence ties these measures to answer quality.

## How it was checked

- Record 0017 and the statistics went through three review rounds (29, 11 and 5 findings)
  before any code.
- A spike had to pass first: with setting changes, wrong `REAL DROP` stayed at 287 to 380
  of 20,000 against a limit of 566.
- Blind acceptance tests written from the records alone by an agent that did not see the
  code: 236 cases, on Python 3.13 and 3.14. Their first run found two product defects,
  both fixed.
- Self-check: 32 of 32 gates, each gated cell at exactly 20,000 simulated histories, seed
  base 18112026, about 66 minutes. Every exact-margin cell also gates the moved measure's
  own finding (largest 466/20,000 against 566).
- Five adversarial checks of the build, each finding reproduced by a second agent before
  it counted: 15, 11, 12, 5 and 8 findings, none critical or high. None touched the
  statistics, a published figure or the privacy rules. Four rounds found the same kind
  of fault in the write path (a failing run removed a directory another run was about to
  use), so the rule was dropped instead of patched again: the tool never removes a
  directory, and output names that begin with `.realornoise-` are refused. After that,
  about 900 groups of real overlapping processes (up to 12 at once) lost no row, hung
  nowhere and removed nothing. Dispositions: decision D-22 on the records branch.
- Both wheels built locally and run through the release smoke script on Python 3.11 and
  3.14, and through `uvx --python 3.14` (example, a refused name, `--keep`).
- Hosted CI on the mirror branch `sprint/v2.4-logs2` at the same commit: 14 of 14 jobs
  (Linux and macOS, Python 3.11 and 3.14, wheel smoke, adapters, the SciPy oracle),
  CodeQL and the workflow audit, all green. Whole local suite: 5,147 passed, 21 skipped
  (optional extras; each skipped group passes in its own environment).
- Privacy tests: canary tokens, an audit hook (no socket, no subprocess, writes only to
  the paths given and, with `--keep`, the table directory), an import allow-list, a JSON
  walk scoped by field.

## Not verified

- Windows.
- A real history longer than a few weeks (the kept table is new; its promise is checked on
  generated histories only).
- The daily client-version workflow has not run yet (it runs on a schedule or by hand).
  CodeQL, the workflow audit and the SciPy oracle job ran once, green, on the mirror
  branch `sprint/v2.4-logs2`; they have not run on `main`.
- The directory lock on file systems without `flock` (the tool then goes on without it;
  two overlapping `--keep` runs can then fail with the write error).
- A run interrupted from the keyboard during the write can leave a `.realornoise.out-`
  temporary file beside a report. The record says so; no file is left half written.

## Re-freeze (record 0017)

Released for change: `docs/STATISTICS_LOGS.md`, `src/arci/logs/schema.py`,
`tests/acceptance/test_logs.py`, `pyproject.toml`, `uv.lock`. Newly pinned:
`docs/design/0017-logs-2.md`. Record 0016 and the other 70 hashes are unchanged; 76 files
are pinned.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
