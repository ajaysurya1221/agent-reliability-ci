# R3a: fixes after the adversarial review of 2.4.0

Read `AGENTS.md` in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`
(branch `v2/logs2`). Work only there. Change no git state. No network, do not call `uv`.
Never open anything under `~/.claude` or `~/.codex`, and search no memory registry. Use
only synthetic data. Plain words, short sentences, no sales wording, no em dashes. You are
the only agent editing the worktree.

The review is
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/R3-logs2-adversarial-workflow.json`
(six reviewers, each finding reproduced by a second agent: 15 findings, 14 confirmed or
partly confirmed, none critical or high). Each reviewer's scripts are under
`/private/tmp/claude-501/-Users-ajay-Developer-agent-reliability-ci/39ca2335-7a5a-47d9-a374-69d92a47e1d0/scratchpad/review24/`;
you may read them. Every item below was decided by the orchestrator.

Record 0017 was amended first (commit `d3e0697`): read its new paragraph "An interrupted
write, and two runs at once" in the section on the kept day table, the sentence about an
empty `DIR` under the options, the last paragraph of "Coverage of the bound", acceptance
item 72 as amended and the new items 74 to 77. Do not edit `docs/design/`,
`tests/acceptance/`, `FROZEN.sha256` or any version number.

## Code

