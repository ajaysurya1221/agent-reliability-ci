# Design memo for `arci-logs/2` (version 2.4.0, design record 0017)

Written by the orchestrator on 16 Nov 2026 after decision D-18. It fixes the choices. The
record `docs/design/0017-logs-2.md` and the revised `docs/STATISTICS_LOGS.md` are written
from it. Where this memo is silent, `arci-logs/1` (record 0016, `docs/STATISTICS_LOGS.md`
at 2.3.0) stays as it is.

## M1. Records

- Method id `arci-logs/2`. Version 2.4.0. `arci-logs/1` records are still read and
  validated; new runs write `arci-logs/2`.
- `docs/design/0016-logs.md` is not edited. Record 0017 restates the **complete** list of
  fixed texts, options, reason codes and the record model, so that tests read one file.
- `docs/STATISTICS_LOGS.md` is revised in place (released for change by D-18).

## M2. Which setting is compared

- **Rule:** the setting (model id and effort as the log records them) with the most
  main-thread responses **in the after period** (`s` to `N`). Ties go to the setting whose
  raw (model id, effort) pair sorts first as text. `--model` and `--effort` override as now.
- A response counts for this choice whether or not its reasoning count is known. No
  reasoning count and no edit result enters the choice.
- Because `N` is the newest day with a main-thread response, the after period always has
  a response, so a setting is always chosen unless every response lacks a model or effort
  (`no_usable_setting`, unchanged).
- **Statement to prove in the statistics document:** the choice is a function of the log
  structure only (which responses exist, their days, settings and threads). The tests
  permute day values of the chosen setting with the group sizes fixed, so the choice is
  the same in every permutation. Assumption A1 is restated: given the log structure, the
  usable day values of the compared setting are exchangeable when nothing changed.
- **Stated limit:** a setting adopted recently has few earlier days, and its first days
  may differ from later ones. The tool does not compare across a change of model or effort.

## M3. What CANNOT TELL shows (`too_few_days`)

For the compared setting, in text, Markdown, HTML and JSON:

- the first day in the window with a main-thread response at this setting;
- days with a response at this setting, before and after;
- usable days per measure (as now);
- **the earliest date a test is possible.** Rule: for `d = N+1, N+2, ...` up to `N+98`,
  treat every day from `N+1` to `d` as usable for every measure. A measure has enough days
  on `d` when the usable days in `[d-13, d]` number at least 5 and those in `[d-97, d-14]`
  at least 10. The date is the first `d` on which at least one gating measure has enough
  days. If there is none, the line is left out. Wording must say it is the earliest case:
  every day until then usable, and the earlier days still on disk or kept.
- when Claude Code is the tool: one line that Claude Code deletes session files after 30
  days by default (setting `cleanupPeriodDays`), and that `--keep` keeps each day's counts.

`not_enough_evidence` and `streaky_days` get no date line.

## M4. The kept day table (opt-in)

- **Flags:** `--keep` writes the table after the run. `--keep-dir DIR` chooses the
  directory and implies `--keep`. Default directory: `$REALORNOISE_HOME` if set, else
  `~/.realornoise`. File name `days-1.json`. `--ignore-kept` reads no table.
- **Reading:** if the file exists in the resolved directory it is read on every run. It
  exists only because the user asked for it earlier. The banner line "writes nothing
  unless asked" stays true.
- **Content** (schema `realornoise-days/1`): per tool, per UTC offset in minutes, per
  setting, per day: number of main-thread responses; a histogram of known reasoning counts
  (count to frequency, zero included); number of unknown counts; for Claude Code, file-edit
  results and failed ones. Main thread only. Numbers and dates only, plus the setting's
  names.
- **Only settings whose model id passes the closed grammar and whose effort is in the
  accepted list are kept.** Other settings are not kept and are counted in a notice. So the
  table holds no log string outside the two bounded exceptions.
- **Caps:** rows older than 180 days before `N` are dropped on write. A day with more than
  5,000 distinct reasoning counts is not kept and is counted.
- **Write rule:** for each (tool, offset, setting, day), the row computed from the logs
  replaces the stored row when it has at least as many responses; otherwise the stored row
  stays. The write is atomic; file mode 0600, directory 0700; it joins the all-or-none
  rule of the other outputs.
- **Use rule:** for each (tool, setting, day) in the window, the row from the logs is used
  when it has at least as many responses as the stored row; otherwise the stored row is
  used. Rows stored under another UTC offset are ignored and counted.
- **Output:** a fixed line stating how many before-days and after-days came from the kept
  table. In JSON each day carries `source: "logs" | "kept"`. The digest covers the table used.
- **Faults:** a table that cannot be read or does not validate is ignored with a notice;
  the run goes on. A failed write is a write error like any output.
- **Limits to state:** kept rows are not checked against logs again; an edited table gives
  an edited result; the output marks kept days. The claims and assumptions do not change.

## M5. The documented command

`uvx --python 3.14 realornoise` in the README first screen, the recipe, the package
README, and both skills. The plugin and the Codex skill pin the version:
`uvx --python 3.14 realornoise==2.4.0` (the version test covers the pin).
`requires-python` stays `>=3.11`.

## M6. The bound, as it is

- The closing paragraph says first that the bound holds if the days are interchangeable
  when nothing changes. It then gives two measured figures from the 2.4.0 self-check: the
  largest wrong-REAL-DROP rate with the rule as built, over the tested positive
  correlations, at 5 days after against 10 before, and at 7 against 21. A test holds the
  printed figures equal to the self-check file. The Markdown footer carries a short form.
- The self-check adds: (i) the null gate with setting changes under M2, 20,000 histories
  per design; (ii) each streak-check rate also given conditional on passing the check;
  (iii) power cells run until the stated number of tested histories is reached, and the
  table says what each count is; (iv) the design 14 after against 16 before (Claude
  Code's default retention) in the null, correlation and power tables; (v) weekly-cycle
  and regime-switching generators, report only.
- The streak check itself is unchanged in this version. The record lists as open: one
  pre-stated check instead of three, an unknown split date, and repeated daily looks.

## M7. Names

- Efforts printed in full: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`,
  `ultra`, `persistent` (the Codex client's own list on 16 Nov 2026).
- `MODEL_WORDS` gains `sol`.
- **Client versions after the split** are printed as a third bounded exception: strings of
  two to four dot-separated numbers of at most five digits each; the three highest by
  numeric order, then `+k more`. Text, Markdown, HTML and JSON.

## M8. Not in 2.4.0

An unknown split date; repeated daily looks with a stated error rate; other coding
agents; OpenTelemetry as a source; a public tracker.

## Gate before product code: spike S0

`spikes/S0-logs2/` and `tasks/S0-logs2-spike.md`. Go when: with M2 and independent days,
wrong REAL DROP and wrong NO DROP are each at or under 2.83% in 20,000 simulated histories
per design, where histories hold two or three settings and a change of setting inside the
window; and the kept-table rules of M4 give the same day table after old logs are deleted
as before.
