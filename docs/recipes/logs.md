# A result from session logs you already have

`arci logs` reads local Claude Code and Codex session logs and compares recent days with
earlier days for one model and effort setting per tool. It runs no model and no trial.
The [statistics contract](../STATISTICS_LOGS.md) states the assumptions and limits;
[record 0017](../design/0017-logs-2.md) defines the output;
[log formats](../LOG_FORMATS.md) describes the readers.

## Try it in one command

```sh
uvx --python 3.14 realornoise
```

Or install the main package:

```sh
pip install agent-reliability-ci
arci logs
```

Installation needs network access. Reading the logs sends nothing and writes nothing
unless an output path or `--keep` is given. Model and effort names that pass the accepted
lists are printed in full; other names become distinct opaque labels. Up to three bounded
client-version names after the split are printed too. Raw text and working-directory names
never appear. Python 3.14 reads compressed Codex logs; uv fetches that Python.

## Try the packaged example

```sh
arci logs --example
```

Example data, generated, not anyone's logs. This is the complete output captured in the
2.4.0 checkout on 2026-11-16.

```text
realornoise 2.4.0 · reads local session logs · sends nothing · writes nothing unless asked
Example data, generated. Not anyone's logs.

Claude Code · model-1 · effort high · main thread · days at UTC+00:00
before  2026-08-09 to 2026-10-31
after   2026-11-01 to 2026-11-14   split 2026-11-01

RESULT: REAL DROP
In at least one recorded measure, the days after the split moved toward worse by more than a chance
ordering of your days explains.

measure, median day           before (days) after (days) change  finding
reasoning tokens per response 986 (42)      529 (14)     -46%    real drop
responses with no reasoning   15.0% (42)    15.0% (14)   0.0 pts no drop (margin 10 pts)
file edits that failed        10.0% (42)    10.0% (14)   0.0 pts no drop (margin 3 pts)

Context counts; differences between the periods are not tested:
client versions 1 before, 1 after, 1 in both · working directories 1 before, 1 after · sub-agent
share 0.7% -> 0.7%
Streak check: 3 of 3 tested measures were not flagged.
method arci-logs/2 · exact rank tests · no random numbers · day-table digest bc3c83e31e99

Codex · model-1 · effort high · main thread · days at UTC+00:00
before  2026-08-09 to 2026-10-31
after   2026-11-01 to 2026-11-14   split 2026-11-01

RESULT: NO DROP
No recorded measure moved toward worse by its margin or more. This does not say anything improved.

measure, median day             before (days) after (days) change  finding
reasoning tokens per response   984 (42)      962 (14)     -2%     no drop (margin 25%)
responses with no reasoning     15.0% (42)    15.0% (14)   0.0 pts no drop (margin 10 pts)
reasoning at one repeated value 11.8% (42)    11.8% (14)   0.0 pts no drop (margin 10 pts)

Context counts; differences between the periods are not tested:
client versions 2 before, 2 after, 2 in both · working directories 2 before, 2 after · sub-agent
share 0.7% -> 0.7%
Streak check: 3 of 3 tested measures were not flagged.
method arci-logs/2 · exact rank tests · no random numbers · day-table digest b267f6b674a9

This shows what your logs recorded. It does not establish answer quality, a cause, or a change
to the model: your tasks, prompts, projects or client version may have changed.
For each tool above and one comparison, if (1) the days in this window are interchangeable when
nothing changes, whatever their number of responses, and (2) to (4) below hold, then REAL DROP
appears at most 2.5% of the time if nothing shifted, and NO DROP at most 2.5% of the time if a
measure moved toward worse by its margin or more. When days resemble their neighbours or work comes
in phases, (1) fails: in the cases it tested, the self-check measured wrong REAL DROP up to
18.1%, with 14 days after the split and 16 before; other patterns can
give more. The conditions (2) to (4) are: (2) any date, model, effort or project you gave was not
chosen from these logs; (3) a change moves every day alike, by an amount the measure can take; (4) a
change leaves the same days, setting, reference value and earlier-day values in use. None of these
is checked, and the streak check does not prove them. Running this again and again until a result
appears is not covered. Exact statement: docs/STATISTICS_LOGS.md in the repository.

Share: --markdown FILE · --html FILE · --json FILE      Stronger evidence: arci verdict, arci run
exit 1
```

