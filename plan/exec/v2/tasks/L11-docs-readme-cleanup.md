# L11: documents, README and repository clean-up for 2.3.0

Read `AGENTS.md`. Work only in `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs` (branch
`v2/logs`). Change no git state. Never open anything under `~/.claude` or `~/.codex`. Do not
edit files listed in `FROZEN.sha256`, anything under `src/`, `bench/`, `packages/`,
`.github/`, `plugins/`, `integrations/`, or `tests/acceptance/`. You are the only agent in
the worktree. Plain words, short sentences, no sales wording, no claim that anything is
unique or first, no em dashes.

Sources (read them in full first):
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md`,
`.../logs/0016-logs-draft.md`, `.../DECISIONS.md` entries D-11 to D-16,
`.../tasks/L0-logs-spike.md` (section "Log formats"),
`.../spikes/L0-logs/ORCHESTRATOR.md`, and in the worktree
`docs/results/logs-selfcheck.md` (the final self-check tables) and the output of
`.venv/bin/arci logs --example`.

## You own

`README.md`, `CHANGELOG.md`, `CITATION.cff`, `docs/STATISTICS_LOGS.md` (new),
`docs/design/0016-logs.md` (new), `docs/LOG_FORMATS.md` (new), `docs/recipes/logs.md` (new),
`docs/COMPATIBILITY.md`, `docs/ROADMAP.md`, `docs/results/order-desk-study.md` (one link),
`tests/unit/docs/test_logs_docs.py` (new), and in `tests/unit/logs/test_report.py` only the
path that `test_every_fixed_text_matches_record` reads.

## Do

1. **`docs/STATISTICS_LOGS.md`**: the statistics draft as a finished document. Remove the
   draft header; point to `design/0016-logs.md`; keep every definition, assumption, claim
   and proof word for word unless a sentence refers to "draft" or to the review process.
   In "What the method cannot see", replace the sentences about the first run and the
   spike with the figures of `docs/results/logs-selfcheck.md`, each with its conditions
   (design, correlation, variant, number of runs, interval): the wrong-REAL-DROP and
   wrong-NO-DROP rates with no check, with a per-measure check and with the rule as built;
   the cost of the check on independent days; and the power table for the rule as built.
   State plainly where the measured rate under correlation stays above 2.5%. Do not round a
   figure in the rule's favour. Do not write any number that is not in that file.
2. **`docs/design/0016-logs.md`**: the record draft as a finished record, in the style of
   `docs/design/0015-imported-outcomes.md`: who wrote it and when; that it was reviewed
   read-only three times before code (13, 10 and 6 findings, all handled; where the
   maintainer's side chose differently from the reviewer, say so as the draft and D-13 do);
   that acceptance tests were written from the records alone by an agent that did not see
   the code; the decisions as they stand now, including D-12 (spike), D-15 (one streaky
   measure stops the comparison) and D-16 (Python range of the second distribution). Keep
   "Record model", "Fixed texts" and "Command line and layout" word for word (the code and
   the tests compare against them). Replace every `plan/exec/v2/...` path a reader of the
   released repository cannot follow with the name of the document in `docs/`, or drop it.
   "Not built" must be true of the code as it is.
3. **`docs/LOG_FORMATS.md`**: what the readers read, for each tool: where the files are and
   which environment variables move them, the line types and fields used, how a response is
   assembled, how the working directory, the session, the model, the effort and the client
   version are found, what is counted and left out (every `ReaderCounters` field with its
   meaning), the order of files, duplicates. State that the formats are not documented by
   their vendors and can change, and that the readers were checked against Claude Code
   client versions 2.1.309, 2.1.321 and 2.1.325 and Codex CLI versions 0.154.0 and 0.167.0
   on one machine, and on no Windows machine.
4. **`docs/recipes/logs.md`**: a recipe in the style of `docs/recipes/verdict.md`: the two
   commands (`uvx realornoise`, or `pip install agent-reliability-ci` then `arci logs`);
   the packaged example with its real output (run it and paste the text; label it example
   data); how to read each line of the output; the three results and what each does and
   does not say; why CANNOT TELL is the usual answer with a short history (retention, 5 and
   10 usable days, streaks); the options; compressed Codex logs and
   `uvx --python 3.14 realornoise`; sharing (`--markdown`, `--html`, `--json`) and what the
   files contain; the Claude Code plugin (`/plugin marketplace add
   ajaysurya1221/agent-reliability-ci`, `/plugin install realornoise@agent-reliability-ci`,
   then `/realornoise:realornoise`) and the Codex skill (copy
   `integrations/codex/skills/realornoise` into `~/.agents/skills/`), each with the note
   that the printed numbers then enter that assistant's conversation; where to go for
   stronger evidence (`arci verdict`, `arci run`).
5. **`README.md`**:
   - Replace everything before the first `## ` heading with the text in "README first
     screen" below, exactly, except that you fill the example lines from the real
     `arci logs --example` output (the result line and the reasoning-tokens row for Claude
     Code, numbers unchanged). `python plan/exec/scripts/first_screen_words.py README.md`
     must report at most 250 words (the script's own exit code uses an older limit of 200;
     read the printed count).
   - The three caveat paragraphs of the old first screen ("PASS means only this", "A small
     first run will often be INCONCLUSIVE", "ARCI observes calls that cross its tool
     boundary") and the LangChain quick start with its output move, unchanged, to the top of
     a new section `## Controlled trials: arci run` placed before "New in 2.0". The flow
     line there reads
     `baseline + candidate → same predeclared tasks/faults → repeated trials → verdict`
     followed by the sentence "For single-task experiments a failing trial can then be
     minimised and replayed; for suites those commands are not built yet."
   - Add a section `## New in 2.3: a result from logs you already have` directly after the
     first screen: 12 to 20 lines; what it reads; the example output block; the three
     results; what it cannot show (cause, answer quality, a change to a model; days that
     come in streaks; short histories); the measured rates under correlation in one
     sentence with a link to `docs/STATISTICS_LOGS.md`; the plugin and skill lines; links to
     the recipe, the statistics and the record.
   - "Related tools": add a paragraph for tools that read the same local logs, each
     described in its own project's words, with a link: ccusage
     (`https://github.com/ccusage/ccusage`, "npx ccusage", usage and cost from local logs);
     kiyoakii/is-gpt-nerfed ("Shrinkflation detector for Codex"); NerfTrack/NerfTrack
     ("Think Codex limits got nerfed by can't prove it? Prove it with NerfTrack!");
     One-Lyf/claude-nerf-watcher ("Claude Code skill: is your plan quietly giving you less?
     Tracks work per 1% of the 5-hour limit vs your own baseline."); lucemia/claude-session-analyzer
     ("Quantitative analysis tool for Claude Code session logs — thinking depth, Read:Edit
     ratio, behavioral signals, sentiment, cost. Replicates methodology from
     anthropics/claude-code#42796"); jspaterson000/nerfd ("The public record of how AI
     coding models actually perform on real work. Local-first, privacy-first scorecard
     captured from Claude Code, Codex, OpenCode and other terminals."); tendaigomo/NerfWatch
     ("The Taravangian Test for AI: catch silent model degradation before your users do.
     SPC-based reasoning-quality monitoring for Claude, GPT, Gemini, and Grok.");
     haowang02/codex-candy-eval (a script that re-runs one question against Codex; its own
     description is in Chinese, do not translate it into a claim). Quote the descriptions
     exactly (keep the dash inside the quoted text). Say that ARCI did not test any of them
     and does not claim to be the only tool of this kind.
   - Update the Roadmap, Development, Availability and GitHub Actions passages and any
     "2.2.0" that describes the current release to 2.3.0, and the "What it does not do" list
     with the limits of `arci logs`.
6. **`CHANGELOG.md`**: a `v2.3.0 (2026-11-15)` entry in the style of 2.2.0: Added (the
   command, the second distribution, the record kind, HTML, the example, the plugin and
   skill, the self-check and its published rates); Changed (the README first screen; the
   timing workflow's trigger; release and CI build two distributions); Not in this release
   (the record's "Not built"); Docs (the clean-up items). The date is today's; the
   orchestrator corrects it at the release if needed.
7. **`docs/COMPATIBILITY.md`**: a 2.3.0 paragraph: `arci-logs/1` is a new record kind; what
   is promised (the record fields, the exit codes, the fixed texts within the method
   version) and what is not (log formats of other vendors' tools; Windows is untested for
   `arci logs`). **`docs/ROADMAP.md`**: 2.3.0 in the first paragraph, same style.
   **`CITATION.cff`**: version 2.3.0 and today's date.
8. **`docs/results/order-desk-study.md`**: replace the link to the branch `v2/phase0` with a
   link to the same folder at commit `d46367d` of this repository
   (`https://github.com/ajaysurya1221/agent-reliability-ci/tree/d46367d/plan/exec/v2/study`)
   and say "at commit `d46367d`" instead of "on the branch".
9. **Tests** (`tests/unit/docs/test_logs_docs.py`): the first screen has at most 250 words
   by the script's count; every relative or repository link in the new documents and the
   new README sections points at a file that exists in the worktree; `docs/STATISTICS_LOGS.md`
   and `docs/design/0016-logs.md` contain no `plan/exec` path and no word "draft"; every
   percentage quoted in the new README section and in "What the method cannot see" appears
   in `docs/results/logs-selfcheck.md`; no `v2/phase0` link remains outside files listed in
   `FROZEN.sha256`. In `tests/unit/logs/test_report.py`, make
   `test_every_fixed_text_matches_record` read `docs/design/0016-logs.md` from the
   repository and never skip.

## README first screen (use exactly; fill the two example lines from the real output)

```markdown
# Did your agent get worse? Real, noise, or cannot tell.

[![PyPI](https://img.shields.io/pypi/v/agent-reliability-ci)](https://pypi.org/project/agent-reliability-ci/)

ARCI (agent-reliability-ci) answers that question in three ways, from the least effort and the
weakest evidence to the most. Each one prints the assumptions it cannot check.

**1. Logs you already have.** If you use Claude Code or Codex, the session logs on your disk
record how the model behaved each day. One command compares recent days with earlier ones:

```bash
uvx realornoise
```

On the packaged example data (`uvx realornoise --example`):

```text
RESULT: REAL DROP
reasoning tokens per response   <before (days)>   <after (days)>   <change>   real drop
```

Nothing leaves your machine, and the output holds numbers only. It shows what your logs
recorded, not why: your tasks, prompts and client changed too. With a short history the usual
answer is `CANNOT TELL`.
[How to read it](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/recipes/logs.md) ·
[the method and its limits](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/STATISTICS_LOGS.md)

**2. Results you already have.** `arci verdict` decides a baseline against a candidate from
pass/fail results another tool produced (Inspect AI, pytest, CSV).
[Recipe](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/recipes/verdict.md)

**3. Controlled trials.** `arci run` runs the old agent and the new one on the same predeclared
tasks, injects tool timeouts, errors and empty results, and returns `PASS`, `BLOCK`,
`INCONCLUSIVE` or `ERROR`. A `PASS` or `BLOCK` is wrong at most 2.5% of the time each, at the
defaults and under assumptions ARCI states and does not check.
[Start here](#controlled-trials-arci-run) · no install: `uvx --from agent-reliability-ci arci demo`
```

## Done when

`.venv/bin/pytest tests/unit/docs tests/unit/logs -q` passes, and the whole suite
`.venv/bin/pytest -q` passes (list sandbox-blocked tests if any);
`.venv/bin/ruff format --check .`, `.venv/bin/ruff check .` and `.venv/bin/basedpyright`
are clean; `shasum -a 256 -c FROZEN.sha256` passes. Final message: files changed, the word
count of the first screen, the test commands and their last lines, every number you quoted
and where it came from, anything you could not do.
