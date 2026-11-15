# L3: log readers, discovery and records

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` first and
follow its rules, the privacy rules above all. Format facts are in `L0-logs-spike.md`
("Log formats"); behaviour is in record 0016, decisions 5 and 6, and in the contract's "What
is compared". The spike's `readers.py`, `records.py` and `synth.py` are a starting point.

## You own

- `src/arci/logs/records.py`, `src/arci/logs/discover.py`, `src/arci/logs/claude_code.py`,
  `src/arci/logs/codex.py`
- `tests/unit/logs/synth_logs.py` (a test helper, not shipped), `tests/unit/logs/test_records.py`,
  `tests/unit/logs/test_discover.py`, `tests/unit/logs/test_claude_code.py`,
  `tests/unit/logs/test_codex.py`

`src/arci/logs/__init__.py` and `tests/unit/logs/__init__.py` already exist; do not edit them.
Another agent is writing `src/arci/logs/rank_test.py` and its test at the same time; do not
touch those.

## Build

1. `records.py`: exactly the names and fields of the contract.
   - `MODEL_WORDS`: a closed vocabulary. Include at least: `claude`, `opus`, `sonnet`,
     `haiku`, `fable`, `mythos`, `instant`, `gpt`, `codex`, `chatgpt`, `o1`, `o3`, `o4`,
     `mini`, `nano`, `micro`, `max`, `pro`, `turbo`, `spark`, `astra`, `omni`, `preview`,
     `latest`, `thinking`, `fast`, `high`, `low`, `medium`, `xhigh`, `gemini`, `flash`,
     `ultra`, `lite`, `exp`, `deepseek`, `chat`, `reasoner`, `coder`, `qwen`, `glm`, `kimi`,
     `grok`, `code`, `mlx`, and single letters `a` to `z` followed by nothing (for names such
     as `4o` treat a part that is digits followed by one letter, or one letter followed by
     digits, as allowed). `render_model` lower-cases nothing: an id with an upper-case
     letter, a slash, a colon, or any part outside the vocabulary returns `None`.
   - `effort_of` maps the closed list and returns `other` for anything else, including a
     missing value.
2. `discover.py`: the four functions of the contract. `claude_files` returns every `*.jsonl`
   under the root except files named `journal.jsonl`; `codex_files` every `rollout-*.jsonl`
   and `rollout-*.jsonl.zst` under `sessions/` and `archived_sessions/`. Missing directories
   give an empty list. No function prints or raises with a path in its message.
3. `claude_code.read` and `codex.read`, per the format facts and these rules:
   - A file is main-thread or not as the format facts say (Claude Code: `isSidechain`; Codex:
     `session_meta.payload.thread_source == "subagent"`).
   - Working directory: Claude Code top-level `cwd` on the line; Codex `session_meta.payload.cwd`.
     `in_project` is true when `project` is `None`, or the working directory equals it or is
     below it (compare as path parts, no file-system access). A Codex file whose first line
     is not a `session_meta` is counted in `files_unreadable` and skipped.
   - Client version: Claude Code top-level `version`; Codex `session_meta.payload.cli_version`.
   - Claude Code effort: top-level `effort`, else `perTurnEffort`, on the response's first
     line. Codex effort and model: the latest `turn_context` before the response; a response
     with no `turn_context` before it is counted in `lines_lacking_field` and skipped.
   - A Claude Code response is one `message.id` within a file (first line gives the time,
     effort, version and working directory; the usage of its last line gives the reasoning
     count; lines with `isApiErrorMessage` true are skipped). A line of type `assistant`
     without `message.id`, `message.model` or a parseable `timestamp` is counted in
     `lines_lacking_field`.
   - A Codex response is one `event_msg` whose `payload.type` is `token_count` with a
     non-null `payload.info`; skip one whose `total_token_usage` equals the previous one in
     the same file. The reasoning count is `last_token_usage.reasoning_output_tokens`.
   - Reasoning counts that are missing, negative, or not integers are `None` and counted in
     `responses_without_reasoning`.
   - File-edit results (Claude Code only; tools `Edit`, `Write`, `MultiEdit`,
     `NotebookEdit`): one `EditResult` per `tool_result` block whose `tool_use_id` matches a
     `tool_use` block of those tools earlier in the same file. It takes the model, effort and
     main-thread flag of the response that made the call, and the time of the result line. A
     result on a line carrying `toolDenialKind`, or `permissionDecision.decision == "reject"`,
     is counted in `edits_denied` and not returned. A `tool_result` whose id matches no
     recorded `tool_use` of any tool is counted in `edits_unmatched`. Codex returns no edits.
   - Times: parse ISO 8601 with `Z` or an offset into UTC. A record later than `now` is
     counted in `records_in_future` and skipped.
   - Lines that are not JSON objects count in `lines_not_json`; lines whose type the reader
     does not use count in `lines_unknown_type`; neither is an error. A file that cannot be
     opened or decoded counts in `files_unreadable`. A `.zst` file on a Python without
     `compression.zstd` counts in `files_unread_compressed`.
   - Read files as a stream, line by line; do not load a file whole. Skip a line cheaply
     (before `json.loads`) when it cannot be of a used type.
4. `tests/unit/logs/synth_logs.py`: a seeded generator of synthetic logs in both formats
   into a directory: sessions per day, main and sub-agent files, unknown line types,
   malformed lines, missing optional keys, future-dated records, denied and unmatched edit
   results, a `.jsonl.zst` copy when the interpreter can write one, and canary tokens in
   every free string: an upper-case one (`CANARY-<n>`), a lower-case one shaped like a model
   id in a field that is not the model (`canary-payroll-<n>`), and for some sessions a model
   id outside the vocabulary (`acme-payroll-secret`) and a version shaped like a private
   number. It returns what it wrote (counts per day, per setting) so tests can compare.

## Tests

- Both readers on synthetic logs: responses, reasoning counts, settings, main-thread flags,
  edit results and every counter equal what the generator wrote.
- Unknown types, malformed lines, truncated last line, missing keys, a file that is not
  UTF-8: counted, never raised.
- `render_model`: vocabulary ids pass (`claude-opus-5-5`, `claude-fable-5-2`, `gpt-6-astra`,
  `gpt-5.6`, `gpt-5.3-codex-spark`, `o3-mini`, `gpt-4o`); `acme-payroll-secret`,
  `claude-acme-payroll`, `Claude-opus`, `a/b`, an empty string and a 60-character id return
  `None`.
- No record field, and no `repr` of a `ReadResult`, contains a canary token, a working
  directory or a version string; the private model id appears nowhere, and its entry in
  `models` is `None`.
- `--project` filtering by path parts, including a path that is a string prefix but not a
  parent.
- Compressed files: read on 3.14, counted as unread on older Pythons (skip the write test
  where the interpreter cannot compress).

## Done when

`.venv/bin/pytest tests/unit/logs -q` passes (ignoring tests owned by the other agent if they
are not there yet); ruff format, ruff check and basedpyright are clean on your files;
`shasum -a 256 -c FROZEN.sha256` still passes.
