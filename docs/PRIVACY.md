# Privacy: realornoise, its Claude Code plugin and its Codex skill

realornoise is a program that runs on your own computer. The project runs no server for
it. The tool needs no account and has no telemetry or analytics. The realornoise command
itself sends nothing to the maintainer or to anyone else. Run through the plugin or the
skill, what it prints enters your conversation with the assistant; see "Through the plugin
or the skill" below.

This page covers the `realornoise` command (the same as `arci logs`), the Claude Code
plugin in `plugins/realornoise` and the Codex skill in `integrations/codex`. It does not
cover the other `arci` commands. Some of them run the agents and tools you configure,
start processes or contact an address you give.

## What the command reads

- Claude Code session logs: `.jsonl` files below `~/.claude/projects`, or
  `$CLAUDE_CONFIG_DIR/projects`.
- Codex session logs: `rollout-*.jsonl` and `.jsonl.zst` files below `~/.codex/sessions`
  and `~/.codex/archived_sessions`, or the same folders under `$CODEX_HOME`.
- Its own table of daily counts, `days-1.json`, if an earlier run with `--keep` wrote one.

These logs hold your conversations. The command reads them on your computer and turns them
into daily counts. `--claude-dir`, `--codex-dir` and `--keep-dir` point it at folders you
name instead. A symbolic link to a file inside those folders is followed. With `--example`
it reads only packaged example data.

## What it prints

- Counts, rates and dates.
- The UTC offset your computer uses for calendar days (`--utc` prints UTC+00:00 instead).
- The program version and a short digest of the daily counts.
- Model, effort and client-version names that pass fixed rules. Model and effort names
  that do not pass become opaque labels. Client versions that do not pass are left out.

Prompts, answers, file paths and raw log lines are not printed. A name that passes is shown
in full and can still be private. Review names and dates before you share a result.

## What it writes

Nothing, unless you ask.

- `--json`, `--markdown` and `--html` write the report files you name.
- `--keep` writes `days-1.json` in `~/.realornoise`, or in `$REALORNOISE_HOME`, or in the
  folder given with `--keep-dir` (which implies `--keep`). Missing folders are created.
  The file holds daily counts, dates, UTC offsets, the tool each row is for, and accepted
  model and effort names. It holds no prompts, answers, paths or client versions.
- While writing, the command uses temporary files beside the targets. With `--keep` it
  also removes leftover files named `.realornoise-*` from the table folder. An interrupted
  run can leave a `.realornoise.out-*` file beside a report.

The plugin and the skill tell the assistant to run the command without any of these
options.

## What it sends

Nothing itself. The command opens no network connection and starts no process. Tests check
this on the project's own code. They are not protection from a modified or compromised
package, or from another user on your computer.

## Through the plugin or the skill

The Claude Code plugin and the Codex skill each tell the assistant to run one pinned
command, once, with nothing added. In Claude Code the plugin's command starts only when you
type it. Whether Claude Code asks you before the shell command runs depends on your
permission mode and settings. In a mode that asks, the prompt shows the command. In one
that does not ask (auto mode, an allow rule, a hook), it runs without a prompt and the
transcript shows what ran. These are instructions to an assistant, not locks. A copy of
the plugin installed before 16 November 2026 keeps the earlier skill until the plugin's
version changes: that skill ran the command itself when you typed it, with the command
approved ahead of time. Everything that command prints enters your conversation with the
assistant. That includes any message from `uvx` itself, such as a
download line or an error, which can show a path on your computer. The assistant is told
to show the output unchanged. From there it goes wherever that conversation goes, like
anything else in it. The project does not control that; the terms of your assistant's
provider apply.

Two things follow:

- The command reads both tools' logs when both exist. The output put into one assistant's
  conversation can include figures and model names from the other tool.
- There is no review step for the output. To see it before an assistant does, run the command in
  a terminal.

## Downloads

Installing or running the tool downloads software.

- `uvx` and `pip` fetch the package and the packages it depends on from the package index
  they are set to use (PyPI by default).
- If Python 3.14 is not installed, `uv` also fetches a Python build from the
  python-build-standalone project (https://docs.astral.sh/uv/concepts/python-versions/).
- Installing the plugin, or copying the skill, fetches files from this repository on
  GitHub.

Those services receive the request, with your network address and whatever the installer
sends about itself, under their own policies. realornoise has not run at that point and
adds nothing to the request.

## How long things are kept

The project keeps nothing, because it receives nothing. On your computer, report files and
`days-1.json` stay until you delete them, and `uv` keeps what it downloaded in its own
cache until you clear it. What entered an assistant's conversation is kept as that
conversation is.

## What the maintainer can see

The tool gives the maintainer nothing. The maintainer can see what PyPI and GitHub publish
or show to a project's owner, for example download statistics and repository traffic.
Those services decide what that includes. If you open an issue or a discussion, what you
write there is public.

## Reporting a problem

Attach the tool's own output and a synthetic reproducer, never a log line. For a suspected
leak or vulnerability use the [security policy](../SECURITY.md), not a public issue.

## More detail and changes

The boundaries above, their limits and the tests that check them are in the
[threat model](THREAT_MODEL_LOGS.md). Changes to this page are in the repository history.
Questions: https://github.com/ajaysurya1221/agent-reliability-ci/issues