1. **An interrupted write** (`src/arci/logs/cli.py`). The same-file check may still create
   empty files at new target paths to detect two spellings of one file, but it removes
   every one of them before anything is staged. A run that is killed while it stages or
   moves files must leave no empty file at a target. Test with an injected failure and
   with a simulated kill (the reviewer's `kept/t2.py` shows one way).
2. **A table of 0 bytes is `absent`** (`src/arci/logs/kept.py`): F24 does not print and a
   `--keep` run replaces it.
3. **Two runs at once.** With `--keep`: take an exclusive lock on the table directory
   (`fcntl.flock` on a descriptor of the directory; where `fcntl` or the lock is not
   available, go on without it), read the stored table again under the lock, merge with
   that, move the new table into place, then remove regular files in the table directory
   whose names begin with `.realornoise-`, and release the lock. The result of the run
   still uses the table as read at the start. The run creates no other file in that
   directory. Unit test: with an injected pause between the first read and the write,
   another writer's rows survive (acceptance item 77); a leftover `.realornoise-x` file is
   removed after a successful write and a file with another name is not.
4. **An empty `--keep-dir` value** is a malformed value: the general usage line, exit 3,
   nothing read, nothing written.
5. The privacy audit-hook test still allows writes only to the paths given and, with
   `--keep`, the table directory; extend it for the lock (no new file) and the cleanup.

## Self-check (`bench/selfcheck_logs.py`, `tests/unit/logs/test_selfcheck_quick.py`)

6. **Margin cells also gate the moved measure's own finding.** In every exact-margin cell
   of the two new gates (setting changes; competitive choice) and of the older null
   tables, count the histories in which the moved measure's own finding is `no drop`, and
   gate that count at 0.0283 beside the tool-level NO DROP. Print both columns. (The
   reviewer showed that a wrong margin for one share measure passed every gate, because
   the tool-level result needs all three measures.) Add a unit test in which a wrong
   margin for one measure makes a quick gate fail (patch the margin in memory).
7. **Gates are explicit checks.** Replace every `assert` that enforces a gate by a check
   that records the result or raises; the script must give the same verdict under
   `python -O`. Add a test that runs the quick mode with optimisation on.
8. **Dead code.** Remove `simulate()` if nothing on the real path calls it, and point
   `test_gate_count_cannot_be_reduced_by_time_budget` at the real gated path: a gated cell
   reports `generated == count`, and the gate fails when it does not.
9. **Run the full self-check again** (seed base `18112026`, the same command as in the
   file's header) and regenerate `docs/results/logs-selfcheck.md`. If a gate fails, stop
   and report; change no threshold, seed or generator. Then update every table and figure
   in `docs/STATISTICS_LOGS.md`, `README.md`, `docs/recipes/logs.md` and `CHANGELOG.md`
   that the new file changes (the new columns; any figure that moved), and `RATE_MAX`,
   `RATE_MAX_AFTER`, `RATE_MAX_BEFORE` with the snapshots that carry them if they moved.

## Documents (each sentence must be true as written)

10. `docs/STATISTICS_LOGS.md` (a pinned file released for change; edit only these):
    - item 3 of "Checks that agents run": replace the sentence that setting selection is
      "checked exactly by a separate gate" by what is true: the choice by after-period
      counts and the usable-day boundaries are checked in the self-check; the fall-back
      to the before period, the tie order of raw names, the filters of `--model` and
      `--effort` and settings present only in kept rows are held by unit and acceptance
      tests;
    - items 7 and 8: add the moved measure's own finding as a second gated count;
    - "How far the bound can fail": say "over every no-change row with rho greater than 0
      of the correlation table and every no-change row of the weekly-cycle and regime
      table", and that it is the rate of the rule as built over all generated histories;
      keep the sentence that the rate among histories that pass the streak check is
      higher, with its figure.
11. `README.md`:
    - line near "New in 2.4": the figure is "the largest wrong-REAL-DROP rate of the rule
      as built, over all histories, in the self-check's correlation, weekly-cycle and
      regime cells", not "the worst rate measured in the self-check";
    - the GitHub Action example, the roadmap paragraph and "Availability and project
      status" name 2.4.0 as the current release (`@v2.4.0`, `==2.4.0`), and no longer list
      stored log history as missing;
    - extend `test_every_release_version_matches` so that the README's current-release
      sentence and the Action pin are version locations.
12. `docs/LOG_FORMATS.md`: what changed in the readers in 2.4.0, in full: they return the
    client-version names; they also return main-thread and sub-agent responses that lack
    a model or an effort, which count only toward the context counts and the version
    list, never toward responses or day values; they take model and effort names from the
    kept table so that labels stay stable across runs. Say that the context counts can
    therefore differ from those 2.3.0 printed for the same logs, and that 2.4.0 follows
    the definition in the records. Put the same note in `CHANGELOG.md` under Changed and
    in `docs/COMPATIBILITY.md`.
13. `CHANGELOG.md`: the security checks scan every push to `main` and `sprint/**` and every
    pull request **to `main`**; add the fixes of this task under Fixed.
14. Both skills (`plugins/realornoise/skills/realornoise/SKILL.md`,
    `integrations/codex/skills/realornoise/SKILL.md`) and `docs/THREAT_MODEL_LOGS.md`:
    `realornoise` itself opens no connection and sends nothing; `uvx` downloads the
    package, and Python 3.14 if it is missing, to run it. Do not say that the command as
    a whole sent nothing. Check the README first screen and the package README for the
    same claim and word it the same way ("the tool sends nothing; installing it downloads
    the package").
15. `CITATION.cff`: the top-level `date-released` is `2026-11-16`. Add `date-released` to
    the list in `docs/RELEASING.md` step 1.
16. `docs/recipes/logs.md` and `docs/THREAT_MODEL_LOGS.md`: the new write rules (a table
    of 0 bytes is replaced; overlapping runs keep each other's rows; leftover temporary
    files are removed; an empty `--keep-dir` is refused).

## Tests

17. `tests/unit/logs/privacy/test_json_leaves.py` and `tests/unit/logs/synth_logs.py`:
    scope the JSON string walk by field. A version-shaped string is allowed only under
    `client_versions_after_shown`; the package's own version only under `arci_version`; a
    model name only under `model`; an effort only under `effort`. The synthetic logs carry
    at least one client version that matches the pattern, so the walk meets one. Add a
    test that a version-shaped string planted in another field is refused.
18. `tests/unit/docs/test_logs_docs.py`: every `k/n = p [lo, hi]` figure in
    `docs/STATISTICS_LOGS.md`, `README.md`, `docs/recipes/logs.md` and `CHANGELOG.md` must
    appear in a row of `docs/results/logs-selfcheck.md`; where the sentence names a seed,
    the figure must be in the row with that seed, and where it names a design
    ("14 days after against 16 before", "5/10"), in a row of that design. Figures cited
    to the spike (535 and 415 of 20,000) are checked against
    `/plan/exec/...` only by their literal text in the statistics document, since the
    spike report is not in this branch; say so in the test.

## Done when

- The full self-check has run again and every gate passed (give the count), or you
  stopped at a failed gate.
- `.venv/bin/pytest -o addopts='' -q tests/unit/logs tests/unit/docs tests/unit/plugin tests/unit/packaging`
  passes with no failure.
- `.venv/bin/pytest -o addopts='' -q tests/acceptance/test_logs.py` passes, except cases
  that fail only because of items 1 to 4 (name each and the rule it meets); a separate
  agent updates that file from the record.
- `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/basedpyright` clean.
- `.venv/bin/python bench/make_log_example.py --check` passes.
- `shasum -a 256 -c FROZEN.sha256` reports only the five released files.

## Final message

One line per numbered item; the gate summary and elapsed time of the new run; the figures
that moved, if any; the commands and their last lines; anything you could not do.