Exit 1 is expected here because Claude Code has REAL DROP, even though Codex has NO DROP.
`uvx --python 3.14 realornoise --example` reads the same packaged data with a fixed clock.

## Read the output

1. The header names the program version and its local-only behaviour. The example label
   appears only for generated data. Each tool's scope gives the selected model and effort,
   main-thread restriction and fixed UTC offset. Other settings are counted but not compared.
2. The period lines give calendar bounds and the split date. The result and its next
   sentence say what the comparison found. By default, the split is 13 days before the
   newest main-thread response: up to 14 after-days and 84 earlier calendar days.
3. Each table cell is the median daily value followed by the number of usable days.
   Reasoning tokens use each day's median positive count. The other rows are daily shares:
   zero-reasoning responses, failed file edits for Claude Code, and positive reasoning counts
   equal to the pooled most common value for Codex. Token changes are relative percentages;
   share changes are percentage points. A dash means unavailable. The finding is each
   measure's test result; `not used` means another measure's streak stopped the comparison.
4. Context counts show distinct client versions and directories and the sub-agent share,
   not tests of those differences. A separate line lists up to three accepted client
   versions after the split, highest first, with a count of those not shown. The streak line
   counts measures not flagged; it does not prove independence. Notices count other settings, unread compressed files, lines
   lacking fields, future records and unreadable files. The method and digest identify the
   rule and day table, not who produced the logs.
5. The limits state what this cannot show and the assumptions for the error bounds.
   The share line names output options and stronger evidence. The final exit is 1 if any
   non-error tool is REAL DROP, else 2 if any is CANNOT TELL, else 0. If every requested
   tool is ERROR, it is 3. A usage error or failure to write a requested file also exits 3.

## Three results, and reading errors

| Result | What it says | What it does not say |
|---|---|---|
| REAL DROP | At least one recorded measure moved toward worse beyond a chance ordering of days. | The model changed, answers got worse, or the drop exceeded a practical margin. |
| NO DROP | Every recorded measure rules out its margin under the stated assumptions. | Anything improved, or no smaller change happened. |
| CANNOT TELL | The available days do not distinguish a shift from noise, or a streak stops the comparison. | There was no change. |

ERROR means no logs, no readable file or no recovered response for a requested tool.
When its directory option was given and no logs were found, the text is
`No session logs found for {Tool} under the directory given with {flag}. Or try: realornoise --example`
where the flag is `--claude-dir` or `--codex-dir`. The directory itself is never printed.
Other tools can still have results. The margins are a 25% fall in reasoning tokens,
10 percentage points for no-reasoning and repeated-value shares, and 3 points for failed
file edits. A measure is a recorded quantity, not answer quality.

The directional bounds apply to one tool and one comparison under unchecked assumptions:
interchangeable days when nothing changes, choices not made from the compared logs,
a uniform admissible shift, and the same usable days, setting, reference and earlier-day
values. Tasks, prompts, projects and clients can all change. Repeated checking until a
result appears is outside those bounds. The [self-check](../results/logs-selfcheck.md)
shows errors above the nominal bound for short correlated histories, even with the check.

## Why CANNOT TELL is usual with a short history

A measure needs 5 usable after-days and 10 usable before-days. A reasoning-token or
repeated-value day needs 20 known counts, including 10 positive counts; a no-reasoning
share needs 20 known counts; a file-edit share needs 10 results. Unknown counts are not
zeros. Sub-agents and other settings do not fill gaps for the chosen setting.
When the reason is `too_few_days`, text, Markdown and HTML show the setting's first response date
in the window and its response-day counts before and after the split. With no `--since`,
text, Markdown and HTML also give the earliest test date, a best case if this setting is
used every day after the last log day, each new day is usable, and earlier days remain on
disk or kept. This is not a promise of a decisive result. It counts from the last log day,
so the date can already be in the past. Claude Code also prints its retention notice.
Other CANNOT TELL reasons do not print this date.

