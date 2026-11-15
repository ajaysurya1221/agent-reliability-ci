# B3: the printed bound sentence, and every document for 2.4.0

Read `AGENTS.md` in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`
(branch `v2/logs2`). Work only there. Change no git state. No network, do not call `uv`.
Never open anything under `~/.claude` or `~/.codex`, and search no memory registry. Use
only synthetic data. Plain words, short sentences, no sales wording, no em dashes, no
claim to be unique, no claim of cause. You are the only agent editing the worktree.

Versions are already 2.4.0 everywhere. Do not change a version number, `FROZEN.sha256`,
`tests/acceptance/`, `bench/`, `docs/results/logs-selfcheck.md`, `docs/STATISTICS_LOGS.md`
or `docs/design/`.

## Part 1. The printed bound sentence (code)

Record 0017 changed after the self-check (commit `e0fefaf`): F10 and the Markdown footer
no longer print two figures (`{rate_5_10}`, `{rate_7_21}`). They print one, the worst the
self-check measured, with its design: `{rate_max}`, `{worst_after}`, `{worst_before}`.
Read in `docs/design/0017-logs-2.md`: the F10 text and the footer under "Fixed texts",
the section "Coverage of the bound", and acceptance item 40.

- `src/arci/logs/report.py`: replace `RATE_5_10` and `RATE_7_21` by `RATE_MAX`,
  `RATE_MAX_AFTER` and `RATE_MAX_BEFORE`, set by the rule of "Coverage of the bound" from
  the checked-in `docs/results/logs-selfcheck.md`; F10 and the footer as the record now
  words them, in text, Markdown and HTML.
- The doc test that holds the constants equal to the self-check file applies the new rule
  (both sections, the stated columns and rows, the first row on a tie).
- Regenerate the snapshots that carry the sentence, and list them.

## Part 2. Documents (all must match the code as it now behaves; run it to see)

1. `README.md`:
   - The first screen's command becomes `uvx --python 3.14 realornoise`, with one short
     clause on why (it reads compressed Codex logs; `uv` fetches that Python). Keep the
     first screen at or under 250 words (`plan/exec/scripts/first_screen_words.py` prints
     the count; its own limit of 200 is old).
   - Replace "New in 2.3" by "New in 2.4" (keep it short): the tool now compares the
     model and effort you use now; `--keep` keeps each day's counts beyond the vendor's
     retention (Claude Code deletes session files after 30 days by default, setting
     `cleanupPeriodDays`; source https://code.claude.com/docs/en/settings-reference, read
     15 Nov 2026); CANNOT TELL names the earliest date a test is possible; the output
     states the worst wrong-REAL-DROP rate the self-check measured. Every figure must be
     in `docs/results/logs-selfcheck.md` (a doc test checks that; make it pass without
     weakening it). Say plainly that with a short history the usual answer is CANNOT TELL.
   - Under "Related tools" add one bullet for tools about "did the model get worse", each
     as it describes itself, read 16 Nov 2026, not tested here:
     [is-it-nerfed](https://github.com/resitaydin/is-it-nerfed) ("A Claude Code plugin
     that checks your own logs for proof"; it asks Sonnet subagents whether you had to
     correct the model, for a sample of your prompts, and compares the last two weeks
     with an earlier window) and [livenerf](https://github.com/ninjahawk/livenerf) ("A
     long-running, deterministic-as-possible benchmark for detecting whether a frontier
     model gets quietly worse after launch"). No comparison claims.
2. `docs/recipes/logs.md`: the transcript is the real output of
   `arci logs --example` at 2.4.0 (a doc test compares it); every option including
   `--keep`, `--keep-dir DIR`, `--ignore-kept` and their two usage errors; how the setting
   is chosen; what CANNOT TELL now shows; a section "Keeping days beyond the vendor's
   retention": what the kept table holds (counts, dates, the setting's names), where it
   is, what it promises and where that stops (runs at most 29 days apart; a day never
   captured whole cannot be recovered), how to delete it; the 30-day default and
   `cleanupPeriodDays`; the closing sentence with the measured figure and what it means
   when work comes in phases.
3. `docs/LOG_FORMATS.md`: what changed in the readers (client-version names; nothing
   else), the kept table's file format field by field, and one sentence that Codex
   compresses sessions idle for 7 days to `.jsonl.zst` (source: the Codex repository,
   `codex-rs/rollout/src/compression.rs`, read 16 Nov 2026), which is why Python 3.14 is
   the documented way to run.
4. `packages/realornoise/README.md`, `plugins/realornoise/skills/realornoise/SKILL.md`,
   `integrations/codex/skills/realornoise/SKILL.md`, `integrations/codex/README.md`: the
   command is `uvx --python 3.14 realornoise`; the plugin's skill and the Codex skill run
   the pinned form `uvx --python 3.14 realornoise==2.4.0` (also in the plugin's
   `allowed-tools`); they do not pass `--keep` (the skill text says the user can run
   `--keep` themselves and what it writes). Extend
   `tests/unit/packaging/test_review_fixes.py::test_every_release_version_matches` so that
   the pin in both skills is a version location.
5. A new page `docs/THREAT_MODEL_LOGS.md` (one page) and a link to it from `SECURITY.md`
   in a short new section for `realornoise`: what it reads (paths); what it writes (only
   files named by options, and with `--keep` the table directory); that it opens no
   socket and starts no process, and which tests hold that (name them); how log content
   is treated (as untrusted input: only numbers, dates and the three bounded kinds of
   name reach any output; terminal escapes); the supply chain (two runtime dependencies;
   trusted publishing with attestations; how to check a release's hashes); what the
   plugin does (runs one pinned command; the printed numbers enter the assistant's
   conversation); what it does not protect against (another user on the machine; an
   edited kept table; a vendor changing its log format). Reports attach the tool's own
   output, never a log line. Add a doc test that the link exists and that every test the
   page names exists.
6. `docs/RELEASING.md` (the skill pins and the new workflows as version or check
   locations; the oracle job; the re-freeze list of record 0017), `docs/COMPATIBILITY.md`
   (what `arci-logs/2` and `realornoise-days/1` promise; `arci-logs/1` records stay
   readable), `docs/ROADMAP.md` (2.4.0 in one sentence; what the record leaves open).
7. `CHANGELOG.md`: move the `Unreleased` entries under `## v2.4.0 (2026-11-16)` and add
   the entries for this release in the file's style: Added, Changed, Fixed (the two
   defects the blind tests found), Not in this release, Docs. The self-check sentence
   gives the worst measured rate with its count, interval and seed, copied from the file.

## Done when

- `.venv/bin/pytest -o addopts='' -q tests/unit/logs tests/unit/docs tests/unit/plugin tests/unit/packaging`
  passes with no failure.
- `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/basedpyright` clean.
- `.venv/bin/python bench/make_log_example.py --check` passes.
- `shasum -a 256 -c FROZEN.sha256` reports only the five released files
  (`docs/STATISTICS_LOGS.md`, `src/arci/logs/schema.py`, `tests/acceptance/test_logs.py`,
  `pyproject.toml`, `uv.lock`).
- `tests/acceptance/test_logs.py` is expected to fail in the cases that hold the old
  sentence; say how many fail and that the sentence is the only cause. A separate agent
  updates that file from the record.

## Final message

Part 1: the three constants and the row they come from, the snapshots regenerated.
Part 2: one line per numbered item. The commands and their last lines. The first-screen
word count. Anything you could not do. No long logs.
