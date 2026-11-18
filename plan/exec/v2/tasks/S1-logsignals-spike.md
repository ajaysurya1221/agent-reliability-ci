# S1: spike for the log-signals study (go or no-go before any analysis)

Decision D-23 in `plan/exec/v2/DECISIONS.md` is the authority for this task. Read it first.

## The question the study would ask

In real coding-agent sessions, do the signals `arci logs` reads (the share of file edits
that failed; reasoning per response) go with an outcome that is not judged from the same
transcript? This spike does **not** answer that. It only finds out whether public data
can.

## The data

SWE-chat, `SALT-NLP/SWE-chat` on Hugging Face (licence ODC-By; version 2 of 2 Oct 2026:
17,968 sessions, 707 repositories, 17,819 raw transcripts, 47 GB in all; paper
arXiv 2604.20779). Access is gated: the maintainer accepts the conditions and downloads
the files. No agent signs in, and no agent handles a token.

Facts read from the public dataset page on 18 Nov 2026 (not yet from the files):

- `sessions.parquet`: one row per session, with `repo_id`, `agent`, `model`,
  `created_at`, token totals, and attribution columns recorded by the capture tool
  (`agent_lines`, `human_added`, `human_modified`, `human_removed`, `total_committed`,
  `total_lines_changed`, `agent_percentage`, `attribution_metric_version`).
  `session_success` is a score given by a model and is null where not annotated.
- `conversations.parquet`: one row per turn; token columns hold input, output and cache
  counts only. No reasoning-token column and no error flag for tool results; tool results
  are cut to 10 KB.
- `transcripts/{session_id}.jsonl`: the agent's own complete record. Whether it keeps the
  native usage fields (`message.usage.output_tokens_details.thinking_tokens`) and
  `tool_result.is_error` is **not stated** and is the main unknown.
- `commits.parquet` holds author names and email addresses. The spike does not need it
  and it is not downloaded.

## Rules

- Change nothing under `src/arci`, no pinned file, no docs. No git command that changes
  state. Never open anything under `~/.claude`, `~/.codex` or `~/.realornoise`. No network.
- The data lives outside the repository, in the folder the brief's caller names
  (`DATA_DIR`). Read it; never copy it into the repository or the scratch folder.
- **Counts only.** No output, error message or report may hold transcript text, a prompt,
  a file path from a session, a user name, a repository name or a session id. Repositories
  are counted, not named. A canary test plants a unique token in every text field of a
  synthetic input and fails if it appears in any output.
- **No joint look.** The spike computes marginal counts. It never tabulates, plots,
  correlates or prints a signal against an outcome, in any form, for any subset. The
  registration has to be written before anyone sees that.
- Deterministic: no unseeded randomness; any sample is chosen by a hash of the session id
  with a salt named in the report, never by a column value.
- Scratch code first (the caller names `SCRATCH_DIR`). On a "go" it moves to
  `bench/logsignals/` on branch `v2/logsignals`.

## Stage A: tables (after the maintainer downloads three files)

Files: `sessions.parquet`, `session_logs.parquet`, `repositories.parquet`.

Report, as counts:

1. Sessions by agent and by month of `created_at`; sessions with a non-empty `model`.
2. Sessions with a non-null attribution record, split by `attribution_metric_version`;
   how many have `total_lines_changed` above 0.
3. Repositories with at least 1, 5, 20 and 50 such sessions.
4. Sessions with a transcript path, and how many of those are Claude Code or Codex.
5. A list of 300 transcript paths chosen by hash (salt in the report) among Claude Code
   and Codex sessions that have an attribution record, written to a file under
   `SCRATCH_DIR` for the maintainer's second download. The list holds paths only; it is
   not committed.
6. The terms shown at download time are the maintainer's to read; the report repeats
   what the public page and the licence say about analysis and about publishing
   aggregate counts.

## Stage B: the 300 transcripts

Run the existing readers unchanged (`arci.logs.claude_code`, `arci.logs.codex`) once per
transcript, importing the package from the worktree's `.venv`.

Report, as counts:

1. Transcripts read with no exception; lines of unknown type.
2. Responses with a known reasoning count; sessions with at least 20 such responses.
3. File-edit results, and how many carry an error flag; sessions with at least 10
   file-edit results.
4. Client versions seen, as counts per version (version strings pass the tool's own
   bounded pattern or are counted as "other").
5. Whether the session's own time stamps place every signal before the commit the
   attribution was computed against (a count of sessions where this can be established).

## Go only if all hold

1. Nothing in the licence, the public page or the conditions the maintainer reports
   forbids this analysis or the publication of aggregate counts.
2. Scaling Stage B's rates to the whole set gives at least 1,000 sessions in at least 30
   repositories that have both one shipped signal (failed-edit share or reasoning per
   response, at the tool's own minimum counts) and an attribution record with
   `total_lines_changed` above 0.
3. Repository and time identifiers are present for those sessions, so repositories can be
   split into two halves by hash.
4. The whole spike gives byte-identical output on a second run and fits on one laptop
   (state peak memory and wall time; state the disk needed for the full transcripts).

If any fails: no-go. The report then says which and why, in words a reader of
`docs/results/` can follow. No second dataset is tried before 14 Dec 2026.

## The report

`SCRATCH_DIR/REPORT.md`, at most 2 pages: the counts above in tables, the four go tests
each with "holds" or "fails" and the number behind it, what could not be established, and
the commands that reproduce it. No recommendation beyond go or no-go.
