## What

`docs/LOG_FORMATS.md` names Codex CLI 0.169.0 as a version the Codex reader was checked against, says what that check was, and says that any `thread_source` other than `subagent` counts as main thread. The test that holds the highest checked version follows. No code change.

Closes #27.

## How it was checked

- Codex CLI 0.169.0 was run once in this project (one short session, read-only sandbox). The installed CLI stayed at 0.167.0.
- The reader was run on that session alone, counts only: 1 file read, 25 lines, 2 responses, 0 lines lacking a field, 0 lines not JSON, 0 responses without a setting, 0 without a reasoning count; client version shown `0.169.0`. The result was `CANNOT TELL` (too few days), as expected for one day.
- Structure only (record types, key names, value types), compared with four of this project's 0.167.0 sessions: the same six record types, the same top-level keys, the same `token_count` fields. `session_meta` has one more key (`account_scoped`) and `turn_context` one fewer (`file_system_sandbox_policy`); the reader reads neither.
- Before that, two reviewers compared the Codex source at the release tags of 0.167.0, 0.168.0 and 0.169.0 and found no change in the fields the reader uses.
- Packaging, docs and plugin suites: 126 passed, 1 skipped. Lint and type check clean. All 76 pinned hashes match.

## Limits

- One short session with two responses. No compressed file, no sub-agent session and no side-chat file of 0.169.0 was read.
- The source of 0.169.0 can save a side chat as its own file with `thread_source` `tui_side_chat`. None was seen. The reader would count it as main thread, and the doc now says so.
