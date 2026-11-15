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

## Addenda after spike S0 (16 Nov 2026; S0 passed, decision D-19)

- **A2 changes too.** The 2.3.0 statistics document forbids choosing the setting from
  after-period counts. The new document restates A1 and A2 and their proofs: with the log
  structure fixed, the choice is fixed under every permutation of day values over fixed
  usable slots; conditional exchangeability then gives the reference distribution.
- **`--since` later than `N`:** the after period has no response. The setting is then
  chosen by the same count rule over the before period, so the output still names a
  setting, and the result is CANNOT TELL (`too_few_days`).
- **One of `--model` and `--effort` given:** among the settings that match the given
  one, the other is chosen by the count rule of M2.
- **Rows under another UTC offset** are counted as rows (one row is one setting on one day).
- **The kept table's promise** is limited to rows admitted to the table and inside the
  active window: with no gap between `--keep` runs longer than 29 days, the days used
  equal those of a history with nothing deleted (S0, G4: 0 of 500 histories differed;
  with gaps of 31 to 45 days every history lost data). The docs say that a day never
  captured whole cannot be recovered.
- **Stated limit with a number:** when the first five days of a newly adopted setting
  run 15% higher than its later days, wrong REAL DROP was 535 of 20,000 at 14 days after
  against 16 before (S0, G2b). The self-check keeps this cell.
- **The self-check adds a competitive choice:** histories in which two settings have
  close after-period counts, so that the choice is exercised and not fixed by construction.
- **Process:** every Codex invocation line now carries the sentence "Never open anything
  under ~/.claude or ~/.codex" itself, because in S0 Codex ran one search of its own
  memory registry under `~/.codex` before it had read the brief. It reported that the
  search returned nothing and that no session log was read.

## Amendments after the reviews of the record (16 Nov 2026; decision D-20)

These replace the memo's wording where they differ.

- **`--ignore-kept` with `--keep` or `--keep-dir` is a usage error** (fixed text
  `--ignore-kept cannot be used with --keep.`). So a run either reads the table, or
  ignores it and writes nothing to it. This removes the state in which a table is read
  only for the write.
- **No earliest test date is printed when `--since` is given.** The rule's windows assume
  the default split.
- **A1 as the statistics document states it**, not as M2 abbreviates it: given the log
  structure, the options of the run and which days are usable for a measure, the usable
  day values of the compared setting for that measure are exchangeable when nothing
  changed. **The log structure includes** which responses and which file-edit results
  exist, their days, settings and threads; it does not include a reasoning count or
  whether an edit failed.
- **Which row wins** (write rule and use rule): rows are compared by the pair (number of
  responses, number of file-edit results), in that order; the row from the logs wins a
  tie. This settles days that hold edit results and no response.
- **A staged table larger than 32 MiB is a write error** for the whole run: nothing is
  written and existing files stay as they are. The reader's limit and the writer's are
  the same number.
- **Client versions** need both readers: each reader returns, for the after period, the
  distinct version strings that match the pattern and the count of distinct ones that do
  not. A string that does not match is never returned.
- **Kept-day counts** in the record count every day whose row came from the kept table,
  usable or not; one day has one source for all measures, and the record model rejects a
  record where two measures disagree about a day's source.
- **What the kept table promises** is stated only for the case S0 tested: rows admitted
  to the table, one UTC offset, deletion of whole days or parts of days by age, and no
  gap between `--keep` runs longer than 29 days. A day never captured whole cannot be
  recovered, and the record says so.
- **The self-check's new gate** uses a generator that satisfies A1 (day values drawn
  independently of the number of responses), with separate null and exact-margin cells.
  Generators that break A1 on purpose (many more responses after the split; a newly
  adopted setting whose first five days run 15% higher, 535 of 20,000 in S0; a
  competitive choice between two settings with close counts is a gate, since it keeps
  A1) are reported, and each names the assumption it breaks.
- **A streak flag withholds a result; it does not establish that days depend on each
  other.** The statistics document and the `streaky_days` text say that.

## Rulings on the confirmation pass (16 Nov 2026; `reviews/R2-logs2-codex-confirm.md`)

Nine of Codex's eleven findings were resolved and two partly. All remaining findings of
the confirmation pass are accepted with their corrected wording. Rulings on the points
that needed one:

- **F24** reads `The kept day table could not be read or is not valid. It was not used.`
  (a report may be written onto the table's path when `--keep` is not given).
- **Order of errors:** option-only errors are checked before any log or table is read;
  data-dependent errors only after option validation succeeds; within each phase the
  first applicable error in the F5 order prints.
- **A day over the histogram cap** is left out of the write merge and counted; a valid
  stored row for that key stays; the use rule still considers the uncapped row from the
  logs.
- **Rollback** removes every directory the run created, deepest first, if any write fails.
- **With no selected setting** the Markdown block prints the F10 text and omits the
  digest-bearing footer.
- **What the kept table promises** uses Codex's wording: immutable records with no late
  backdated arrivals; only batches strictly older than 30 times 24 hours are deleted; the
  retained and the undeleted history are compared at the same instant with the same
  options, offset and window; each deleted day was captured whole before deletion, with
  successful captures at most 29 days apart; within the admitted rows and the active
  window the day lists agree apart from `source`, and the results agree; days that hold
  only file-edit results are outside the promise.
