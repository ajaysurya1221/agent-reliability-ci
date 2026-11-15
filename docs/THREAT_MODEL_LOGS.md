# realornoise threat model

`realornoise` and `arci logs` read local files. They do not run a model or a trial.
This page covers the installed command. Installing it with uv or pip can use the network.

## Reads and writes

Claude Code logs are `.jsonl` files below `~/.claude/projects`, or
`$CLAUDE_CONFIG_DIR/projects`; `--claude-dir` replaces that root. Codex logs are
`rollout-*.jsonl` and `.jsonl.zst` below `~/.codex/{sessions,archived_sessions}`, or the
same folders under `$CODEX_HOME`; `--codex-dir` replaces that home. Discovery follows
symlinks to regular files. `--example` reads only packaged synthetic logs.

An existing `days-1.json` is read from `$REALORNOISE_HOME` or `~/.realornoise`, unless
`--ignore-kept`, `--project` or `--example` applies. `--keep-dir DIR` selects another
directory and implies `--keep`. Writes are limited to files named by `--json`, `--markdown`
and `--html`, and with `--keep` the table directory, its missing parents and `days-1.json`.
Temporary files beside the targets support rollback. New table directories use 0700;
the table uses 0600. Existing directories keep their permissions.

The command opens no socket and starts no process. These checks hold that boundary:
`tests/unit/logs/privacy/test_audit_hook.py::test_full_run_has_no_network_process_or_unrequested_write`
observes a synthetic run with and without keeping days;
`tests/unit/logs/privacy/test_imports.py::test_import_allow_list` checks imports.
These are checks of this code and these runs, not protection from modified dependencies.

## Untrusted input

Log content is data, never instructions. Only numbers, dates and three bounded kinds of
name reach output from logs: model ids, effort names and client versions. Model ids use a
closed grammar; efforts use a fixed list; versions use two to four dot-separated numbers,
each at most five digits. Rejected model and effort names become opaque aliases; rejected
versions are never printed. Accepted names are disclosed in full and may still be private.
Prompts, answers, paths, raw log lines and exception text do not reach reports. Terminal
control characters are rendered as visible escapes; Markdown and HTML escape special characters.

`tests/unit/logs/privacy/test_canary.py::test_canaries` checks canary strings across reports,
errors and kept tables. `tests/unit/logs/privacy/test_json_leaves.py::test_every_json_string_leaf`
checks the JSON string categories. `tests/unit/logs/test_html.py::test_names_cannot_inject_markup_or_controls`
checks markup and control characters.

## Package and assistant boundary

The main package declares two runtime dependencies, pydantic and PyYAML, plus their
transitive dependencies. The realornoise distribution pins that main package. Compressed
logs use Python 3.14's standard library. The release workflow uses PyPI trusted publishing
with attestations. To check a release, download each distribution's wheel and sdist, obtain
its `SHA256SUMS` from the matching release workflow artifact, and run
`shasum -a 256 -c SHA256SUMS` in each download directory. Check the version and attestations
on PyPI too. See [Releasing](RELEASING.md#4-verify). Hashes check bytes, not behavior.

The Claude Code plugin and Codex skill run one pinned command:
`uvx --python 3.14 realornoise==2.4.0`. They do not pass `--keep`. The printed numbers and
bounded names enter the assistant's conversation and go wherever that conversation goes.
The command itself sends nothing.

## Limits and reports

This does not protect against another user on the machine, an edited kept table, changed
log files, compromised packages or a vendor changing its log format. Table validation
checks structure and totals, not authenticity. A decision seal checks consistency, not
who ran it. Statistical assumptions are separate from these file boundaries.

When reporting a problem, attach the tool's own output and a synthetic reproducer, never
a log line. Review even accepted names and dates before sharing. Use the
[security policy](../SECURITY.md) for suspected vulnerabilities.
