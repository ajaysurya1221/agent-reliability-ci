# Contributing

This is a single-maintainer project. The maintainer works with AI coding agents (Claude Code
and Codex) as pair-programmers; see the README's "How it was built" for the current
breakdown by release. Issues and pull requests are welcome. There is no promised response
time: reports and PRs are read and handled on a best-effort basis, the same as the security
policy says.

## Running the checks locally

```bash
uv sync
just check        # ruff format --check, ruff, basedpyright strict, pytest
just frozen       # the frozen contract files (FROZEN.sha256) are unchanged
```

Or call the tools directly, without `uv` as a wrapper:

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/basedpyright
.venv/bin/pytest
shasum -a 256 -c FROZEN.sha256
```

`just unit` and `just acceptance` run one half of the test suite at a time.
`AGENTS.md` has the full rules for anyone, human or agent, editing this repository.

## Pinned files

`FROZEN.sha256` lists the files that are the source of truth for behaviour the acceptance
tests, the statistics or the release process depend on: the core modules under `src/arci/`,
every acceptance test, `pyproject.toml`, `uv.lock`, `justfile`, `AGENTS.md`, and the frozen
docs (`AGENT_SEMANTICS.md`, `STATISTICS*.md`, `TRUST_MODEL.md`, `docs/design/**`). These
change only together with a new design record under `docs/design/` that says what changed
and why, following `docs/RELEASING.md`'s re-freeze steps. A pull request that edits a
pinned file without a new design record will be asked to drop that change; `shasum -a 256 -c
FROZEN.sha256` is checked in CI and should pass on every other pull request.

## Privacy in bug reports

**Never attach session logs, individual log lines, or file paths from your own Claude Code
or Codex logs.** They can hold the content of your prompts and your agent's replies. If you
are reporting a problem with `arci logs` or `realornoise`, attach only the tool's own
printed or written output: it already holds counts, rates, dates, and the names of the
model and effort setting being compared, and nothing from inside a session. If a report is
opened with a log line or a log file path attached, it will be edited or removed and the
reporter asked to resend without it.

For a suspected vulnerability, use private reporting as `SECURITY.md` describes, not a
public issue.

## Reporting a changed log format

Claude Code or Codex can change how they write session logs at any time; `docs/LOG_FORMATS.md`
lists the client versions the readers were checked against. If `arci logs` or `realornoise`
stops finding responses, miscounts them, or reports a read or format error against a client
version newer than the ones listed there, open an issue with the "Session log format
changed" template. Give the tool, the client version, and the `realornoise` (or
`agent-reliability-ci`) version, and paste the tool's own printed output, not a log line or
a file path. The issue template's checkbox confirms no log line or path was pasted; leave it
unchecked only if you are certain nothing from inside a log was included anyway, and say so
in the issue body.
