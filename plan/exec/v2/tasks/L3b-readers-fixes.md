# L3b: reader changes after the second records review

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` and follow
its rules. The records were revised after you wrote the readers; read record 0016, decision
6 ("Privacy is a tested property") and "Record model" (`ReaderCounters`), and the contract's
"What is compared", in their current text. Where this brief and `L-CONTRACT.md` differ on a
record field, this brief wins.

## You own

`src/arci/logs/records.py`, `discover.py`, `claude_code.py`, `codex.py`, and the reader tests
and `synth_logs.py` under `tests/unit/logs/` (not `rank_test.py` or its test).

## Changes

1. **Effort is an identity, like the model.** Replace the `Effort` literal on records by
   `effort: int`, an index into `ReadResult.efforts: tuple[str | None, ...]`, where the entry
   is the effort as written when it is in the closed list (`minimal`, `low`, `medium`,
   `high`, `xhigh`, `max`) and `None` otherwise. Two different unknown efforts get two
   indexes. Keep `EFFORTS: frozenset[str]` public.
2. **Responses without a setting.** A response whose model or effort is missing (not a
   non-empty string) is not returned; count it in `responses_without_setting`.
3. **Tighter model grammar.** `render_model(raw)` returns the id as written only when: it is
   at most 48 characters, lower-case ASCII; split at `-`, `.` and `_` every part is a word in
   `MODEL_WORDS`, or a number of at most two digits, or a letter-digit token of at most
   three characters (`4o`, `o3`, `r1`), or an eight-digit number starting with `20`; and at
   most one part is such a date. Otherwise `None`. `gpt-12345678-87654321`,
   `gpt-123-456`, `acme-payroll-secret` return `None`.
4. **Stable order for unknown names.** `ReadResult` gains `model_order: tuple[int, ...]` and
   `effort_order: tuple[int, ...]`: the indexes sorted by the raw strings as text. Later
   code numbers `model-N` and `effort-N` and breaks ties with these, without ever seeing a
   raw string.
5. **One response, one count across files.** Claude Code: a `message.id` already seen in an
   earlier file of the same `read` call is skipped and counted in `responses_duplicate`
   (paths are read in the order given). Codex: the key is the session id of the file's
   `session_meta`, the event timestamp and the complete `total_token_usage` object; a
   repeat, in the same file or a later one, is skipped and counted in `responses_duplicate`.
6. **`--project` on Codex stops early.** When `project` is given and the `session_meta`
   working directory is outside it, read no further line of that file and count it in
   `files_outside_project`. (Claude Code keeps reading: its working directory is per line.)
7. **Timestamps.** A timestamp without a zone is treated as a missing field
   (`lines_lacking_field`). Later than `now`: `records_in_future`, as before.
8. **Counters.** `ReaderCounters` has exactly the fields of the record model:
   `files_read`, `files_unread_compressed`, `files_unreadable`, `files_outside_project`,
   `lines`, `lines_not_json`, `lines_unknown_type`, `lines_lacking_field`,
   `records_in_future`, `responses`, `responses_duplicate`, `responses_without_reasoning`,
   `responses_without_setting`, `edits_denied`, `edits_unmatched`.
9. **Claude Code effort precedence** stays `effort`, then `perTurnEffort`.

## Tests

Update the existing tests and the generator, and add: two unknown efforts stay separate; a
response without model or effort is counted and not returned; the grammar cases of item 3
(include the canary `gpt-12345678-87654321` as a model id in synthetic logs and assert it
appears in no record field and no `repr`); a session copied into a second file is counted
once for each tool; a Codex file outside the project is not read past its first line (prove
it with a file whose later lines would raise or be counted); a naive timestamp.

## Done when

`.venv/bin/pytest tests/unit/logs -q` passes; ruff format, ruff check and basedpyright are
clean on your files; `shasum -a 256 -c FROZEN.sha256` still passes.
