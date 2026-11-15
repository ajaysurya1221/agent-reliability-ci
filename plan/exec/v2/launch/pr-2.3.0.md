# Pull request text for 2.3.0 (paste into the description box)

Title: `v2.3.0: a result from session logs you already have`

Compare link: https://github.com/ajaysurya1221/agent-reliability-ci/compare/main...v2/logs

---

## What this adds

`arci logs`, also published as `uvx realornoise`: it reads the Claude Code and Codex session
logs already on disk, compares recent days with earlier days for the same model and effort,
and answers `REAL DROP`, `NO DROP` or `CANNOT TELL` (exit 1, 0, 2; `ERROR` is 3). Nothing is
sent anywhere. The output holds counts, rates, dates and the names of the model and effort
compared.

- Method `arci-logs/1`: exact rank tests on day values, no random numbers. Each wrong result
  is at most 2.5% per tool under four printed assumptions that the tool does not check.
  Statement and proof: `docs/STATISTICS_LOGS.md`. Design record: `docs/design/0016-logs.md`.
- A second distribution, `realornoise`, that pins `agent-reliability-ci==2.3.0` and exposes
  the one command. Python 3.11 onward; compressed Codex logs need Python 3.14.
- Text, Markdown, JSON and HTML output; a packaged synthetic example (`--example`).
- A Claude Code plugin and a Codex skill that only run the command.
- `arci verdict` and `arci run` are unchanged and remain the stronger evidence.

## What it cannot show

A cause, answer quality, or a change to a model. With a short history the usual answer is
`CANNOT TELL`. When days come in streaks the bound does not hold: the published self-check
(`docs/results/logs-selfcheck.md`) gives the measured wrong-result rates under day-to-day
correlation, including the cells where the rate stays above 2.5%.

## How it was checked

- Blind acceptance tests written from the records alone by an agent that did not see the
  code: 82 cases, pinned in `FROZEN.sha256`.
- Self-check: 19 of 19 gates, each gated cell at exactly 20,000 simulated tables.
- Two adversarial reviews (23 and 22 findings; 22 and 12 confirmed; all confirmed findings
  fixed) and a final check of the output-writing path that found no defect.
- Privacy tests: canary tokens, an audit hook (no socket, no subprocess, writes only to the
  paths given), an import allow-list.
- Both wheels installed in fresh environments on Python 3.11, 3.12, 3.13 and 3.14.

## Not verified

- Windows.
- Log formats older than Claude Code 2.1.309 and Codex CLI 0.154.0.
- A split-in-time check on real logs (the maintainer's project has about a week of logs).
- The release workflow's second publish job, which only runs on a tag.

## Re-freeze (record 0016)

`pyproject.toml` (version, description, three keywords), `uv.lock` (its own version line),
`AGENTS.md` (rule 1). Newly pinned: `docs/design/0016-logs.md`, `docs/STATISTICS_LOGS.md`,
`src/arci/logs/schema.py`, `tests/acceptance/test_logs.py`. The other 68 hashes are
unchanged; 75 files are pinned.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