Even enough days can be too variable. If any eligible measure's earlier days come in
streaks, the whole tool comparison is CANNOT TELL. Passing this check does not establish
interchangeability. Keep using the tool normally; do not scan split dates or settings until
a desired result appears. Use controlled runs when the question needs stronger evidence.

## Options

| Option | Meaning |
|---|---|
| `--tool auto\|claude-code\|codex\|both` | Default `auto` requests tools whose roots exist; under `auto`, a tool whose directory option is given is always requested, also when the directory does not exist. If neither root exists and no directory option was given, both report no logs. |
| `--since YYYY-MM-DD` | Set the split, at most 83 days before the newest day; a later-than-newest split gives no after-days. |
| `--model NAME`, `--effort NAME` | Select names as printed, including opaque labels. Default is the setting with the most main-thread responses after the split, among candidates matching these filters. If none has an after-response, use counts over the whole window. Ties use raw model, then raw effort, in code-point order. Kept rows participate in these counts. |
| `--project PATH` | Keep sessions whose working directory is that path or below it. |
| `--claude-dir DIR` | Replace the Claude Code projects directory. |
| `--codex-dir DIR` | Replace the Codex home containing `sessions` and `archived_sessions`. |
| `--utc` | Use UTC calendar days instead of the start instant's local offset. |
| `--example` | Read packaged synthetic logs with a fixed clock; directory and keep options are ignored after usage checks. No kept table is read or written. |
| `--markdown FILE`, `--html FILE`, `--json FILE` | Write the chosen report files. |
| `--keep` | Read the kept table and save daily counts after the run. |
| `--keep-dir DIR` | Choose the table directory; implies `--keep`. |
| `--ignore-kept` | Do not read or use the kept table. Cannot be combined with either keep option. |
| `--help`, `-h` | Show the command's options without reading logs. |

The two keep-option conflicts exit 3 before reading logs or writing files:
`--keep cannot be used with --project.` and `--ignore-kept cannot be used with --keep.`
Both also apply when `--keep-dir` implied `--keep`, including with `--example`.

Choose filters and dates without looking at the compared records if you intend to invoke
the bounds. The calendar uses one UTC offset, not historical daylight-saving offsets.

## Keeping days beyond the vendor's retention

```sh
uvx --python 3.14 realornoise --keep
```

