# Release page text for 2.4.0 (paste into the description box)

Open: https://github.com/ajaysurya1221/agent-reliability-ci/releases/new?tag=v2.4.0

Title: `v2.4.0: compare the setting you use now, and keep days beyond the vendor's retention`

Leave "Set as a pre-release" off and "Set as the latest release" on. Attach no files.

---

`uvx --python 3.14 realornoise` (the same as `arci logs`) reads the Claude Code and Codex session logs already on your disk, compares recent days with earlier days for the model and effort you use now, and answers `REAL DROP`, `NO DROP` or `CANNOT TELL` (exit 1, 0, 2; `ERROR` is 3). It runs no model. The tool sends nothing; installing it downloads the package.

Try it (no logs needed):

```sh
uvx --python 3.14 realornoise --example
```

On your own logs, keeping each day's counts for later runs:

```sh
uvx --python 3.14 realornoise --keep
```

### Why this release
The first runs of 2.3.0 on a whole machine gave `CANNOT TELL` for a reason the tool could have avoided: it compared the model and effort used most over the whole window, which was a model no longer in use. Claude Code also deletes session files after 30 days by default (`cleanupPeriodDays`), so the earlier period could never fill.

### Added
- `--keep` (opt-in) saves each day's counts, dates and the names of the model and effort to `~/.realornoise/days-1.json`, so days outlive the vendor's retention. It holds no log text, prompt or path. `--keep-dir DIR` moves it; `--ignore-kept` skips reading it. The promise holds for runs at most 29 days apart; a day never captured whole cannot be recovered.
- `CANNOT TELL` shows the usable days so far and the earliest date a test is possible.
- Client versions seen after the split, nine Codex effort names, and a [threat model](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.0/docs/THREAT_MODEL_LOGS.md) for the command.

### Changed
- Method `arci-logs/2`: the setting compared is the model and effort with the most main-thread responses after the split. `arci-logs/1` records stay readable.
- The documented command asks for Python 3.14, because Codex compresses sessions idle for 7 days and Python 3.14 reads them.
- The printed limit states one measured figure, the largest wrong `REAL DROP` rate of the rule as built in the [self-check](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.0/docs/results/logs-selfcheck.md)'s correlation, weekly-cycle and regime cells: 362/2000 = 0.181000 [0.164743, 0.198480], regime-switching days, 14 days after against 16 before, seed 18112185.
- `arci verdict` and `arci run` are unchanged and remain the stronger evidence.

### Fixed
- Two defects found by the blind acceptance tests (the order of equal client versions; a table path below a regular file), and the write-path defects found by two adversarial reviews (an interrupted write, two runs at once, a table of 0 bytes).

### Limits
- It shows what your logs recorded, not why. It cannot show a cause, answer quality or a change to a model: your tasks, prompts, projects and client changed too. No published evidence ties these measures to answer quality.
- With a short history the usual answer is still `CANNOT TELL`.
- When work comes in phases the 2.5% bound does not hold; the figure above is what the self-check measured, and other patterns can give more.
- Not verified: Windows; a real history longer than a few weeks; log formats older than the client versions named in `docs/LOG_FORMATS.md`.

Recipe: [docs/recipes/logs.md](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.0/docs/recipes/logs.md) · Statistics and limits: [docs/STATISTICS_LOGS.md](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.0/docs/STATISTICS_LOGS.md) · Design record: [0017](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.0/docs/design/0017-logs-2.md) · PyPI: [realornoise](https://pypi.org/project/realornoise/2.4.0/), [agent-reliability-ci](https://pypi.org/project/agent-reliability-ci/2.4.0/)

SHA-256 of the files on PyPI:
- HASHES-AFTER-PUBLISH
