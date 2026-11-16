# 0017: v2.4.0, method arci-logs/2

Record by the orchestrator, 2026-11-16, written from the design memo approved with decision
D-18. Version 2.4.0. Method `arci-logs/2`. Record 0016 stays pinned and unchanged as the record
of `arci-logs/1`. This record restates in full every option, fixed text, reason code and record
field that a test compares, so that a test reads this file alone. Where this record is silent,
[the statistics contract](../STATISTICS_LOGS.md) as revised for 2.4.0 applies; record 0016 is
needed only for `arci-logs/1` records.

## Why

Three things were found after 2.3.0: two runs on a real machine with a long history, a research
round whose cited claims were checked one by one, and a count-only check of the reasoning field.

- The 2.3.0 rule compares the setting with the most responses over the whole window. On the real
  machine that was a setting with no response in the last 14 days, in both tools. The result was
  CANNOT TELL, and the output did not say why.
- Claude Code deletes session files after 30 days by default. A default user then has about 16
  earlier days, while a test needs 10 usable ones and the default before period is 84 days.
- The 2.5% wording is too strong for short histories when days resemble their neighbours. The
  2.3.0 self-check measured wrong REAL DROP rates above 2.5% for such days.
- The tool prints six effort names. The Codex client accepts nine.

## Decision

1. **Method `arci-logs/2`, version 2.4.0.** New runs write `arci-logs/2` records. Records of
   `arci-logs/1` are still read and validated under the 0016 model; no run writes one.

2. **The compared setting is the one in use after the split.** The setting (model id and
   effort as the log records them) with the most main-thread responses in the after period,
   `s` to `N`, is compared. Ties go to the setting whose raw model id is first in code-point
   order; if the model ids are equal, the one whose raw effort is first in code-point order.
   A response counts for this choice whether or not its reasoning count is
   known. No reasoning count and no file-edit result enters the choice. This replaces the 0016
   rule, which counted responses over both periods together. The candidates are the settings
   with at least one main-thread response in the window, on the days as used (see the use rule
   under "The kept day table"); `--model` and `--effort` keep only the candidates with those
   rendered names, as in 0016. When no candidate has a main-thread response after the split (a
   `--since` later than `N`, or after-period responses that all lack a setting), the same count
   rule runs over the before period, with the same ties. A setting is
   therefore chosen unless no candidate remains: no setting has a main-thread response in the
   window, or none has the names given with `--model` and `--effort`. The result is then
   CANNOT TELL with `no_usable_setting` and its unchanged text. The statistics contract proves
   that the choice is a function of the log structure only and restates assumption A1 for it.

3. **CANNOT TELL (`too_few_days`) names what is missing.** For the compared setting, every
   output shows the first day in the window with a main-thread response at this setting, the
   days with a response before and after the split, the usable days per measure (in the table,
   as in 0016), and the earliest date a test is possible. For Claude Code it also shows that
   Claude Code deletes session files after 30 days by default (setting `cleanupPeriodDays`)
   and that `--keep` keeps each day's counts. `not_enough_evidence` and `streaky_days` get no
   date line.

4. **An opt-in kept day table.** `--keep` writes a table of daily counts outside the vendors'
   folders after the run; later runs use it for days whose session files are gone. It is
   specified in full under "The kept day table" below. This reverses one item of the 0016 list
   "Not built": a stored day table that outlives log retention.

5. **The bound is stated as it is.** The closing paragraph first says that the 2.5% bounds need
   the days to be interchangeable when nothing changes, together with the other assumptions,
   then gives one measured figure from the 2.4.0 self-check with its design: the largest wrong
   REAL DROP rate of the rule as built over every no-change row of the correlation table and of
   the weekly-cycle and regime table ("Coverage of the bound"). A test holds the printed values
   equal to the self-check file.
   The Markdown footer carries a short form. The 2.4.0 self-check adds: (i) a gate with setting
   changes under decision 2, from a generator that keeps A1 (day values drawn independently of
   the number of responses), with a null cell and one exact-margin cell per measure, 20,000
   histories each, wrong REAL DROP at most 0.0283 in the null cell and wrong NO DROP at most
   0.0283 in each margin cell; (ii) a second gate of the same kind in which two settings have
   close after-period counts, so the choice is exercised; (iii) report-only cells whose
   generators break A1 on purpose, each naming the assumption it breaks; (iv) each streak-check
   rate also given conditional on passing the check; (v) power cells run until the stated number
   of tested histories is reached, the table saying what each count is; (vi) the design 14 after
   against 16 before in the null, correlation and power tables; (vii) weekly-cycle and
   regime-switching generators, report only. The streak check itself is unchanged.

6. **Names.** Nine efforts are printed in full. `MODEL_WORDS` gains `sol`. Client versions
   after the split are printed as a third bounded exception to the no-log-string rule.

7. **The documented command** is `uvx --python 3.14 realornoise` in the README first screen,
   the recipe, the package README and both skills. The plugin and the Codex skill pin the
   version: `uvx --python 3.14 realornoise==2.4.0`; the version test covers the pin.
   `requires-python` stays `>=3.11` for both distributions.

8. **Version 2.4.0.** The command, the exit codes, the result names, the reason codes and the
   tests keep their meaning. A record kind is added (`arci-logs/2`); `arci-logs/1` records
   stay valid.

## Decisions of this record beyond the memo

Each line is a rule this record sets that the design memo's sections do not state. The memo as
amended on 16 Nov 2026 (decision D-20) settles every point the two reviews of this record
raised, and nothing in this record departs from it.

- `--keep` or `--keep-dir` with `--project` is a usage error with its own fixed text (F5).
- Under `--project` no table is read (`kept_table` is `not_read`).
- `--example` ignores `--keep`, `--keep-dir` and `--ignore-kept` for its behaviour: it reads no
  table and writes none. The usage errors are checked on the options alone, before any log or
  table is read, so `--example` does not excuse them.
- Where more than one usage error applies, the one printed is the first in the order of the F5
  list.
- An empty `REALORNOISE_HOME` is treated as unset. `$REALORNOISE_HOME` is made absolute and `~`
  is expanded, as for `--keep-dir`. `--keep-dir` wins over `REALORNOISE_HOME`.
- The 32 MiB limit of the memo is read as more than 33,554,432 bytes, for the reader and for
  the staged file alike.
- The earliest test date always exists: it is at most `N+24`, so the memo's "if there is none"
  branch cannot occur and is not stated.
- Rows stored under another UTC offset are counted all, whatever their day, as the memo says.
- When no candidate has a main-thread response in the after period, the count rule runs over
  the before period, as the memo's addendum says for a `--since` later than `N`; the same holds
  when after-period responses all lack a setting.
- The ties of the setting rule are read as a pair compared field by field: model id first, then
  effort, each in code-point order.
- Candidates, the after-period counts of the choice and `other_settings` are taken from the days
  as used, kept rows included; the context counts and reader counters come from the logs only.
- Client versions: equal numeric tuples go in ascending code-point order of their text; `k` counts every distinct
  after-period version not listed, matching or not. The memo asks each reader for the
  after-period versions; a reader does not know the split, so the readers return a version name
  only when the string matches the pattern, and `measures.build` applies the after-period
  restriction (see "Names").
- The JSON walk rule accepts version strings under `client_versions_after_shown` only.
- New record fields `since_given`, `kept_table` and `keep`, with the values given in "Record
  model". The `arci-logs/1` model stays in the code as `arci.logs.schema.LogsDecisionV1`;
  `LogsDecision` is the `arci-logs/2` model.
- In the HTML strip charts a kept day is an open circle.
- F21 prints with zeros whenever the table was read.
- F20's second line names only settings shown by name.
- Stored rows dated after `N` are not used. They are not dropped either: a write prunes only
  rows dated before `N-180`.
- On write, stored rows of the tool dated before `N-180` are dropped under every offset, and
  only for a requested tool that is not ERROR.
- Which errors are checked in which phase: the option-only phase holds an unknown option, a
  malformed value, a malformed `--since` date, two output options naming the same file and the
  two conflicts of `--keep`; the rest need the logs. The ruling fixes the two phases; this list
  assigns the errors to them.
- The tool never removes a directory. A table directory a run created stays, empty, when its
  write fails (changed after the last check; see "Directories are never removed").
- F24 says only that the table was not used, and the record says why: without `--keep` an output
  option may name the table's path, and the report is then written over it.
- The rows written, and the counts `settings_not_kept` and `days_not_kept`, cover every kept
  setting and day from `N-180` to `N`, whatever `--model`, `--effort` and `--since` say.
- The table's path joins the same-file check only when `--keep` or `--keep-dir` is given. A
  table directory the run created stays, empty, if any write fails. `kept_table` is `absent`
  only when the path does not exist; any other failure to open is `unreadable`.
- `--help` is listed in the synopsis; its text is not a fixed text.

## What 0017 leaves unchanged, replaces and adds

Unchanged from 0016: the measures, their usable-day rules and margins; the three tests and the
streak check with their thresholds (`(1/40)/3`, `1/40`, `1/10`); the order of results and the
exit codes; the window (split `N - 13` by default, 84 before-days, `--since` rules); the
readers, their counters and every reading fault; the output-file rules (all or none, same-file
check, permission bits); every fixed text not marked below; the privacy rules, extended by the
client-version exception (decision 6) and the kept day table (decision 4); the second
distribution, the plugin and the Codex skill, apart from the command in decision 7.

Replaced: the setting rule (decision 2); the closing paragraph F10, the method line F11 and the
Markdown footer; the `streaky_days` reason text (changed in 0017: it says that the check
withholds a result and that a flag does not establish that days depend on each other); the
effort list and `MODEL_WORDS`; the 0016 "Not built" item on a stored day
table; the record model's `schema_version` and digest method (`arci-logs/2`); the 0016 privacy
sentence "Client versions and working directories are never output" (changed in 0017: client
versions after the split that match the version pattern are printed, F26; working directories
are still never output); the JSON walk rule (changed in 0017: it also accepts, under
`client_versions_after_shown` only, strings that fullmatch `^[0-9]{1,5}(\.[0-9]{1,5}){1,3}$`);
the write rule (changed in 0017: the command writes only the files named by `--markdown`,
`--html` and `--json`, their temporary files, and with `--keep` the kept table, its temporary
file and its directory). The canary rule still holds: a version-shaped canary that does not
match the pattern (for example `9.8.7654321`), and any version from the before period only,
appears in no output.