Claude Code deletes session files after 30 days by default. Its setting is
`cleanupPeriodDays` ([settings reference](https://code.claude.com/docs/en/settings-reference),
read 15 Nov 2026). `--keep` saves main-thread daily counts, dates, UTC offsets and accepted
model and effort names. It saves no prompts, answers, paths or client versions.
Settings shown by aliases are not kept. Days with more than 5,000 distinct reasoning
counts are not kept; the output counts these omissions.

The file is `days-1.json` under `--keep-dir DIR`, else `$REALORNOISE_HOME` when non-empty,
else `~/.realornoise`. The directory is created with mode 0700 and the file with mode 0600.
An existing directory keeps its mode. The table is read on later runs even without `--keep`;
`--ignore-kept`, `--project` and `--example` skip it. `--keep` writes every accepted setting
from the newest log day back through 180 days, independent of model, effort or date filters.
Older rows of that requested, readable tool are pruned. The table is not a permanent archive.

For a day present in both sources, the row with more responses wins; on equal responses,
more file-edit results wins; on an exact tie, logs win. The whole row is used, never a mix.
Kept days are counted in the output and drawn as open circles in HTML. Context and reader
counts still come from logs alone. The table cannot advance the newest day or turn missing
logs into a result. Invalid tables are not used; a `--keep` run does not overwrite one.

A table of 0 bytes is absent and a `--keep` run replaces it. An empty `--keep-dir`
is refused with the general usage line and exit 3, before reading or writing anything.
Placeholders used to check target names are removed before staging. With `--keep`, the
writer locks the table directory, reads the table again, merges and writes it under that
lock, so overlapping runs keep each other's rows. Where directory locking is unavailable,
the run proceeds without it. A table directory that cannot be opened for
the lock is a write error. The tool never removes a directory. The table directory
and any missing parents are created before staging files, with mode 0700. If the
write fails, those directories stay, empty; existing directories keep their mode.
The tool assumes no other program removes or replaces the table directory while a
run uses it.
The result still uses the table read at the start.
After a successful write, leftover regular files whose names begin with `.realornoise-`
are removed from the table directory while the lock is held. Output file names
beginning with `.realornoise-`, compared after Unicode normalization (NFKC) and
case folding, including symbolic links that resolve to such names, are refused
with the general usage line and exit 3 before any read or write. Other names are left alone.
Other outputs use `.realornoise.out-` temporary names, which the table cleanup never
removes. Without a lock, an overlapping `--keep` run can fail with the write error
and leaves the table and all requested outputs as they were.

A keyboard interrupt before the last move restores replaced files, removes new empty
targets and ends with the write error and exit 3. After the last move the files are
already written, and the run still ends with that error. An interrupt can leave a
`.realornoise.out-` temporary file beside a report.
A process killed outright restores nothing and can leave replaced files, empty new targets
or temporary files.
A `.realornoise.out-` file left beside a report may be deleted by hand.

The retention promise assumes immutable records, no late backdated arrivals and whole-file
deletion strictly after 720 hours. Each deleted day must have been captured whole before deletion, with successful captures
at most 29 days apart. For admitted rows, retained and undeleted histories then give the
same day values and results at the same instant, options, UTC offset and window, as checked
on synthetic histories. A day never captured whole cannot be recovered. Days with only
file-edit results are outside the tested promise. Changing the offset, rejected names,
rows above the count limit, edited logs or a longer gap also fall outside it. Partial days
or a changed reader can affect one period differently and break the statistical assumptions.

To delete kept history, delete `days-1.json` from the directory you chose. For the default:

```sh
rm ~/.realornoise/days-1.json
```

Omit `--keep` on later runs to leave it absent. The file format and validation limits are in
[LOG_FORMATS.md](../LOG_FORMATS.md#kept-day-table-realornoise-days1).

## Compressed Codex logs

Codex can write `.jsonl.zst` files. Python older than 3.14 skips them, counts them and
reports that the result uses the remaining files. To read them:

```sh
uvx --python 3.14 realornoise
```

Both distributions support Python 3.11 onward. The explicit interpreter option matters:
`uvx` does not choose Python 3.14 just because a tool needs it for compressed files.

## Share the numbers

```sh
arci logs --markdown comparison.md --html comparison.html --json comparison.json
```

Markdown is a block for an issue thread: scope, result, table, context counts and limits.
HTML is a self-contained page with the same information and daily strip charts. It has
no script or external reference. JSON is the sealed `arci-logs/2` record: day tables,
exact rational test values, reader counters, context counts and rendered model and effort
names, plus bounded client versions, kept-day sources and short-history fields. It contains enough to recompute the result, not the original log text. The seal
checks consistency; it does not authenticate execution. Review the dates and accepted
model, effort and client-version names before sharing them.

## Inside Claude Code or Codex

In Claude Code:

```text
/plugin marketplace add ajaysurya1221/agent-reliability-ci
/plugin install realornoise@agent-reliability-ci
/realornoise:realornoise
```

The [plugin](../../plugins/realornoise/skills/realornoise/SKILL.md) tells Claude to run `uvx --python 3.14 realornoise==2.4.0` and to show its output.
Whether Claude Code asks you first depends on your permission mode and settings. Neither skill asks for
`--keep`; run that option yourself in a terminal when you want to store counts.
Everything the command prints then enters that assistant's conversation.

For Codex, copy [integrations/codex/skills/realornoise](../../integrations/codex/skills/realornoise/SKILL.md)
into `~/.agents/skills/`, then invoke `$realornoise`. Everything the command prints then enters that
assistant's conversation. This differs from running the CLI in a terminal, which sends
nothing itself.

## Stronger evidence

Use [`arci verdict`](verdict.md) when you have repeated pass/fail results for a baseline
and candidate. Use [`arci run`](../../README.md#controlled-trials-arci-run) to run both on
the same predeclared tasks and faults with an independent checker. These answer controlled
comparison questions that observational session logs cannot answer.

The self-check measured wrong REAL DROP up to 18.1% (362/2000, Wilson 95% interval
[0.164743, 0.198480], seed 18112185), with 14 days after and 16 before in regimes:
work that comes in phases can break the stated bound, and other patterns can give more.
