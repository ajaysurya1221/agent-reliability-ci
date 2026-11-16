# Session logs read by `arci logs`

These formats are not documented by their vendors as public interfaces and can change.
The readers were checked against Claude Code client versions 2.1.309, 2.1.321 and 2.1.325
and Codex CLI versions 0.154.0 and 0.167.0 on one machine.
`arci logs` is untested on Windows; Windows case rules are unchanged.
This describes the readers in [the repository](../src/arci/logs/), not a vendor contract.
The [statistics](STATISTICS_LOGS.md) define the day table and comparison;
[record 0017](design/0017-logs-2.md) defines the output record and fixed texts.

In 2.4.0 the readers return client-version names and also return main-thread and
sub-agent responses that lack a model or an effort. Those responses count only toward
context counts and the version list, never toward responses or day values. The readers
take model and effort names from the kept table so labels stay stable across runs.
Context counts can therefore differ from those 2.3.0 printed for the same logs.
2.4.0 follows the definition in the records.
Each reader returns a version identity per response, with the matching version string
or null for a name outside `^[0-9]{1,5}(\.[0-9]{1,5}){1,3}$`.

## Files and order

Claude Code's root is `$CLAUDE_CONFIG_DIR/projects`, or `~/.claude/projects` when the
variable is absent or empty. `--claude-dir DIR` replaces the projects directory itself.
The reader discovers `.jsonl` files recursively, except files named `journal.jsonl`.
Main sessions normally use `<root>/<project-dir>/<session>.jsonl`; sub-agent files sit
below session folders under `subagents/**/agent-*.jsonl`.