Added: the M3 lines for `too_few_days`, the kept day table and its options, the kept-table
notices, the client-version line, the new record fields below, and two usage errors.

## Names

- **Efforts printed as written:** `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`,
  `ultra`, `persistent` (the Codex client's own list on 16 Nov 2026). Any other effort is shown
  as `effort-1`, `effort-2`, ... as in 0016.
- **How aliases are numbered (0016's rule, stated here).** Per tool and per kind, the raw names
  that the lists reject are put in code-point order of the raw string and numbered from 1 in that
  order: the first rejected effort is `effort-1`, the second `effort-2`, and likewise `model-1`,
  `model-2`, ... for rejected model ids. Models and efforts are numbered independently, accepted
  names take no number, and one raw name always gets the same alias within a run. A setting shown
  by alias is never kept in the day table.
- **Model ids** pass the closed grammar of 0016 (`records.render_model`): at most 48 characters;
  lower-case ASCII; split at `-`, `.` and `_` into at most six parts; every part is a word of
  `MODEL_WORDS`, or a number of one or two digits, or a token of two or three characters made
  of one letter and digits (`4o`, `o3`, `r1`), or one eight-digit number starting with `20`; at
  most three parts are numbers; at most one is the date. `MODEL_WORDS` is exactly: `claude`,
  `opus`, `sonnet`, `haiku`, `fable`, `mythos`, `instant`, `gpt`, `codex`, `chatgpt`, `mini`,
  `nano`, `micro`, `max`, `pro`, `turbo`, `spark`, `astra`, `omni`, `preview`, `latest`,
  `thinking`, `fast`, `high`, `low`, `medium`, `xhigh`, `gemini`, `flash`, `ultra`, `lite`,
  `exp`, `deepseek`, `chat`, `reasoner`, `coder`, `qwen`, `glm`, `kimi`, `grok`, `code`, `mlx`,
  `sol` (`sol` new in 0017). Any other model id is shown as `model-1`, `model-2`, ... as in
  0016. Accepted names are disclosed in full; the grammar bounds what a name can carry and does
  not promise that a name is not private.
- **Client versions after the split (new in 0017)** are the third bounded exception. A client
  version is printed only when it matches `^[0-9]{1,5}(\.[0-9]{1,5}){1,3}$`: two to four
  dot-separated numbers of at most five digits each. The population is the one of
  `client_versions_after` (all responses of the tool in the after period, after the
  `--project` filter, before the main-thread and setting filters). The printed list holds the
  three highest matching versions by numeric order (each version read as a tuple of integers,
  compared as tuples; equal tuples, such as `1.01` and `1.1`, go in ascending code-point order of their text, so `1.01` comes before `1.1`), highest
  first. `k` is the number of distinct after-period client versions not listed, whether or not
  they match. The list is followed by ` +{k} more` when `k` is at least 1. When no version
  matches, the line is left out. A version that does not match is never printed. Working
  directories are still never printed.
- **What the readers return (new in 0017).** Both readers change for this line
  (`src/arci/logs/claude_code.py` and `src/arci/logs/codex.py`). Each keeps one version identity
  per response, as in 0016, and returns in addition a tuple of version names in the order of
  those identities, beside its model and effort names: a name is the version string when the
  string matches the pattern above, and null when it does not. So a reader returns the distinct
  version strings that match, and the identities of the rest without their strings; a string
  that does not match is never returned, and no later step can print one. The after-period
  restriction is applied in `measures.build`, which knows the split: it takes the distinct
  version identities of the tool's after-period responses (the population above), lists the
  three highest whose name is not null by the order above, and counts the remaining distinct
  identities, matching or not, as `k`. The number of distinct after-period versions whose name
  is null is therefore `client_versions_after` minus the number of distinct matching ones.

## Command line and layout

```
arci logs [--tool auto|claude-code|codex|both] [--since YYYY-MM-DD] [--model NAME]
          [--effort NAME] [--project PATH] [--claude-dir DIR] [--codex-dir DIR] [--utc]
          [--markdown FILE] [--html FILE] [--json FILE] [--keep] [--keep-dir DIR]
          [--ignore-kept] [--example] [--help]
realornoise [the same options]
```

Every option of 0016 keeps its meaning:

- `--tool auto` (the default) requests each tool whose log root exists; when neither exists both
  are requested, so both report `no_logs` and the exit code is 3. `both` requests both. Under
  `--tool auto`, a tool for which a directory option was given is always requested. An explicit
  `--tool claude-code` or `--tool codex` requests that tool alone.
- `--since YYYY-MM-DD` replaces the split date; a malformed date, or one more than 83 days before
  the newest day, is a usage error; a date after the newest day gives an after period with no
  days.
- `--model NAME` and `--effort NAME` take rendered names and keep only matching candidates.
- `--project PATH` is made absolute against the current directory, without touching the file
  system; `~` is expanded.
- `--claude-dir DIR` replaces the Claude Code `projects` directory; `--codex-dir DIR` replaces
  the Codex home.
- `--utc` uses offset 0 for days.
- `--markdown FILE`, `--html FILE`, `--json FILE` write the report files.
- `--example` ignores the directory options, reads the packaged synthetic logs with a fixed
  "now" stored beside them, and prints F13 as the second line of the text output, in the
  Markdown block and on the HTML page. The packaged example gives REAL DROP for Claude Code
  and NO DROP for Codex, and every row of both tables has enough days: each day has at least
  ten file-edit results for Claude Code, some responses with no reasoning, and for Codex some
  responses at one repeated value.
- `--help` (listed in 0017; present in 2.3.0) prints the options and reads no logs; its text is
  not a fixed text, but it names every option of the synopsis.
- Two output options may not name the same file: `Two output options name the same file.`
  is a usage error. Two spellings of one file (letter case or Unicode form on a file system
  that folds them, a symbolic link, a relative and an absolute path) are the same file. An
  existing output file keeps its permission bits; a new one gets what the process's umask
  gives a new file. Output files are written only after every one of them has been
  rendered, each to a temporary name beside its target and then moved into place; if any
  write fails, none of the requested files is left changed.
- Unknown options, a malformed value and the usage errors of F5 print exactly one fixed line
  to standard error (the sentence alone, no prefix) and exit 3; an unknown option or malformed
  value prints `Usage error. Run: realornoise --help`. Nothing is written to standard output
  and no output file is written. Nothing else is ever written to standard error.
- `run` takes the options only (`argv` does not start with `logs`), and `now` must carry a
  zone. `main(argv=None)` calls `run` with the real clock, environment, home and streams.
  `arci logs ...` and `realornoise ...` call `main`.

New in 0017:

- `--keep` writes the kept day table after the run.
- `--keep-dir DIR` chooses the table's directory and implies `--keep`. `DIR` is made absolute
  against the current directory and `~` is expanded, as for `--project`. An empty `DIR` is a malformed
  value: the general usage line, exit 3, nothing read and nothing written.
- An output option whose file name begins with `.realornoise-` (in any letter case) is a
  malformed value: the general usage line, exit 3, nothing read and nothing written. Those names
  are reserved for the table's temporary files.
- `--ignore-kept` reads no kept table, so the result uses no kept row. It may not be combined
  with `--keep` or `--keep-dir`.

Rules for the new options:

- **Directory.** `--keep-dir DIR` if given; else `$REALORNOISE_HOME` when it is set and not
  empty, made absolute and with `~` expanded, as for `--keep-dir`; else `~/.realornoise`. The
  file is `days-1.json` in that directory. The same directory is used for reading and writing.
  The directory itself is never printed.
- **Reading.** When the file exists in the resolved directory it is read on every run, with or
  without `--keep`. It exists only because the user asked for it earlier, so the header line
  "writes nothing unless asked" stays true. No table is read at all under `--ignore-kept`,
  `--project` or `--example`.
- **`--ignore-kept` with `--keep` or `--keep-dir`** is a usage error with fixed text
  `--ignore-kept cannot be used with --keep.` and exit 3. The text names `--keep` also when the
  run gave `--keep-dir`. So a run either reads the table and may write it, or ignores it and
  writes nothing to it; no run reads the table for the write alone.
- **`--keep` or `--keep-dir` with `--project`** is a usage error with fixed text
  `--keep cannot be used with --project.` and exit 3. Kept rows hold no project, so rows of a
  project-filtered run would later be used as whole-tool rows.
- **Order of errors.** Checking has two phases. The errors that read the options alone are
  checked first, before any log or table is opened: an unknown option, a malformed value, a
  malformed `--since` date, two output options naming the same file, and the two conflicts above.
  `--example` does not excuse them. The errors that need the logs are checked only after the
  first phase found none: a `--since` more than 83 days before the newest day, dates outside the
  calendar range, and output that could not be written. Within one phase, where more than one
  error applies, the one printed is the first in the order of the F5 list.
- **`--example`** ignores `--keep`, `--keep-dir` and `--ignore-kept`: it reads no table and
  writes none, as it ignores the directory options.
- An option given more than once takes its last value, as in 0016.

Text output, in this order, with one blank line between groups:

1. F1, then F13 for `--example`, then F24 when the kept table could not be read (new in 0017).
2. For each requested tool, Claude Code first: F2; the two F3 lines; a blank line; F4; the F5
   reason; for `too_few_days` only, F18, then F19 (its two lines), then for Claude Code F20 (its
   two lines) (new in 0017); a blank line; the F6 table; a blank line; the two F7 lines; F26 when
   it applies (new); F8; F21 when the kept table was read (new; in this block only, so a tool
   with no selected setting and an ERROR tool print no F21); then each notice that applies,
   in the order F14, F9, F15, F16, F17, F22, F23, F25 (the last three new); then F11. For ERROR:
   the tool name on its own line, F4 and the F5 reason, then F9 and F17 when they apply in their
   ERROR wording (so a Codex history that is entirely compressed, read on an older Python, still
   names the way to read it). For `no_usable_setting`: the tool name, F4, the reason and the
   notices that apply, in the order above.
3. F10, once, when at least one tool has a result other than ERROR. Its third sentence begins
   "For each tool above and one comparison, if (1)".
4. F12, then the last line `exit {code}`.

Lines are at most 100 characters. A fixed sentence longer than 100 characters is broken at the
last space that leaves the line at most 100 characters long, and so on for the rest, as in 0016.
F10, F19, F20 and the `streaky_days` reason are given below as lines of at most 100 characters
and print as given; with their values filled they stay within 100 characters. F26 can pass 100
characters with three long versions and is then broken by the rule. A line of exactly 100
characters is allowed. The text
is plain ASCII except `·`; no colour, no control characters (every rendered name passes through
`outcome_report.escape_terminal`).

The Markdown file holds one block per requested tool, separated by a blank line, with no line
wrapping (a table row is one line). The Markdown and HTML outputs have no line limit. The
Markdown block for a tool with a selected setting holds, separated by blank lines: F2 in
bold with the result; the F6 table; one line with the split date and F7's counts; F26 when it
applies (new); for `too_few_days`, F18, F19 as one line, and for Claude Code F20 as one line
(new); F21 when the kept table was read (new); the notices in the text order; the closing line
for the result; the footer (changed in 0017). The file starts with F13 for `--example` and then
F24 when it applies (new). An ERROR block holds the tool name, `ERROR` and the F5 text, then F9
(with its next line) and F17 in their ERROR wording when they apply, and nothing else.

With no selected setting (`no_usable_setting`), every output form shows the tool name, the
result and the fixed reason, then the notices that apply, in the text order, and F10. The scope
parts that are not available, the period lines, the measure table, the context counts and the
digest are left out; no digest is made up. In the Markdown file such a block ends with the F10
text and no footer, since the footer carries a digest; the footer appears only for a tool with a
selected setting and a result other than ERROR.

In the HTML output the characters `&`, `<`, `>`, `"` and `'` are written as HTML character
references, so a fixed text that holds one of them appears on the page escaped, and a test
compares it after unescaping the page.

The HTML page holds, per tool, the same information as the text output, F18 to F26 included,
and one strip chart per gating measure (one dot per usable day, a vertical line at the split,
the two medians), as inline SVG. In the strip charts a day from the kept table is drawn as an
open circle and a day from the logs as a filled one (new in 0017). It has no script, no
external reference, and no value that is not in the record. This includes the notices of an
ERROR tool.

The JSON file holds the sealed `arci-logs/2` record, UTF-8, keys sorted, two-space indent, a
final newline.

Exit codes: REAL DROP 1, NO DROP 0, CANNOT TELL 2, ERROR 3. The process exit code, among tools
without ERROR, is 1 if any is REAL DROP; otherwise 2 if any is CANNOT TELL; otherwise 0. If
every requested tool is ERROR, it is 3. A usage error, or a requested output file that cannot be
written, exits 3 whatever the results. Each tool's result is shown separately from the one exit
code.

`arci.logs.cli.run(argv, *, now=None, env=None, home=None, out=None, err=None) -> int` stays
the testable entry. `env` supplies `REALORNOISE_HOME`; `home` supplies `~` for the default
table directory.

## The earliest date a test is possible

Computed for the compared setting when the reason is `too_few_days` and no `--since` was given.
Otherwise it is null and its line is left out. `N` is the last day of the after period.

For each gating measure, let `U` be the set of days in its `before_days` and `after_days` (the
usable days of the record). For `d = N+1, N+2, ...`, let `U_d` be `U` together with every day
from `N+1` to `d`. The measure has enough days on `d` when `U_d` holds at least 5 days in
`[d-13, d]` and at least 10 days in `[d-97, d-14]`. The earliest date is the first `d` from
`N+1` on which at least one gating measure has enough days; it is at most `N+24`, so it always
exists. (At `N+24`, `[d-13, d]` holds the 14 new days `N+11` to `N+24`, and `[d-97, d-14]`
holds the 10 new days `N+1` to `N+10`.)

Every day in `[d-97, d-14]` that is not after `N` lies in the record's window, so the date can be
recomputed from the record alone. The date counts from `N`, not from today; when the tool was
last used some time ago, it can be a day that has already passed. The line says that it is the
best case. It is conditional on the compared setting being used every day after `N`, so a past
date promises nothing.

## The kept day table

**File.** `days-1.json` in the directory of the rules above. Schema `realornoise-days/1`.

**Content.** One JSON object with exactly two keys:

- `schema`: the string `realornoise-days/1`.
- `rows`: a list of row objects, sorted by (`tool`, `utc_offset_minutes`, `model`, `effort`,
  `day`), with no key of these five fields twice.

Each row has exactly these keys:

| Field | Type and rule |
|---|---|
| `tool` | `"claude-code"` or `"codex"`. |
| `utc_offset_minutes` | integer, greater than -1440 and less than 1440: the offset of the run that wrote the row. |
| `model` | the model id as written; it passes the model grammar above. |
| `effort` | the effort as written; one of the nine efforts above. |
| `day` | `YYYY-MM-DD`, a calendar date at that offset. |
| `responses` | integer, 0 or more: main-thread responses of this setting on this day, with or without a known reasoning count. |
| `reasoning` | list of `[count, frequency]` pairs: each known reasoning count of these responses (0 included) and how many responses had it; counts strictly ascending, integers 0 or more; frequencies integers 1 or more; at most 5,000 pairs. |
| `reasoning_unknown` | integer, 0 or more: responses of this row with no known reasoning count. |
| `edits` | Claude Code: integer, 0 or more, file-edit results of this setting dated this day (denials and unmatched results left out, as in 0016). Codex: `null`. |
| `edits_failed` | Claude Code: integer from 0 to `edits`, the failed ones. Codex: `null`. |

`responses` equals the sum of the frequencies plus `reasoning_unknown`. A row has at least one
response or at least one file-edit result. Integers are JSON integers, never booleans or
decimals. The table holds numbers, dates and the setting's names, and nothing else read from a
log. A row is enough to compute every measure of 0016 for its day: the known and positive
counts, the median of the positive counts, the share of zero counts, the frequency of `v*`, and
the edit share.

**What is kept.** Main thread only, with the 0016 reader rules (duplicates, records in the
future, zone-less timestamps and responses without a setting left out). Only settings whose
model id passes the grammar and whose effort is one of the nine are kept; other settings are not
kept and are counted (`settings_not_kept`, notice F22). A day with more than 5,000 distinct
reasoning counts is not kept and is counted (`days_not_kept`, notice F23). So the table holds no
log string outside the two bounded name exceptions. `settings_not_kept` is the number of
distinct raw settings with a main-thread response or file-edit result from `N-180` to `N` that
are not kept; `days_not_kept` is the number of (setting, day) rows of kept settings in that
range left out for more than 5,000 distinct counts. Both count settings and rows, never
responses: a setting with a thousand responses on ten days counts once in `settings_not_kept`,
and a day over the cap counts once in `days_not_kept`. Both are counted whenever `keep` is true
and the tool is not ERROR, also when the table is not written.

**A day over the histogram cap.** A day of a kept setting with more than 5,000 distinct
reasoning counts is left out of the write merge and counted in `days_not_kept`. A valid stored
row for that (tool, offset, setting, day) stays as stored; it is neither replaced nor dropped.
The use rule is not affected: the row from the logs is used for that day under the ordinary rule,
with all its counts, since the cap bounds only what the file may hold. A row with exactly 5,000
distinct counts is kept.

**Write rule.** With `--keep`, after the run, for each requested tool that has a newest day `N`
(a tool whose result is ERROR writes nothing): the rows from the logs are every (setting, day)
with at least one main-thread response or file-edit result of a kept setting, from `N-180` to
`N`, at the run's offset. The rows written cover every kept setting and day in that range,
whatever `--model`, `--effort` and `--since` say. For each (tool, offset, setting, day), the two
rows are compared by the pair (number of responses, number of file-edit results), in that order;
the row from the logs replaces the stored row when its pair is at least as large, and otherwise
the stored row stays. A Codex row has no file-edit count and counts as 0 there. A row is written
whole: no field of one row is merged into the other. Pruning belongs to the same step and runs
only for a requested tool that is not ERROR and has a newest day `N`: it drops that tool's stored
rows dated before `N-180`, under every offset, and touches nothing else. Stored rows dated after
`N` stay as stored, although no run uses them. Rows of a tool that was not requested, or that is
ERROR, stay as stored, pruning included. When every requested tool is ERROR, nothing is written
at all and the stored file keeps its bytes.

**Use rule.** Unless the table is not read, for each (tool, setting, day) in the window at the
run's offset: the two rows are compared by the pair (number of responses, number of file-edit
results), in that order, as in the write rule; the row from the logs is used when its pair is at
least as large, and otherwise the stored row is used. So the row from the logs wins a tie, and a
day that holds file-edit results and no response is decided by its file-edit count. A Codex row
counts as 0 file-edit results. A stored row with no row from the logs is used. The window
is fixed from the logs alone: `N` is the newest day with a main-thread response in the logs, so a
tool with no logs is still ERROR (`no_logs`), and stored rows dated after `N` are not used. Stored
rows of this tool under another UTC offset are not used, and all of them are counted, whatever
their day (`kept_rows_other_offset`, notice F25). After the use rule, the setting choice, `v*`,
the usable days and the tests run on the days as used, exactly as on days from the logs.
Candidates, after-period counts for the choice, and `other_settings` are taken from the days as
used: a setting with at least one response in a used row in the window is a candidate, whether
that row came from the logs or the kept table. The context counts (F7, F26) and the reader
counters come from the logs only. A row is used whole, so the pair decides every field of the
day together: a logs row with more responses and fewer file-edit results than the stored row is
used whole, and the day's file-edit count is then the logs row's.

**Writing.** The directory is created with mode 0700 when it does not exist, with any missing
parents; the mode of an existing directory is not changed. The file is written to a temporary
name in the directory and moved into place; its mode is 0600, also when it replaces a file with
other bits. Keys sorted, no indent, UTF-8, a final newline. The write joins the all-or-none rule
of 0016: it is staged with the other requested files; if any write fails, none of them is left
changed and the run exits 3 with
`Requested output could not be written.` as the only line on standard error and nothing on
standard output. **Rollback** restores every file and removes no directory: the table directory is
created before any file is staged, and one this run created, with any parents it created, stays
in place and is empty. A directory that already existed keeps its mode. A failure
while a staged file is being moved into place rolls back the same way. The
table's path joins the same-file check only when `--keep` or `--keep-dir` is given: an output
option that names the table is then `Two output options name the same file.` `kept_table` is
`absent` only when the path does not exist or the file there holds 0 bytes; any other failure
to open it is `unreadable`.

**An interrupted write, and two runs at once (added after the adversarial review).** The
same-file check may create empty files at target paths that do not exist yet; it removes them
again before anything is staged, so a run that is stopped while it stages or moves files
leaves no empty file at a target. A table file of 0 bytes is not a table: it is read as
`absent`, F24 does not print, and a `--keep` run replaces it. With `--keep`, the stored table
is read again and merged, and the new table is moved into place, while the run holds an
exclusive lock on the table directory, so two runs that overlap do not lose each other's rows:
the second writer merges with what the first one wrote. The result of the run still uses the
table as it was read at the start. Where the platform offers no such lock, the run goes on
without it. After a successful write, and while the lock is held, temporary files that this
tool left in the table directory (regular files whose names begin with `.realornoise-`) are
removed. The run creates no file in the table directory other than the table and its own
temporary file.

**Whose temporary files the cleanup may remove (added after the second review).** Only the
table's own temporary files carry the prefix `.realornoise-`. The temporary files of every
other output begin with `.realornoise.out-`, in whatever directory they are, so the cleanup
never removes a file that another run is still using for its other outputs. While the lock is
held no other run can be writing the table, so every `.realornoise-` file found is a leftover.
Where there is no lock, an overlapping `--keep` run can lose its temporary file to the cleanup:
it then fails with the write error and leaves the table and every requested output as they
were.

**Directories are never removed, and reserved names (decided after the last check; this
replaces the earlier rule that a failed write removes the directories it created).** Three
rounds of review each found a new fault of one kind: a failing run removed a directory that
another run was about to use. The tool therefore never removes a directory. A run that holds
the lock on the table directory then holds it on the directory every other run sees; no check
of the directory's identity and no second attempt is needed, and none is made. If the table
directory cannot be opened for the lock, the write fails. Where the platform has no such lock
call, or the call itself fails, the run goes on without a lock. The tool assumes that no other
program removes or replaces the table directory while a run is using it. An output option
(`--json`, `--markdown`, `--html`) whose file name begins with `.realornoise-`, compared after
Unicode normalization (NFKC) and without regard to letter case, is a malformed value: the
general usage line, exit 3, nothing read and nothing written. The test is made on the name as
given and on the name of the file the path resolves to, so a symbolic link to such a name is
refused too. Those names are reserved for the table's temporary files, so the cleanup can never
remove a file that a run asked for.

**A run that is interrupted or killed (added after the check of the simpler design).** An
interrupt from the keyboard during the write ends the run with the write error and exit 3. If
it arrives before the last file is moved into place, the run restores the files it had already
replaced and removes an empty file it had made at a new target. If it arrives after the last
move, the files are already written and the run still ends with that error. A second interrupt
during the restore can leave some files replaced. An interrupt can also leave a temporary file
beside a report (its name begins with `.realornoise.out-`), which may be deleted by hand. A
process that is killed outright restores nothing: it can leave some files replaced, an empty
file at a new target if it is killed during the same-file check, and such a temporary file.
In the table directory the next successful `--keep` run removes the table's
leftovers. No requested file is ever left half written: each is moved into place whole.

**One size limit.** The reader's limit and the writer's are the same number: 32 MiB, read as
more than 33,554,432 bytes. Neither the number of settings nor the number of rows is capped, so
a table of admitted rows can reach that size. The staged table is measured before anything is
moved into place. A staged table larger than the limit is a write error for the whole run: it is
treated like any other failed write, so nothing is written, every requested output file and the
stored table stay as they were, a table directory the run created stays, empty, and the run
prints `Requested output could not be written.` as the only line on standard error and exits 3.
The run therefore never leaves behind a table its own reader would refuse.

**Faults.** The table is not used, with notice F24, when the file cannot be opened or read, is
not a regular file, is larger than the size limit above, is not UTF-8 JSON, holds an object key
twice, or fails any rule above. One bad row makes the whole table unused: there is no partial
use, and F24 prints once for the run. The run goes on without it. With `--keep`, a table that
could not be read is not replaced and not changed; the run goes on, F24 says so, and the exit
code is the one of the result. Without `--keep` the file may still be replaced, but only because
an output option named its path (see the same-file rule above); F24 therefore says only that the
table was not used. The path, the file's text and any error text are never printed. A staged
table over the size limit is not a fault of this kind but a write error, as above.

**What the table promises, and where it stops.** The promise holds for the case the S0 spike
tested, and for no other. Its conditions, all of them needed: records are immutable and no
response arrives late with an earlier timestamp; only batches strictly older than 30 times 24
hours are deleted; the retained history and the undeleted history are compared at the same
instant, with the same options, the same UTC offset and the same window; each deleted day was
captured whole by a `--keep` run before it was deleted, and successful captures are at most 29
days apart; and the rows are rows the table admits (a kept setting, at most 5,000 distinct
counts) inside that window. Then, for each measure, the day lists of the two runs agree after
`source` is removed from them, and the two results agree. (S0, G4: 0 of 500 histories differed;
with gaps of 31 to 45 days every history lost data.) Outside these conditions nothing is
promised, and the `source` fields differ by construction, since the point of the table is that a
day came from it. A day never captured whole cannot be recovered: `--keep` keeps what a run could
read, so a day whose files were already partly deleted when the first `--keep` run saw it stays
partial for good. Days that hold only file-edit results are outside the promise: their retention
was not tested, and a row is used whole, so a day whose responses grew while its file-edit
results were deleted keeps the logs row and its smaller file-edit count.

**Limits.** Kept rows are not checked against logs again. An edited table gives an edited result.
The output marks kept days: F21 in text, Markdown and HTML, `source` on every day in JSON, open
circles in the HTML charts, and the day-table digest covers each day's source. A row, from the
logs or kept, can hold only part of a day: a kept row written before its day ended, or a log row
after some of the day's session files were deleted; its value then describes only those
responses. Kept days are almost always before-days, so any difference between kept and log rows,
such as a reader change between versions or a partial day, falls on one period and breaks A1.
The kept table changes no claim; it adds these ways for A1 to fail. Where clocks change for
daylight saving, rows written before a change are at another offset and are not used after it
(counted in F25); `--utc` keeps one offset all year.

## Record model (`src/arci/logs/schema.py`, pinned)

Pydantic models, `extra="forbid"`, frozen, sealed with `hashing.hash_record`. Rationals are
strings `"p/q"` in lowest terms with a positive denominator (`"0/1"` for zero); dates are
`YYYY-MM-DD`. Fields marked (new) are new in 0017; all others are as in 0016.

- `LogsDecision`: `schema_version: "arci-logs/2"`, `arci_version`, `example: bool`,
  `utc_offset_minutes: int` (greater than -1440, less than 1440), `project_filtered: bool`,
  `since_given: bool` (new; true when `--since` was given), `kept_table: "not_read" | "absent" |
  "read" | "unreadable"` (new; `not_read` under `--ignore-kept`, `--project` or `--example`;
  otherwise `absent` when the path does not exist, `unreadable` when F24 prints, else `read`),
  `keep: bool` (new; true when `--keep` or `--keep-dir` was given and `--example` was not),
  `tools: list[ToolDecision]` (Claude Code first, then Codex; only requested tools), `exit_code`,
  `seal` (`hash_record` of the record without `seal`).
- `ToolDecision`: `tool: "claude-code" | "codex"`, `result: "REAL_DROP" | "NO_DROP" |
  "CANNOT_TELL" | "ERROR"`, `reason: ReasonCode`, `model: str | None`, `effort: str | None`
  (rendered names), `other_settings: int`, `split_date: date | None`, `before: Period | None`,
  `after: Period | None`, `measures: list[MeasureDecision]`, `context: ContextCounts | None`,
  `counters: ReaderCounters`, `day_table_sha256: str | None`, and:
  - `first_response_day: date | None` (new): the first day in the window with a main-thread
    response at the compared setting, from the days as used.
  - `response_days_before: int`, `response_days_after: int` (new): days in each period with at
    least one main-thread response at the compared setting, from the days as used.
  - `earliest_test_date: date | None` (new): the date of "The earliest date a test is
    possible"; set exactly when `reason` is `too_few_days` and `since_given` is false, and then
    equal to the recomputation from the stored day lists; otherwise null.
  - `kept_days_before: int`, `kept_days_after: int` (new): days in each period whose row for the
    compared setting came from the kept table, whether or not that day is usable for any measure.
    A kept row can hold too few responses for every measure, so these counts can be larger than
    the number of days marked `kept` in the stored day lists and cannot be recomputed from those
    lists. 0 unless `kept_table` is `read`.
  - `kept_rows_other_offset: int` (new): stored rows of this tool under another UTC offset,
    whatever their day. 0 unless `kept_table` is `read`.
  - `settings_not_kept: int`, `days_not_kept: int` (new): as defined under "What is kept"; 0
    unless `keep` is true.
  `measures` is in the order of the contract's table. With ERROR or `no_usable_setting`:
  `model`, `effort`, `before`, `after`, `context`, `day_table_sha256`, `first_response_day` and
  `earliest_test_date` are null; `measures` is empty; `response_days_*` and `kept_days_*` are 0.
  With ERROR, `kept_rows_other_offset`, `settings_not_kept` and `days_not_kept` are 0.
  `split_date` is kept whenever the tool has a main-thread response (so it is set for
  `no_usable_setting` unless there is no response at all). When the split is later than the
  newest day, `after` is null and the after-day lists are empty.
- `Period`: `first_day`, `last_day` (calendar bounds of the period).
- `MeasureDecision` (unchanged): `id`, `worse: "lower" | "higher"`, `margin` (the adverse
  change: `"1/4"`, `"1/10"`, `"3/100"`), `before_days` and `after_days` (`list[DayValue]`,
  ascending by day, no day twice), `median_before`, `median_after` (median of the day values; an
  even number of days gives the mean of the two middle ones; null with no usable day),
  `p_streak`, `p_real`, `u_none`, `p_none`, `finding: "streaky" | "real_drop" | "no_drop" |
  "cannot_tell" | "too_few_days"`. Which test fields are filled is fixed by the finding and
  enforced by a validator, together with the thresholds: `too_few_days`: none; `streaky`:
  `p_streak` only; `real_drop`: `p_streak` and `p_real`; `no_drop` and `cannot_tell`: all
  four. The validator also recomputes `p_streak`, `p_real`, `u_none` and `p_none` from the
  stored day values and rejects a record whose stored values differ.
- `DayValue`: `day`, `count: int`, `value` (in the measure's own units, not negated), and
  `source: "logs" | "kept"` (new). `count` is the number of positive counts for
  `reasoning_tokens` and `repeated_value_share`, of known counts for `no_reasoning_share`, and
  of file-edit results for `edit_failure_share`. `source` is `kept` only when `kept_table` is
  `read`.
- `ContextCounts`, over all responses of the tool in the window after the `--project` filter,
  before the main-thread and setting filters, from the logs only: `client_versions_before`,
  `client_versions_after`, `client_versions_both`, `workdirs_before`, `workdirs_after` (counts
  of distinct values), `subagent_share_before`, `subagent_share_after` (rationals; null when
  the period has no response), and
  `client_versions_after_shown: list[str]` (new; 0 to 3 versions that match the version pattern,
  in the order of the Names section) and `client_versions_after_more: int` (new; the `k` of that
  section). The length of `client_versions_after_shown` plus `client_versions_after_more` equals
  `client_versions_after`.
- `ReaderCounters`: unchanged: `files_read`, `files_unread_compressed`, `files_unreadable`,
  `files_outside_project`, `lines`, `lines_not_json`, `lines_unknown_type`,
  `lines_lacking_field`, `records_in_future`, `records_without_timezone`, `responses`,
  `responses_duplicate`, `responses_without_reasoning`, `responses_without_setting`,
  `edits_denied`, `edits_unmatched`. They count what was read from the logs; kept rows do not
  change them.
- `ReasonCode`: unchanged: `real_drop`, `no_drop`, `not_enough_evidence`, `too_few_days`,
  `streaky_days`, `no_usable_setting`, `no_logs`, `read_error`, `format_not_recognised`.
- `day_table_sha256` is `hash_record` of `{method: "arci-logs/2", tool, model, effort,
  split_date, before, after, alpha_real: "1/120", alpha_none: "1/40", measures: [{id, margin,
  before_days, after_days}]}` in the fixed orders above, with the rendered model and effort,
  dates and rationals as the strings of the record, periods and day values as the record's
  objects (a missing period is null); each day value now includes its `source`. The
  ToolDecision validator recomputes this digest from the stored fields and rejects a record
  whose `day_table_sha256` differs with reason `inconsistent_day_table_sha256`; a tool with no
  day table is unchanged.
- Further validators (new): `first_response_day` lies in the window and is not later than any
  stored usable day of `reasoning_tokens`, `no_reasoning_share` or `repeated_value_share`;
  `response_days_before` is at least the number of distinct days in the `before_days` of each
  of those three measures, and likewise after. `edit_failure_share` days are not compared with
  response days, since a file-edit result can fall on a day with no response.
  `kept_days_before` is at least the number of distinct before-days with `source: "kept"`,
  likewise after, and at most the number of days in the period; `earliest_test_date` is null or
  equal to its recomputation; a `kept` source with `kept_table` other than `read` is rejected;
  `kept_table` is `not_read` only when `keep` is false, since a run that writes the table also
  reads it; `client_versions_after_shown` holds at most three strings, each matching the version
  pattern, in the order of the Names section, and its length plus `client_versions_after_more`
  equals `client_versions_after`. A record that breaks any of these is rejected.
- **One day, one source (new).** One row of the day table supplies every measure of that day, so
  a day that appears in the day lists of more than one measure carries the same `source` in each.
  A record in which two measures give one day different sources is rejected, with reason
  `inconsistent_day_source`. The `kept_days_*` counts stay as above: they also count days that no
  measure lists.
- `arci-logs/1` records validate under the 0016 model, field for field, as
  `arci.logs.schema.LogsDecisionV1`; `arci.logs.schema.LogsDecision` is the `arci-logs/2` model.

Rendering (unchanged): reasoning counts as integers rounded half up; shares as percentages with
one decimal; the change of `reasoning_tokens` as a whole percentage of the before median; the
change of a share in percentage points with one decimal; margins as `25%`, `10 pts`, `3 pts`; a
value that is not available as `-`. Rendered numbers decide nothing.

## How a test reads this record

A test that compares fixed texts with the code takes every span in backticks between the headings
`## Fixed texts` and `## Coverage of the bound` (changed in 0017: the 0016 test ended at
`## Command line`, which now precedes this section; `tests/unit/logs/test_report.py` changes
with it). In the code, F10 and the footer keep `{rate_max}`, `{worst_after}` and `{worst_before}`
as format fields, filled from the module constants `RATE_MAX`, `RATE_MAX_AFTER` and
`RATE_MAX_BEFORE`; the comparison uses the
unfilled constants, as for `{12 hex}`. Each span is a fixed text, or one
of these spans that are not texts: one of the nine reason codes, `{}`, `ERROR`, `K`, `k`,
`p_streak > 1/10`, `{default}`, `{flag}`, `{k}`. A multi-line text is given one line
per span, as in 0016; the footer is one span. Whitespace is compared after collapsing runs to one
space. Markers "(new in 0017)" and "(changed in 0017)" stand outside the spans.

## Fixed texts

`{}` marks a value. Numbers are rendered from the record; nothing else varies.

- **F1 header:** `realornoise {version} · reads local session logs · sends nothing · writes nothing unless asked`
- **F2 scope:** `{Tool} · {model} · effort {effort} · main thread · days at UTC{+hh:mm}`
- **F3 periods:** `before  {first} to {last}` and `after   {first} to {last}   split {s}`; with no
  after-days the second line is `after   no days   split {s}`
- **F4 result (per tool):** `RESULT: REAL DROP` / `RESULT: NO DROP` / `RESULT: CANNOT TELL` /
  `RESULT: ERROR`. The process exit code prints once, on the last line: `exit {code}`.
- **F5 reasons:**
  - `real_drop`: `In at least one recorded measure, the days after the split moved toward worse by more than a chance ordering of your days explains.`
  - `no_drop`: `No recorded measure moved toward worse by its margin or more. This does not say anything improved.`
  - `not_enough_evidence`: `The days are too few or too variable to tell a shift from noise.`
  - `too_few_days`: `Too few usable days for every measure (5 needed after the split, 10 before).`
  - `streaky_days` (changed in 0017; two lines):
    `The streak check flagged a recorded measure: its earlier days crossed their middle few times.`
    `No result is given here. A flag does not establish that your days depend on each other.`
  - `no_usable_setting`: `No model and effort setting has a response in the window.`
  - `no_logs`: `No session logs found for {Tool}. Looked under {default}. Use {flag} DIR, or try: realornoise --example`
    where `{default}` and `{flag}` are `~/.claude/projects (or CLAUDE_CONFIG_DIR)` and
    `--claude-dir`, or `~/.codex (or CODEX_HOME)` and `--codex-dir`
    When the tool's directory option was given, use instead:
    `No session logs found for {Tool} under the directory given with {flag}. Or try: realornoise --example`
    The directory itself is never printed.
  - `read_error`: `Session log files could not be read.`
  - `format_not_recognised`: `Log files were found, but this version could not recover a response from them.`
  - usage errors (exit 3): `--since needs a date as YYYY-MM-DD.` · `--since can be at most 83 days before the newest day in the logs.` · `Requested output could not be written.` · `Comparison dates are outside the supported calendar range.` · `Two output options name the same file.` · `--keep cannot be used with --project.` (new in 0017) · `--ignore-kept cannot be used with --keep.` (new in 0017)
  - `Internal error.`: printed alone on the error stream when the program fails in a
    way no other text covers; exit 3
  - an unknown option or malformed value: `Usage error. Run: realornoise --help`
- **F6 table:** header `measure, median day` / `before (days)` / `after (days)` / `change` /
  `finding`; each period cell is the median followed by the number of usable days in
  brackets; row names `reasoning tokens per response`, `responses with no reasoning`,
  `file edits that failed`, `reasoning at one repeated value`; findings `real drop`,
  `no drop (margin {margin})`, `cannot tell`, `too few days`, `days come in streaks`; when the
  tool's reason is `streaky_days`, every row that is not `days come in streaks` or
  `too few days` shows `not used` instead of its own finding (the record keeps the finding).
- **F7 context:** `Context counts; differences between the periods are not tested:` then
  `client versions {a} before, {b} after, {c} in both · working directories {d} before, {e} after · sub-agent share {f}% -> {g}%`
- **F8 streak check:** `Streak check: {k} of {K} tested measures were not flagged.` (`K` measures
  with enough days, `k` of them with `p_streak > 1/10`); left out when `K` is 0
- **F9 unread:** `Compressed Codex files not read (Python 3.14 is needed): {k}. The result uses the rest.`
  then, on its own line, `To read them: uvx --python 3.14 realornoise`
  Under ERROR: `Compressed Codex files not read (Python 3.14 is needed): {k}.` then, on its own
  line, the same "To read them" line as above.
- **F10 limits (changed in 0017; every run with a tool whose result is not ERROR):**
  `This shows what your logs recorded. It does not establish answer quality, a cause, or a change`
  `to the model: your tasks, prompts, projects or client version may have changed.`
  `For each tool above and one comparison, if (1) the days in this window are interchangeable when`
  `nothing changes, whatever their number of responses, and (2) to (4) below hold, then REAL DROP`
  `appears at most 2.5% of the time if nothing shifted, and NO DROP at most 2.5% of the time if a`
  `measure moved toward worse by its margin or more. When days resemble their neighbours or work comes`
  `in phases, (1) fails: in the cases it tested, the self-check measured wrong REAL DROP up to`
  `{rate_max}%, with {worst_after} days after the split and {worst_before} before; other patterns can`
  `give more. The conditions (2) to (4) are: (2) any date, model, effort or project you gave was not`
  `chosen from these logs; (3) a change moves every day alike, by an amount the measure can take; (4) a`
  `change leaves the same days, setting, reference value and earlier-day values in use. None of these`
  `is checked, and the streak check does not prove them. Running this again and again until a result`
  `appears is not covered. Exact statement: docs/STATISTICS_LOGS.md in the repository.`
- **F11 method (changed in 0017):** `method arci-logs/2 · exact rank tests · no random numbers · day-table digest {12 hex}`
- **F12 next:** `Share: --markdown FILE · --html FILE · --json FILE      Stronger evidence: arci verdict, arci run`
- **F13 example label:** `Example data, generated. Not anyone's logs.`
- **F14 other settings:** `Other model or effort settings, not compared: {k}.`
- **F15 skipped lines:** `Lines that lacked a needed field, left out: {k}.`
- **F16 future records:** `Records stamped later than now, left out: {k}.`
- **F17 unreadable files:** `Files that could not be read: {k}. The result uses the rest.`
  Under ERROR: `Files that could not be read: {k}.`
- **F18 compared setting (new in 0017; reason too_few_days only):**
  `This setting: first response in the window {first} · days with a response {b} before, {a} after`
  where first is the record's first response day, and b and a are its counts of days with a
  response before and after the split.
- **F19 earliest date (new in 0017; reason too_few_days, no --since given):**
  `Earliest test date if this setting is used every day after {last}: {date} (best case).`
  `It also needs each such day usable for a measure and the earlier days still on disk or kept.`
  where date is the record's earliest test date and last is the last day of the after period.
- **F20 Claude Code retention (new in 0017; Claude Code with reason too_few_days only):**
  `Claude Code deletes session files after 30 days by default (setting cleanupPeriodDays).`
  `With --keep, each day's counts are kept for later runs, for settings shown by name.`
- **F21 kept days (new in 0017; every tool with a selected setting when the table was read, 0 included):**
  `Days from the kept table: {b} before, {a} after.`
  where b and a are the record's counts of kept days before and after the split.
- **F22 settings not kept (new in 0017):**
  `Settings not kept, since a name is outside the accepted lists: {k}.`
- **F23 days not kept (new in 0017):**
  `Days not kept, since they hold more than 5,000 distinct reasoning counts: {k}.`
- **F24 table not read (new in 0017; once per run):**
  `The kept day table could not be read or is not valid. It was not used.`
  It says nothing about the file afterwards, because a report may be written onto that path
  when --keep is not given.
- **F25 other offset (new in 0017):**
  `Kept rows stored under another UTC offset, not used: {k}.`
- **F26 client versions (new in 0017; when at least one after-period version matches):**
  `Client versions after the split: {versions}`
  where versions is the listed versions joined by a comma and a space, followed by a space,
  a plus sign, k and the word "more" when k is at least 1 (as in "2.1.325, 2.1.321 +2 more").

A notice prints only when its `{k}` is at least 1 (F14 to F17, F22, F23, F25). F21 prints with
zeros. In the text output, F18 to F21 follow the 100-column rule above. A malformed --since
prints its own sentence; an unknown option and any other malformed value print the general
usage line. The counter files_read counts every file opened, including a Codex file left after
its first line and a file that then fails while being read (that file is also counted as
unreadable); a Codex file is taken as compressed by its name, ending in .jsonl.zst, without
opening it; files_outside_project is used for Codex only and is 0 for Claude Code; responses
includes sub-agent responses.

The Markdown block's closing line depends on the result, unchanged:
- REAL DROP: `One person's logs. Evidence of movement toward worse in a recorded measure; this establishes no cause and says nothing about answer quality.`
- NO DROP: `One person's logs. No recorded measure moved toward worse by its margin; this does not say anything improved.`
- CANNOT TELL: `One person's logs. Not enough to tell a shift from noise.`
- ERROR: the tool name, `ERROR` and the F5 text, then F9 (with its next line) and F17 in
  their ERROR wording when they apply, and nothing else.

followed by the footer (changed in 0017), except for ERROR and for a tool with no selected
setting, which end with the F10 text and no footer: `Wrong REAL DROP and wrong NO
DROP are each at most 2.5% for this tool and one comparison, if the days in the window are
interchangeable when nothing changes and the assumptions below hold; when days resemble their
neighbours or work comes in phases the self-check measured wrong REAL DROP up to {rate_max}%
({worst_after} days after, {worst_before} before) in its tested cases. Assumptions, unchecked: no
date, model, effort or project chosen from these logs; a uniform shift the measure can take;
the same days, setting, reference value and earlier-day values in use. Repeated checking until
a result appears is not covered.
arci-logs/2, digest {12 hex}. Yours: uvx --python 3.14 realornoise`

## Coverage of the bound

`{rate_max}`, `{worst_after}` and `{worst_before}` are filled at build time from the 2.4.0
self-check file (`docs/results/logs-selfcheck.md`). The rows that count are those of the two
sections `Days that come in streaks (report only)` and `Weekly cycles and regime switches
(report only)` whose `drop` cell is `0` and whose `metric` cell is `wrong REAL DROP`; in the
first section the `rho` cell must also be greater than 0. In each such row the cell of the
column whose header is exactly `as built (95% CI)` is read (all histories, not the rate
conditional on passing the check); the proportion is the decimal after `= ` in that cell.
`{rate_max}` is the largest such proportion over both sections. `{worst_after}` and
`{worst_before}` are the two numbers of that row's `after/before` cell; if several rows share
the largest proportion, the first in file order gives them. The value printed for `{rate_max}`
is the proportion times 100, in decimal, without trailing zeros and without a trailing point
(a proportion of `0.181000` prints as `18.1`, of `0.035500` as `3.55`, of `0.000000` as `0`).
The two day counts print as plain whole numbers with no leading zero. The `%` sign belongs to
the text. A test reads the self-check file, applies this rule, and holds the three values
equal to the constants `RATE_MAX`, `RATE_MAX_AFTER` and `RATE_MAX_BEFORE` in the code, in F10
and in the footer.

This replaces the two figures of the first form of this record (`{rate_5_10}`, `{rate_7_21}`,
read from the correlation rows of two designs only). The 2.4.0 self-check measured its
largest rate in a cell that those two figures left out: days in regimes, at 14 days after
against 16 before. The printed figure is the largest rate of the rule as built, over all
generated histories, among the cells of those two sections, which break A1 by dependence
between days. It is not the largest number in the self-check file: among the histories that
pass the streak check the rates are higher, and the demonstrations outside the assumptions
are not rates of this kind. The statistics document gives those figures.

## Files

New: `src/arci/logs/kept.py` (the kept day table), `tests/unit/logs/` additions. Changed in
`tests/unit/logs/`: `test_report.py` (the fixed-text section ends at `## Coverage of the bound`).

Changed: `src/arci/logs/{schema,records,claude_code,codex,measures,decide,report,html,cli}.py`
(`claude_code.py` and `codex.py` for the version names of the Names section),
`bench/selfcheck_logs.py`, `docs/STATISTICS_LOGS.md`, `docs/LOG_FORMATS.md`,
`docs/recipes/logs.md`, `docs/results/logs-selfcheck.md`, `README.md`, `CHANGELOG.md`,
`packages/realornoise/README.md`, `plugins/realornoise/`,
`integrations/codex/skills/realornoise/`, `tests/acceptance/test_logs.py`.

Re-freeze at the release: `docs/STATISTICS_LOGS.md`, `src/arci/logs/schema.py`,
`tests/acceptance/test_logs.py`, `pyproject.toml`, `uv.lock`. Newly pinned: this record.
`docs/design/0016-logs.md` stays pinned and unchanged. Every other hash stays as it is.

## Open, and not built

Open in this version: one pre-stated streak check instead of the three variants the self-check
reports; an unknown split date; repeated daily looks. The streak check itself is unchanged.

Not in 2.4.0: an unknown split date; repeated daily looks with a stated error rate; other coding
agents; OpenTelemetry as a source; a public tracker. Still not built from 0016: a scan over split
dates; a comparison of two models; a plausible range for the change; Windows paths checked on a
real machine; log formats older than the client versions listed in `docs/LOG_FORMATS.md`;
usage-limit or cost measures; anything that sends data anywhere.

## Acceptance, as tests can see it

Each item can be checked from outside: by running `arci.logs.cli.run` on synthetic logs with a
fixed `now`, `env` and `home`, and reading standard output, standard error, the exit code, the
written files and the JSON record.

Unless an item supplies a kept-table fixture of its own, the run uses an isolated `home` with no
table file and an `env` without `REALORNOISE_HOME`, so no stored row can reach the result. The
items are grouped: 1 to 55 as before, then the groups of the confirmation pass.

1. A run writes a JSON record with `schema_version` `arci-logs/2`, and the fields of the record
   model above, no more and no fewer, at every level.
2. A record of `arci-logs/1` written by 2.3.0 still validates, under
   `arci.logs.schema.LogsDecisionV1.model_validate`.
3. Two settings A and B in one tool's window: A has more responses over the whole window, B has
   more in the after period. The record names B.
4. Two settings with equal after-period counts: the one whose raw model id is first in
   code-point order is compared, and with equal model ids the one whose raw effort is first. A
   case where the readings differ: model `a` with effort `z` against model `a-b` with effort
   `high`; `a` is compared.
5. Changing reasoning counts or file-edit results of any response, with the responses, their
   days, settings and threads kept, never changes the compared setting.
6. Making some after-period responses lack a reasoning count does not change which setting is
   compared.
7. With `--since` later than `N` and settings in the window, a setting is still compared (the
   one with the most before-period responses) and the result is CANNOT TELL with `after` null.
8. When every response in the window lacks a model or an effort, the result is CANNOT TELL with
   `no_usable_setting` and its unchanged text. `--model` naming no candidate also gives
   `no_usable_setting`.
9. `--model` and `--effort` keep their 0016 effect. With one of them, the count rule chooses
   among the candidates that match it, so the named candidate is compared even when another has
   more after-period responses. With both, the one candidate that matches the pair is compared.
   With no match, the result is CANNOT TELL with `no_usable_setting`.
10. Under `too_few_days`, text output holds F18 with the first response day and the counts of
    days with a response before and after; Markdown and HTML hold the same values; the JSON
    holds them in `first_response_day`, `response_days_before`, `response_days_after`.
11. Under `too_few_days` without `--since`, F19 prints with the date of the rule above, and the
    JSON `earliest_test_date` equals a recomputation from the stored day lists. A test builds
    cases where the date is `N+1`, a middle date, the date at which the before-days, not the
    after-days, become enough, and the date exactly `N+24` (no usable before-day and no usable
    after-day).
12. With `--since`, or with any reason other than `too_few_days`, F19 is absent and
    `earliest_test_date` is null; `not_enough_evidence` and `streaky_days` print no F18, F19
    or F20.
13. F20 prints for Claude Code under `too_few_days`, and never for Codex. With a compared
    setting whose model id fails the grammar, F20 prints the same two lines, and with `--keep`
    the table holds no row for that setting and F22 counts it.
14. The efforts `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`,
    `persistent` print as written. With exactly one rejected effort in the tool's logs, it prints
    as `effort-1`; with several, each gets its own number, from 1 up, in code-point order of the
    raw strings, as "How aliases are numbered" says.
15. A model id `gpt-5-sol` prints as written; with exactly one id outside the grammar it prints
    as `model-1`, and with several each gets its own number by the same rule, numbered apart from
    the efforts.
16. Client versions `2.1.309`, `2.1.321`, `2.1.325`, `2.1.40` after the split print F26 as
    `Client versions after the split: 2.1.325, 2.1.321, 2.1.309 +1 more`; a version that does
    not match the pattern, such as a canary string, is never printed and counts in `+k more`;
    when no version matches, F26 is absent. A version that occurs only before the split is never
    listed, while one that occurs in both periods is. Each
    reader's result holds a version name only for a string that matches the pattern, so a
    non-matching string is in no reader result and in no output.
17. Without `--keep`, `--keep-dir`, an existing table and any report-output option, no file is
    created anywhere, and the table directory does not come into being.
18. `--keep` with `REALORNOISE_HOME` set writes `days-1.json` under it; with it unset or empty,
    under `home/.realornoise`; `--keep-dir DIR` writes under `DIR` and needs no `--keep`.
19. The written table validates against the schema above: exactly the listed keys, rows sorted,
    `responses` equal to the frequencies plus `reasoning_unknown`, Codex `edits` null.
20. The written file has mode 0600; a directory it creates has mode 0700.
21. The table holds no string from the logs other than accepted model and effort names and the
    two fixed tool names: canary tokens in every free log string never appear in it.
22. A setting whose model id fails the grammar, or whose effort is not one of the nine, is not
    in the table, and F22 prints its count.
23. A day with 5,001 distinct reasoning counts is not in the table, and F23 counts it.
24. Rows dated more than 180 days before `N` are dropped on write; a row dated exactly `N-180`
    stays.
25. Write rule: the pair decides. A stored row whose pair (responses, file-edit results) is
    larger stays; a row from the logs whose pair is at least as large replaces it, a tie
    included; a stored row with equal responses and more file-edit results stays.
26. The promise of "What the table promises, and where it stops", under every one of its
    conditions: the fixture holds immutable records with no late arrival carrying an earlier
    timestamp, deletes only batches strictly older than 30 times 24 hours, and runs `--keep` so
    that each deleted day was captured whole beforehand, with successful captures at most 29 days
    apart. The retained history and the undeleted history are then run at the same instant, with
    the same options, offset and window. For each measure the two day lists agree after `source`
    is removed from both, and the two results agree; the days that came from the table carry
    `source: "kept"`, so the lists are not equal with `source` kept. A further case has a session
    file that spans the deletion boundary (its responses on days on both sides of it), and checks
    the day lists the use rule gives for those days.
27. Outside those conditions nothing is promised, and these cases fix the behaviour instead:
    (a) a constructed history in which a day is never captured whole, because the first `--keep`
    run comes 31 days after that day ended and its earlier batches are already deleted: that day
    is missing or partial in the later run, and the day lists differ from the undeleted history's
    even after `source` is removed; (b) a day whose logs row has
    more responses and fewer file-edit results than the stored row is used whole from the logs,
    so the day's `edit_failure_share` value comes from that row and the stored file-edit count is
    not recovered; (c) an edit-only day, with file-edit results and no response, takes the row
    with more file-edit results, so a complete stored row beats a partial logs row; S0 did not
    cover retention of file-edit results on their own, so (b) and (c) are the rule, not a
    promise.
28. F21 prints the counts of kept days per period for each tool with a selected setting when the
    table was read, `0 before, 0 after` included; it is absent for a tool whose result is ERROR or
    `no_usable_setting`, and for every tool when no table exists or under `--ignore-kept`.
29. `--ignore-kept` reads no table and writes none: the result equals the result of the same run
    with no table present, `kept_table` is `not_read`, and a stored table is left byte for byte.
30. Rows stored under another offset are not used; F25 counts all of them, whatever their day; a
    run with `--utc` and one at offset +05:30 keep separate rows.
31. A table that is not JSON, holds an unknown key, a duplicate row key, a boolean count or
    unsorted rows prints F24 once, after F1, sets `kept_table` to `unreadable`, and the result
    equals the result with no table; the Markdown and HTML rendered from the stored record alone
    hold F24 too; with `--keep`, that file is left byte for byte as it was, and the exit code is
    the one of the result.
32. `--keep` with `--project` prints `--keep cannot be used with --project.` on standard error,
    nothing on standard output, writes nothing, and exits 3.
33. When the table write fails (for example, its directory cannot be created), the run prints
    `Requested output could not be written.` as the only line on standard error, prints nothing
    on standard output, exits 3, and leaves every requested output file and the table as they
    were; a table directory the run created stays and is empty. With `--keep --json FILE` and a
    JSON target that cannot be written, the table is unchanged; a table directory that did not
    exist before the run exists afterwards and is empty.
34. With `--keep` or `--keep-dir`, a `--json`, `--markdown` or `--html` path that names the table
    file is `Two output options name the same file.`; without any of those three flags the same
    path is not an error and the report file is written there. One case has no `--keep`, an
    invalid table at the resolved path and `--json` naming that path: F24 prints once, the result
    is the result with no table, the report is written over the file, and no output claims that
    the file was left alone.
35. With otherwise valid options and report paths that collide with nothing, adding `--keep` to
    `--example` leaves the output unchanged and writes no table, and no table is read. The option
    errors still apply: `--example --keep --project PATH` prints
    `--keep cannot be used with --project.` and exits 3.
36. Every `DayValue` carries `source`; the day-table digest changes when one day's source
    changes and nothing else does. The `kept_days_*` counts include a day whose kept row is
    usable for no measure, so a case with such a day has a count larger than the kept days in
    the day lists.
37. The record model rejects: two measures giving one day different sources
    (`inconsistent_day_source`); `kept_days_before` smaller than the distinct kept before-days of
    the day lists, or larger than the number of days in the period; `source: "kept"` with
    `kept_table` other than `read`; `kept_table` `not_read` with `keep` true; an
    `earliest_test_date` that differs from its recomputation.
38. Every text output line is at most 100 characters, also with F18, F19, F20, F26 at their
    longest values and with the two lines of the `streaky_days` reason; the text is plain ASCII
    except `·`.
39. Every fixed text in this record equals a constant in the code, and every backtick-delimited
    span between the headings "Fixed texts" and "Coverage of the bound" is a fixed text or one of
    the listed spans that are not texts. The prose around the spans is not compared.
40. F10 and the footer hold `{rate_max}`, `{worst_after}` and `{worst_before}` filled with the
    values that the rule in "Coverage of the bound" reads from the self-check file.
41. Where they are present, F11 and the footer name `arci-logs/2`. A tool with no selected
    setting has no digest, so it carries neither F11 nor the footer, and a test checks that too.
42. The mapping from each result to its exit code, the result names, and the reason texts other
    than those marked changed in this record are those of 0016. Result equality with 2.3.0 is
    held only for runs in which nothing differs in the effective inputs: no kept row contributed
    (`kept_days_before` and `kept_days_after` are 0 and `kept_table` is not `read`), the 0016
    setting rule and the rule of decision 2 choose the same setting, and the window, options and
    day values are the same. Where the two rules choose different settings, or a kept row
    contributed, the result may differ and only the mapping is held.
43. The run opens no socket, starts no process, and writes only the requested report files and
    their temporary files and, with `--keep`, the table, its temporary file and its directory.
44. Use rule tie: a stored row and a logs row with equal responses and equal file-edit results:
    the logs row is used (`source: "logs"`).
45. A stored row dated after `N` is not used and does not count in `kept_days_*`; a stored row
    under another offset counts in `kept_rows_other_offset` whatever its day, a day after `N`
    included.
46. `--keep --tool codex` leaves every stored Claude Code row unchanged as a parsed row object,
    field for field, pruning included. The file's bytes may differ, since the writer always
    writes the canonical form.
47. `kept_table` is `absent` with no file, `read` with a valid one, `unreadable` with F24,
    `not_read` under `--ignore-kept`, `--project` or `--example`; `since_given` and `keep`
    follow their options.
48. `--keep-dir DIR` wins over `REALORNOISE_HOME`.
49. The pair decides the row: a stored row with equal responses and more file-edit results is
    used; a logs row with more responses and fewer file-edit results is used whole.
50. A Claude Code day with 10 file-edit results and no main-thread response at the compared
    setting validates, counts in `edit_failure_share`, and does not count in `response_days_*`.
51. A setting present only in kept rows, with more after-period responses than any setting in
    the logs, is compared, and F14 counts the others.
52. `--keep --ignore-kept`, and `--keep-dir DIR --ignore-kept`, each print
    `--ignore-kept cannot be used with --keep.` on standard error, nothing on standard output,
    read no table, write nothing, and exit 3; the same holds with `--example` given as well.
53. One size limit, both ways, with files that are otherwise valid. Reader: a table of 33,554,431
    bytes and one of exactly 33,554,432 bytes are read and used; one of 33,554,433 bytes prints
    F24, is not used, and with `--keep` is left byte for byte. Writer: a staged table of
    33,554,431 bytes and one of exactly 33,554,432 bytes are written and are read by the next
    run; a staged table of 33,554,433 bytes prints
    `Requested output could not be written.` as the only line on standard error, writes nothing,
    leaves the stored table and every requested output file as they were, removes no directory
    (one the run created stays, empty), and exits 3.
54. The new client-version exception holds only under `client_versions_after_shown`: the JSON
    walk accepts a version-shaped string there and nowhere else, so the canary `9.8.7654321`, and
    a version that occurs only before the split, appear in no output. The categories 0016 already
    allows stay allowed, `arci_version` with the value `2.4.0` among them.
55. `--help` reads no logs and its text names every option of the synopsis.

**Selection, reduction and context.**

56. The before-period fallback, in two shapes: (a) the after period holds responses but every
    one of them lacks a model or an effort, and (b) `--model` or `--effort` removes every
    after-period candidate while a matching candidate has before-period responses. In both the
    count rule runs over the before period, the record names that setting, and the result is
    CANNOT TELL.
57. A valid stored table changes a run without `--keep`: with `--keep` absent and the table in
    the resolved directory, kept days enter the day lists and F21 prints. The table cannot set
    the window: `N` stays the newest day with a main-thread response in the logs even when the
    table holds later days, and a tool with no log file is still ERROR (`no_logs`) with stored
    rows present.
58. The merged days drive everything that reads days: `v*`, each day's value and usable flag,
    `first_response_day`, `response_days_before`, `response_days_after` and `other_settings` all
    change when a kept row supplies a day, while `context` and `counters` keep the values the
    logs alone give. One fixture changes `v*` by a kept row and checks
    `repeated_value_share` with it.
59. Names at their boundaries: each of the nine efforts is admitted; a model id of 48 characters
    passes and one of 49 does not; six parts pass and seven do not; three numeric parts pass and
    four do not; one date part passes and two do not; `4o`, `o3` and `r1` pass. Client versions
    are ordered as tuples of integers: `2.1.325` before `2.1.40`; `1.01` and `1.1` are equal
    tuples and go in ascending text order (`1.01` before `1.1`); two, three and four numbers all match, one and five do not; a
    number of five digits matches and one of six does not; two non-matching strings count as two
    in `k`.
60. The version population is every response of the tool in the after period after the
    `--project` filter: responses of other settings and sub-agent responses are included, a
    response outside the project is not, and a version seen only before the split is not listed.
    In the JSON, the length of `client_versions_after_shown` plus `client_versions_after_more`
    equals `client_versions_after`.

**Table persistence and faults.**

61. The written rows and the two omission counts cover every eligible setting and day from
    `N-180` to `N`, whatever `--model`, `--effort` and `--since` say: a fixture with a selector
    that hides most settings still writes them all. `settings_not_kept` counts distinct settings
    and `days_not_kept` distinct (setting, day) rows, not responses. A day with exactly 5,000
    distinct reasoning counts is written; one with 5,001 is left out and counted, a valid stored
    row for that key stays as stored, and the run's own day value for that day still comes from
    the uncapped row from the logs.
62. Pruning runs under every offset for a requested tool that is not ERROR, and only for it: an
    ERROR tool keeps every stored row, including rows before `N-180`; a run in which every
    requested tool is ERROR writes nothing and leaves the file's bytes; stored rows dated after
    `N` survive a write and are not used.
63. Every one of these makes the whole table unused with one F24 and the result of a run with no
    table: a file that cannot be opened, a directory or other file that is not regular, bytes
    that are not UTF-8, a duplicate JSON object key, a missing key, a `schema` other than
    `realornoise-days/1`, a malformed day or an offset outside the range, frequencies plus
    `reasoning_unknown` that do not equal `responses`, `edits_failed` greater than `edits`, and
    rows out of order. One bad row is enough; no other row is used.
64. The written file is the canonical form (keys sorted, no indent, UTF-8, one final newline) and
    is byte for byte equal for two runs on the same logs. A directory that already existed keeps
    its mode; a table that replaces a file with other bits has mode 0600; an existing report file
    keeps its permission bits.
65. Paths and the points at which a write can fail: a relative `--keep-dir` is resolved against
    the current directory and a `~` path against the injected `home`; `--keep-dir` implies
    `--keep`, so `--keep-dir DIR --project PATH` and `--keep-dir DIR --ignore-kept` print their
    own fixed lines; with two errors at once the first in the F5 order prints, and an option-only
    error prints even when a log-dependent error would also apply; `--html` naming the table
    file is the same-file error, as is another spelling of that path; and a failure while a
    staged file is moved into place, not only at directory creation, leaves every output and the
    table as they were; a table directory the run created stays, empty.

**Record validation and rendering.**

66. The record's `seal` is `hash_record` of the record without `seal`, and `day_table_sha256` is
    `hash_record` of exactly the payload of "Record model", in its order: a test builds the
    payload itself and compares. Changing any one field of the payload changes the digest.
67. The validators reject, one case each: a `first_response_day` outside the window or later than
    a stored usable day; a `response_days_before` below the distinct before-days of one of the
    three response measures; a `kept_days_after` above the number of days in the after period; a
    non-null `model`, `before`, `context` or `day_table_sha256` with ERROR or
    `no_usable_setting`; a `client_versions_after_shown` out of the required order; and a shown
    list plus `client_versions_after_more` that does not equal `client_versions_after`.
68. An ERROR record and a `no_usable_setting` record carry the fields "Record model" requires:
    `model`, `effort`, `before`, `after`, `context`, `day_table_sha256`, `first_response_day` and
    `earliest_test_date` null, `measures` empty, `response_days_*` and `kept_days_*` 0, and with
    ERROR also `kept_rows_other_offset`, `settings_not_kept` and `days_not_kept` 0; the notices
    that still apply (F9, F17 in their ERROR wording; F14, F22, F23, F25 for
    `no_usable_setting`) print in the text order.
69. Every new state round-trips: the record is written, validated again from its JSON, and the
    text, Markdown and HTML rendered from the restored record equal those of the first run. The
    states covered are `kept_table` `not_read`, `absent`, `read` and `unreadable`, `since_given`
    both ways, `keep` both ways, a day of each `source`, and a `no_usable_setting` tool beside a
    tool with a result.
70. F18 to F26 in all three formats: each prints where "Text output, in this order" and the
    Markdown and HTML rules put it, is absent when its condition does not hold, and F21 prints
    its zeros. The HTML page draws a kept day as an open circle and a logs day as a filled one,
    has no script and no external reference, and holds no value that is not in the record.
71. With no selected setting, the Markdown block ends with the F10 text and no footer, and a
    snapshot holds that block; a tool with a selected setting and a result other than ERROR keeps
    the footer with its digest.

**Self-check and distribution.**

72. The self-check file holds the new cells: the A1-preserving null cell and one exact-margin
    cell per measure, the competitive-choice null and margin cells, each on 20,000 histories,
    with wrong REAL DROP at most 0.0283 in a null cell and, in a margin cell, both the tool's
    wrong NO DROP and the moved measure's own `no drop` finding at most 0.0283 (added after the
    adversarial review: the tool-level rate alone could not show a wrong margin of one measure);
    the script fails when a gated cell would run on fewer histories, and its gates are explicit
    checks, not `assert` statements. It also holds
    the report-only cells (many more after-period responses; the newly adopted setting at 1.15,
    with 535 of 20,000 at 14 after against 16 before and 415 of 20,000 at 7 against 21), each
    naming the assumption it breaks, the streak-check rates conditional on passing the check, the
    power cells with their generated, tested and stopped counts, the design 14 after against 16
    before in the null, correlation and power tables, the weekly-cycle and regime-switching
    generators, and the counterexample label `Demonstration outside A1 (arci-logs/2): `.
73. The documented command `uvx --python 3.14 realornoise` appears in the README first screen,
    the recipe, the package README and both skills; the plugin and the Codex skill pin
    `uvx --python 3.14 realornoise==2.4.0`; both distributions report version 2.4.0 and keep
    `requires-python` at `>=3.11`.

**After the adversarial review.**

74. A table file of 0 bytes is `absent`: F24 does not print, `kept_table` is `absent`, and a
    `--keep` run writes a valid table in its place.
75. An empty value for `--keep-dir` prints the general usage line, exits 3, and reads and writes
    nothing; no file appears in the current directory.
76. After a successful `--keep` run the table directory holds the table and no other file that
    the run created. A leftover regular file in that directory whose name begins with
    `.realornoise-` is gone after the run; a file with any other name is left as it was. A run
    whose write fails leaves no empty file at any target path that did not exist before.
77. Two `--keep` runs that overlap keep the rows of both: the second writer merges with the
    table the first one wrote (a unit test with an injected pause between the first read and the
    write holds this; an acceptance test cannot time two processes).

**After the last check.**

78. The tool removes no directory. After a `--keep` run whose write fails, a table directory
    that did not exist before the run exists and is empty, with any parents the run created,
    and every directory that existed before still exists with its mode.
79. A `--json`, `--markdown` or `--html` path whose file name begins with `.realornoise-`, in
    any letter case, prints the general usage line, exits 3, and reads and writes nothing. The
    names `.realornoise.json` and `realornoise-report.json` are accepted. A path that is a
    symbolic link to a file whose name begins with `.realornoise-` is refused in the same way,
    and neither the link nor its target is changed.
