# realornoise threat model

`realornoise` and `arci logs` read local files. They do not run a model or a trial.
This page covers the installed tool: it opens no connection and sends nothing.
Installing it downloads the package. uvx also downloads Python 3.14 if it is missing.

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

The Claude Code plugin and Codex skill each tell the assistant to run one pinned command,
once and with nothing added: `uvx --python 3.14 realornoise==2.4.1`. They tell it not to
add `--keep`. In Claude Code, Claude does not start the plugin's skill on its own: it
starts when the user types its command, or names it in a message and Claude judges that
they asked for it. The skill approves no tool ahead of time and has no shell line of its
own. Whether Claude Code asks
before the command runs depends on the user's permission mode and settings. An instruction
is not a control: the prompt, when there is one, and the transcript show the command. A
copy of plugin version 2.4.0 installed before the skill became an instruction keeps the
earlier skill, which ran the command itself with the command approved ahead of time,
until the plugin is updated. Plugin version 2.4.1 holds the instruction. Everything the
command prints, including any message from uvx, which can show a path, enters the
assistant's conversation and goes wherever that conversation goes.
realornoise itself opens no connection and sends nothing. uvx downloads the package,
and Python 3.14 if it is missing, to run it.

## Limits and reports

This does not protect against another user on the machine, an edited kept table, changed
log files, compromised packages or a vendor changing its log format. Table validation
checks structure and totals, not authenticity. A decision seal checks consistency, not
who ran it. Statistical assumptions are separate from these file boundaries.

When reporting a problem, attach the tool's own output and a synthetic reproducer, never
a log line. Review even accepted names and dates before sharing. Use the
[security policy](../SECURITY.md) for suspected vulnerabilities.