Codex's root is `$CODEX_HOME`, or `~/.codex` when the variable is absent or empty.
`--codex-dir DIR` replaces that home directory. The reader walks `sessions` and
`archived_sessions` recursively for names starting with `rollout-` and ending in
`.jsonl` or `.jsonl.zst`. Session paths normally include `sessions/YYYY/MM/DD/`.
Codex compresses sessions idle for 7 days to `.jsonl.zst`
([Codex compression source](https://github.com/openai/codex/blob/main/codex-rs/rollout/src/compression.rs),
read 16 Nov 2026), which is why `uvx --python 3.14 realornoise` is the documented command.
Compressed files use Python 3.14's `compression.zstd`. Earlier Pythons count them as
unread compressed files, report the count (and, when other files give a result, that the
result uses the rest), and print `uvx --python 3.14 realornoise`. No decompression dependency is installed.

Each tool's files are sorted by their paths relative to the root, written with `/`.
Lines are read in file order. The first assembled copy of a response wins, even when
later copies disagree. Claude Code uses the message id across files. Codex uses the
session id, event timestamp and complete cumulative-usage object, including all its keys;
the object is compared independent of key order. Within one Codex file, a token-count
event whose cumulative usage equals that of the previous token-count event is a repeat,
whatever its timestamp and whether or not a session id exists. Without a session id or
cumulative-usage object the cross-file identity cannot be formed.

`--project PATH` is made absolute against the current directory, without touching the
file system, before any comparison; `~` is expanded. It compares path components lexically: the working directory must
be that path or below it. It does not resolve symlinks. Claude Code is filtered per response;
its file still gets read. Codex reads only the first line of files outside the project.
Reader counters describe the scan, including sub-agents and, for Claude Code, responses
outside the project. They are not the selected setting's usable-day denominators.

## Claude Code

Each line is a JSON object; top-level `type` selects `assistant` or `user`. Other types,
including `system`, `attachment` and `api-request`, are unused. A line with
`isApiErrorMessage: true` is unused too; false does not exclude it. Unknown keys are ignored
and are not counted. Prompt text, answer text and thinking signatures are not output.

An assistant line uses:

| Field | Use |
|---|---|
| `message.id` | Response identity within and across files. |
| `timestamp` | A zoned ISO timestamp; the first line fixes the response time. |
| `message.model` | Model setting from the first line. |
| `effort`, else `perTurnEffort` | Effort setting from the first line; the first non-empty string is used. An empty or non-string `effort` falls back to `perTurnEffort`. |
| `cwd` | Working directory on the first line, used for the project filter and context counts. |
| `version` | Client version on the first line, retained as an identity and a bounded name or null. |
| `isSidechain` | Exactly `true` means a sub-agent response. |
| `message.usage.output_tokens_details.thinking_tokens` | Non-negative integer reasoning count, excluding booleans; missing, null or invalid means unknown, never zero. |
| `message.content[]` | `tool_use` blocks supply `id` and `name` for matching results. Other blocks do not supply a measure. |

One `message.id` can occupy several content-block lines. It becomes one response with
the first line's setting, timestamp and context, accumulated tool calls, and the last
line's reasoning count. A later line cannot repair a missing first setting or replace a
zone-less first timestamp. A valid main-thread response time can set the newest day even
when that response has no setting. `message.stop_reason`, text blocks and thinking
signatures do not decide whether a response is complete.

User lines use `message.content[]` blocks with `type: "tool_result"` and `tool_use_id`.
They match an earlier `tool_use` id in the same file. `Edit`, `Write`, `MultiEdit` and
`NotebookEdit` are file-edit tools. `is_error: true` means failure; absent or false means
success. A string-valued `message.content` supplies no result blocks. The result's own
`timestamp` gives its day; model, effort, project membership and main-thread status come
from the response that made the call.

The presence of top-level `toolDenialKind`, or `permissionDecision.decision: "reject"`,
makes a matched file-edit result a denial: it is left out, not treated as failure.
Unmatched result ids are counted and left out. A result matched to a non-edit tool is
neither an edit nor an unmatched result. Calls are collected only from retained responses,
so a result in a duplicate session can be unmatched when its response was already seen.

## Codex

Each line has `timestamp`, `type` and `payload`. The first line must be `session_meta`.
Without that header the rest of the file is not read. Its payload supplies `id` (session
identity), `cwd`, `cli_version` and `thread_source`. Exactly `"subagent"` means not the
main thread; `"user"` or an absent value means main thread. With a project filter,
an outside or missing working directory stops reading after this line.

`turn_context.payload.model` and `.effort` apply until the next `turn_context` line.
A response is an `event_msg` whose `payload.type` is `token_count` and whose `payload.info`
is an object. Null or absent `info` produces no response. Other event types are counted as
unused. The response uses the event's timestamp and the latest turn context.
`info.last_token_usage.reasoning_output_tokens` gives the reasoning count; missing,
null, negative, boolean or non-integer counts remain unknown.
`info.total_token_usage`, together with the session id and event time, supplies the
duplicate identity described above. Missing model or effort leaves the response out of
the setting comparisons and increments its counter.

No answer-text assembly is needed: the token-count event supplies the response measure.
There is no Codex file-edit measure, since edits can go through shell commands. Client
versions supply identities and bounded names; working directories become counts, never printed strings.

## Counters and records left out

The JSON output includes every `ReaderCounters` field below. Counts can overlap: a file
opened before a read error counts as both read and unreadable. Nothing assembled from
an unreadable file is retained. Counters are not an exhaustive partition of input.

| Field | Meaning |
|---|---|
| `files_read` | Files opened, including a Codex file left after its first line. |
| `files_unread_compressed` | Compressed Codex files skipped because stdlib zstd is unavailable. |
| `files_unreadable` | Files that could not be opened, or that failed while being read or decompressed. |
| `files_outside_project` | Codex files skipped after the header's working-directory check; always zero for Claude Code. |
| `lines` | Every physical line read, including a line that fails decoding; only the first line of a Codex file outside the project. |
| `lines_not_json` | Invalid UTF-8, invalid JSON, non-object JSON and JSON constants the decoder refuses. |
| `lines_unknown_type` | Unused or missing line types, Claude Code API-error lines, and Codex events other than token counts. Unknown keys do not increment this. |
| `lines_lacking_field` | Used lines lacking fields needed to recover a response or timed edit result, such as a message id or valid timestamp. Missing reasoning and setting have separate counters. |
| `records_in_future` | Responses or matched file-edit results stamped later than the one start instant, left out. |
| `records_without_timezone` | Response lines or matched file-edit results with a valid but zone-less timestamp, left out. |
| `responses` | Responses kept after duplicate, time and setting checks, including sub-agents; a missing reasoning count is still a response. |
| `responses_duplicate` | Later copies skipped by the identity rules; Claude Code counts a duplicate id once per later file. |
| `responses_without_reasoning` | Kept responses with an unknown reasoning count. |
| `responses_without_setting` | Responses left out because model or effort is missing, empty or not a string. |
| `edits_denied` | Matched Claude Code file-edit results excluded as permission denials. |
| `edits_unmatched` | Claude Code results matching no recorded call of any tool, left out. |

A line that is not valid UTF-8 is a line that is not JSON; it does not make the
file unreadable. A file is unreadable only when it cannot be opened, or fails while being read or decompressed;
nothing from an unreadable file is used. A byte-order mark at the start of a file is
ignored. A timestamp before 2000-01-01 or after 2200-01-01 is a missing field.
Discovery returns only regular files, including symlinks to regular files. Paths that are
not regular files (pipes, devices and directories) are not discovered and are counted nowhere.

The run reads the clock once. Timestamps use that instant's local UTC offset throughout
the calendar, or offset zero with `--utc`; this does not reconstruct historical daylight
saving offsets. The main thread of one selected model and effort setting supplies the
day table. See [the recipe](recipes/logs.md) for usable days, results and notices.

Model and effort names pass the bounded rendering rules in [record 0017](design/0017-logs-2.md).
Accepted names are disclosed in full; other names become distinct `model-1`, `effort-1`
style labels. No log text, raw directory, rejected client version or exception text is printed.
After-period client versions use all in-project responses, including other settings and
sub-agents. Up to three matching names are listed in descending numeric-tuple order;
equal tuples use ascending text order (`1.01` before `1.1`). The `+k more` count includes
all other distinct versions, matching or not. With no matching name, the line is omitted.

## Kept day table: `realornoise-days/1`

`days-1.json` lives in `--keep-dir DIR`, else non-empty `$REALORNOISE_HOME`, else
`~/.realornoise`. It is UTF-8 JSON, sorted keys, no indent, with a final newline.
Its top-level object has exactly two fields:

| Field | Meaning |
|---|---|
| `schema` | Exactly `realornoise-days/1`. |
| `rows` | Row objects sorted by `(tool, utc_offset_minutes, model, effort, day)`, with no duplicate key tuple. |

Each row has exactly these fields:

| Field | Meaning |
|---|---|
| `tool` | `claude-code` or `codex`. |
| `utc_offset_minutes` | Integer strictly between -1440 and 1440; the writing run's fixed offset. |
| `model` | Model id passing the bounded model grammar; aliases are never kept. |
| `effort` | One of `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`, `persistent`. |
| `day` | Calendar date as `YYYY-MM-DD` at this offset. |
| `responses` | Non-negative count of this setting's main-thread responses, including unknown reasoning counts. |
| `reasoning` | At most 5,000 `[count, frequency]` pairs. Counts are non-negative integers in strictly ascending order, including zero; frequencies are positive integers. |
| `reasoning_unknown` | Non-negative number of responses without a known reasoning count. |
| `edits` | Claude Code: non-negative file-edit result count, excluding denials and unmatched results. Codex: null. |
| `edits_failed` | Claude Code: integer from zero through `edits`. Codex: null. |

`responses` must equal `reasoning_unknown` plus all histogram frequencies. A row needs
at least one response or edit. Integer fields reject booleans and decimal numbers.
Extra fields, duplicate JSON keys, invalid names, malformed dates, unsorted or duplicate
rows or counts, invalid totals, non-regular files and files over 33,554,432 bytes are rejected.
The whole invalid table is left unused; `--keep` does not replace it. The writer shares the
32 MiB limit. Writes are staged with requested reports and rolled back together on failure.
The file has mode 0600; newly created directories have mode 0700.

The table stores counts and settings, not prompts, answers, paths, version strings or
response ids. It has no integrity seal or authentication. For merging, pruning, retention
limits and deletion, see [Keeping days](recipes/logs.md#keeping-days-beyond-the-vendors-retention).
