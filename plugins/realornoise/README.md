# realornoise

realornoise reads the Claude Code and Codex session logs already on your computer. For each
tool it compares recent days with earlier days, for the model and effort you used most in
the recent days, and answers REAL DROP, NO DROP or CANNOT TELL. It runs no model.

This plugin adds one command to Claude Code. The command tells Claude to run
`uvx --python 3.14 realornoise==2.4.1` once, with nothing added, and to show what it
prints, unchanged. Whether Claude Code asks you before that command runs depends on your
permission mode and settings.

## Where it works

It works in Claude Code on the computer that holds your session logs, and it needs `uv`
(https://docs.astral.sh/uv/) and a shell. It has not been tested anywhere else. Where there
are no local session logs, the command has nothing to read.

## Install

In Claude Code:

```text
/plugin marketplace add ajaysurya1221/agent-reliability-ci
/plugin install realornoise@agent-reliability-ci
```

## How to use it

Type the command yourself. In Claude Code, Claude does not start it on its own. If Claude
Code asks before running the shell command, check that it is the one above, then approve
it. The command takes no options: if you type anything after its name, Claude is told to
run nothing and to say so. For options such as `--example`, use a terminal.

```text
/realornoise:realornoise
```

Three uses:

1. You think your coding agent has behaved differently in the last two weeks. Run the
   command. By default it compares up to 14 recent days with up to 84 earlier calendar days.
2. You have used Claude Code for only a few days. Run the command. The usual answer is
   CANNOT TELL, which is a normal result. When there are too few days, the output names the
   earliest date a test could run, as a best case if you use the same setting every day.
   That date is not a promise of a decisive result.
3. You want to see the output before reading your own logs. In a terminal, run
   `uvx --python 3.14 realornoise==2.4.1 --example`. It reads only packaged example data,
   generated, not anyone's logs. That run exits 1, because the example has one REAL DROP.

## What the result means

Each tool gets its own result:

- REAL DROP: at least one recorded measure moved toward worse by more than a chance ordering
  of your days explains.
- NO DROP: no recorded measure moved toward worse by its margin or more. It does not say
  that anything improved.
- CANNOT TELL: the days you have do not separate a shift from noise. With a short history
  this is the usual answer.
- ERROR: no logs or no readable responses for that tool.

The output ends with one exit line for the whole run: 1 if any tool is REAL DROP, otherwise
2 if any is CANNOT TELL, otherwise 0. It is 3 only if every tool is ERROR.

The measures are reasoning tokens per response, the share of responses with no reasoning,
and failed file edits (Claude Code) or reasoning at one repeated value (Codex).

## What it cannot show

It shows what your logs recorded, not why. It cannot show a cause, answer quality, or a
change to the model. Your tasks, prompts, projects or client version may have changed. The
error bounds hold only under assumptions the tool states and does not check. When days
resemble their neighbours or work comes in phases, its self-check measured a wrong REAL DROP
up to 18.1% of the time in the cases it tested. Other patterns can give more.
Details: https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/STATISTICS_LOGS.md

## What it reads, runs, fetches, writes and sends

- Reads: Claude Code `.jsonl` files below `~/.claude/projects` (or
  `$CLAUDE_CONFIG_DIR/projects`), and Codex `rollout-*.jsonl` and `.jsonl.zst` files below
  `~/.codex/sessions` and `~/.codex/archived_sessions` (or the same folders under
  `$CODEX_HOME`). These logs hold your conversations. The tool turns them into daily counts.
- Runs: `uvx --python 3.14 realornoise==2.4.1`, which Claude runs in the shell. This is an
  instruction to Claude, not a lock. In a permission mode that asks, the prompt shows the
  command before it runs. In one that does not ask (auto mode, an allow rule, a hook), the
  transcript shows the command that ran. The package itself opens no network connection
  and starts no process.
- Fetches: `uvx` downloads the pinned package and the packages it depends on from the
  package index `uv` is set to use (PyPI by default). If Python 3.14 is not installed, `uv` also
  downloads a Python build from the python-build-standalone project
  (https://docs.astral.sh/uv/concepts/python-versions/).
- Writes: Claude is told to run the command with no options. Without an option
  realornoise writes no file. `uv` keeps what it downloaded in its own cache until you
  clear it.
- Prints: counts, rates, dates, the UTC offset your computer uses for calendar days, the
  program version, a short digest of the daily counts, and model, effort and client-version
  names that pass fixed rules. Other model and effort names become opaque labels. Prompts,
  answers, file paths and raw log lines are not printed by realornoise. Through the plugin,
  any message from `uvx` itself, such as a download line or an error, is shown too, and
  such a message can show a path on your computer.
- Sends: the plugin puts the printed output into this conversation. From there it goes
  wherever this conversation goes, like anything else you type. realornoise sends nothing
  itself.

Privacy: https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/PRIVACY.md

Threat model: https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/THREAT_MODEL_LOGS.md

## If something goes wrong

- `uvx` not found: install uv from https://docs.astral.sh/uv/, or run
  `pip install agent-reliability-ci` and then `arci logs` in a terminal.
- Claude Code marks the command as failed: the command exits with status 1 when a result
  is REAL DROP and 2 when a result is CANNOT TELL. That is the result, not a failure.
- Claude says that nothing ran: your permission mode, a deny rule or auto mode's
  classifier refused the command.
- The command runs by itself, with nothing shown first: a copy of plugin version 2.4.0
  installed before the skill became an instruction to Claude keeps the earlier skill
  until the plugin is updated. Plugin version 2.4.1 holds the instruction. The earlier skill ran
  the command itself when you typed it, with the command approved ahead of time.
- ERROR for a tool: the tool found no logs, no readable file or no usable response for it on
  this computer. Results for the other tool can still appear.
- To keep daily counts beyond the 30 days Claude Code keeps session files by default, run
  `uvx --python 3.14 realornoise==2.4.1 --keep` yourself in a terminal. It writes
  `~/.realornoise/days-1.json`, which holds daily counts, dates, UTC offsets and accepted
  model and effort names. It holds no prompts, answers, paths or client versions.

Guide: https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/recipes/logs.md

## Support and license

Questions and bugs: https://github.com/ajaysurya1221/agent-reliability-ci/issues
Security reports: https://github.com/ajaysurya1221/agent-reliability-ci/security/advisories/new
This is a single-maintainer project, and no response time is promised.

License: Apache-2.0.
