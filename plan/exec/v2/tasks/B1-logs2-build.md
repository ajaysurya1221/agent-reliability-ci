# B1: build `arci-logs/2` in `src/arci/logs` (record 0017)

Read `AGENTS.md` in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`
(branch `v2/logs2`). Work only there. Change no git state. No network, do not call `uv`.
Never open anything under `~/.claude` or `~/.codex`, and search no memory registry. Use
only synthetic logs. Plain words, short sentences, no sales wording, no em dashes. You are
the only agent in the worktree.

## The records (the source of truth; read them fully before any code)

- `docs/design/0017-logs-2.md`: design record 0017. Everything you build is stated there:
  options, the setting rule, the earliest test date, the kept day table, the record model,
  the fixed texts, the name rules, the layouts, and "Acceptance, as tests can see it".
- `docs/STATISTICS_LOGS.md`: the statistics document for `arci-logs/2`.
- `docs/design/0016-logs.md`: the record of `arci-logs/1`; unchanged, for history.
- `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/DESIGN-MEMO.md`: the
  choices and the rulings behind the record. If the record and the memo disagree, the
  record wins; tell me.
- `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/S0-logs2/` holds the
  spike's scratch code for the setting choice and the kept-row rules. You may read it; it
  is not product code.

If the record is ambiguous or cannot be built as written, **do not guess silently**: take
the smallest reading, build it, and list the point in your final message.

## Pinned files in this task

`FROZEN.sha256` lists pinned files. Decision D-18 releases these for change under record
0017, and only these: `src/arci/logs/schema.py` (yours in this task),
`docs/STATISTICS_LOGS.md` (already replaced by the orchestrator; do not edit it),
`tests/acceptance/test_logs.py` (not yours; a separate agent rewrites it from the record).
`shasum -a 256 -c FROZEN.sha256` will therefore report exactly these as changed, plus
nothing else. Do not edit `FROZEN.sha256`.

## You own

- `src/arci/logs/`: `schema.py`, `records.py`, `claude_code.py`, `codex.py`,
  `measures.py`, `decide.py`, `report.py`, `html.py`, `cli.py`, and the new `kept.py`.
  `rank_test.py` and `discover.py` only if the record requires it (say why).
- `tests/unit/logs/` (all files except `test_oracle_scipy.py`), its snapshots, and
  `tests/unit/logs/privacy/`.
- The packaged example and its generator (`src/arci/logs/example/`,
  `bench/make_log_example.py`) where the record changes their output.
- `tests/unit/docs/test_logs_docs.py`: only what must change because the fixed texts now
  live in record 0017 and the section ends at `## Coverage of the bound`.

Not yours in this task: `bench/selfcheck_logs.py` and `docs/results/logs-selfcheck.md`
(task B2), `README.md`, `docs/recipes/`, `docs/LOG_FORMATS.md`, the plugin and the skills,
`packages/` (task B3), `tests/acceptance/`, `.github/`, `pyproject.toml`, version numbers.

## What to build

Everything record 0017 states for the code. In short, so that nothing is missed:

1. Record model `arci-logs/2` with every new field and validator; the `arci-logs/1` model
   stays readable as `LogsDecisionV1`.
2. Both readers return client-version names as the record says.
3. The setting rule (most main-thread responses in the after period; the stated
   fall-backs, ties and partial overrides), computed from the days as used.
4. The kept day table: schema `realornoise-days/1`, read with every listed fault, the row
   order (responses, then file-edit results; logs win a tie), the use rule, the write
   rule, caps, pruning, the 32 MiB limit, modes, the staged all-or-none write together
   with the other outputs, rollback of created directories.
5. Options `--keep`, `--keep-dir DIR`, `--ignore-kept`, their usage errors, and the order
   in which errors are checked.
6. The earliest test date, the first response day and the response-day counts.
7. Every new and changed fixed text, in text, Markdown and HTML, and in JSON the fields
   that carry them; kept days marked in HTML; the nine effort names; `sol`; client
   versions after the split.
8. The two rate figures of the closing paragraph and the Markdown footer come from named
   constants `RATE_5_10` and `RATE_7_21` in `report.py`. Until task B2 has run the 2.4.0
   self-check, set them from the checked-in `docs/results/logs-selfcheck.md` by the rule
   in the record's "Coverage of the bound" section, and make the doc test hold them equal
   to that file.

## Tests

- Unit tests for every numbered acceptance item of the record that can be tested at unit
  level, and for every validator (positive and negative).
- Property tests for the kept-row rules (write then use; deletion by age; another UTC
  offset), seeded.
- Privacy tests extended: the canary strings must not appear in the kept table, the audit
  hook allows writes only to the paths given and, with `--keep`, the table directory; no
  socket, no subprocess.
- Round trip: every new state through JSON, then text, Markdown and HTML rendered from the
  restored record alone.
- Regenerate snapshots only where the record changes the output, and list which.

## Done when

- `.venv/bin/pytest -o addopts='' -q tests/unit/logs tests/unit/docs tests/unit/plugin tests/unit/packaging`
  passes, except tests that fail only because of work that belongs to B2 or B3 (name each
  one and the reason; expected: documents that still show `uvx realornoise` or 2.3.0 texts).
- `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/basedpyright` clean.
- `.venv/bin/python bench/make_log_example.py --check` passes.
- `shasum -a 256 -c FROZEN.sha256` reports only the three released files.
- From the worktree: `.venv/bin/python -m arci.cli logs --example` runs and its output
  follows the record (paste the first 12 lines and the exit code).

## Final message

One line per numbered item above with what you built and where; the commands and their
last lines; every snapshot regenerated; every place where you had to read the record in
the smallest way; the tests left failing for B2 or B3; anything you could not do. No long
logs.
