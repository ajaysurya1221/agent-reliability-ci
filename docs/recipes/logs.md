# A result from session logs you already have

`arci logs` reads local Claude Code and Codex session logs and compares recent days with
earlier days for one model and effort setting per tool. It runs no model and no trial.
The [statistics contract](../STATISTICS_LOGS.md) states the assumptions and limits;
[record 0016](../design/0016-logs.md) defines the output;
[log formats](../LOG_FORMATS.md) describes the readers.

## Try it in one command

```sh
uvx realornoise
```

Or install the main package:

```sh
pip install agent-reliability-ci
arci logs
```

Installation needs network access. Reading the logs sends nothing and writes nothing
unless an output path is given. Model and effort names that pass a bounded grammar are
printed in full; other names become distinct opaque labels. Raw text, client versions and
working-directory names do not appear in the output.

## Try the packaged example

```sh
arci logs --example
```

Example data, generated, not anyone's logs. This is the complete output captured in the
checkout on 2026-11-15. The banner still reports 2.2.0 before the release version change;
its numbers and text below are unchanged.

```text
realornoise 2.2.0 · reads local session logs · sends nothing · writes nothing unless asked
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
method arci-logs/1 · exact rank tests · no random numbers · day-table digest 5737f3d6ed96

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
method arci-logs/1 · exact rank tests · no random numbers · day-table digest c0b6d7c8c0d6

This shows what your logs recorded. It does not establish answer quality, a cause, or a change
to the model: your tasks, prompts, projects or client version may have changed.
For each tool above and one comparison: if nothing shifted, REAL DROP appears at most 2.5% of the
time; if a measure moved toward worse by its margin or more, NO DROP appears at most 2.5% of the
time. Both hold only if: (1) the days in this window are interchangeable when nothing changes;
(2) any date, model, effort or project you gave was not chosen from these logs; (3) a change
moves every day alike, by an amount the measure can take; (4) a change leaves the same days,
setting, reference value and earlier-day values in use. None of these is checked, and the streak
check does not prove them. Running this again and again until a result appears is not covered.
Exact statement: docs/STATISTICS_LOGS.md in the repository.

Share: --markdown FILE · --html FILE · --json FILE      Stronger evidence: arci verdict, arci run
exit 1
```

Exit 1 is expected here because Claude Code has REAL DROP, even though Codex has NO DROP.
`uvx realornoise --example` reads the same packaged data with a fixed clock.

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
   not tests of those differences. The streak line counts measures not flagged; it does
   not prove independence. Notices count other settings, unread compressed files, lines
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
Claude Code's retention can remove the older files before enough usable days accumulate.
No day table is stored automatically to outlive that retention.

Even enough days can be too variable. If any eligible measure's earlier days come in
streaks, the whole tool comparison is CANNOT TELL. Passing this check does not establish
interchangeability. Keep using the tool normally; do not scan split dates or settings until
a desired result appears. Use controlled runs when the question needs stronger evidence.

## Options

| Option | Meaning |
|---|---|
| `--tool auto\|claude-code\|codex\|both` | Default `auto` requests tools whose roots exist; if neither exists, both report no logs. |
| `--since YYYY-MM-DD` | Set the split, at most 83 days before the newest day; a later-than-newest split gives no after-days. |
| `--model NAME`, `--effort NAME` | Select names as printed, including opaque labels. Default is the most frequent setting over both periods, ties by raw text order. |
| `--project PATH` | Keep sessions whose working directory is that path or below it. |
| `--claude-dir DIR` | Replace the Claude Code projects directory. |
| `--codex-dir DIR` | Replace the Codex home containing `sessions` and `archived_sessions`. |
| `--utc` | Use UTC calendar days instead of the start instant's local offset. |
| `--example` | Read packaged synthetic logs with a fixed clock; directory options are ignored. |
| `--markdown FILE`, `--html FILE`, `--json FILE` | Write the chosen report files. |
| `--help` | Show the command's options without reading logs. |

Choose filters and dates without looking at the compared records if you intend to invoke
the bounds. The calendar uses one UTC offset, not historical daylight-saving offsets.

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
no script or external reference. JSON is the sealed `arci-logs/1` record: day tables,
exact rational test values, reader counters, context counts and rendered model and effort
names. It contains enough to recompute the result, not the original log text. The seal
checks consistency; it does not authenticate execution. Review the dates and accepted
model and effort names before sharing them.

## Inside Claude Code or Codex

In Claude Code:

```text
/plugin marketplace add ajaysurya1221/agent-reliability-ci
/plugin install realornoise@agent-reliability-ci
/realornoise:realornoise
```

The [plugin](../../plugins/realornoise/skills/realornoise/SKILL.md) runs the command and shows its output.
The printed numbers then enter that assistant's conversation.

For Codex, copy [integrations/codex/skills/realornoise](../../integrations/codex/skills/realornoise/SKILL.md)
into `~/.agents/skills/`, then invoke `$realornoise`. The printed numbers then enter that
assistant's conversation. This differs from running the CLI in a terminal, which sends
nothing itself.

## Stronger evidence

Use [`arci verdict`](verdict.md) when you have repeated pass/fail results for a baseline
and candidate. Use [`arci run`](../../README.md#controlled-trials-arci-run) to run both on
the same predeclared tasks and faults with an independent checker. These answer controlled
comparison questions that observational session logs cannot answer.
