---
name: realornoise
description: Run realornoise on the Claude Code and Codex session logs on this machine and show its result (real drop, no drop or cannot tell) unchanged. Runs only when the user types the command.
disable-model-invocation: true
allowed-tools: Bash(uvx --python 3.14 realornoise==2.4.0)
---

The command below has already run on this machine. It read local session logs and printed
counts, rates, dates and the bounded model, effort and client-version names. realornoise itself opens no connection and sends nothing.
uvx downloads the package, and Python 3.14 if missing, to run it. Its output is now part of this conversation, so what it printed is
visible to this assistant and goes wherever this conversation goes.

!`uvx --python 3.14 realornoise==2.4.0 2>&1 || true`

Show the output above to the user exactly as printed, in one code block, and add nothing to
it. Do not summarise it, soften it or draw a conclusion from it: the output already says what
it shows and what it cannot show. An exit line of 0, 1 or 2 is a normal result.

If the output says that `uvx` was not found, tell the user to install `uv`
(https://docs.astral.sh/uv/) or to run `pip install agent-reliability-ci` and then
`arci logs`, and stop.

The skill does not pass `--keep`. The user can run `uvx --python 3.14 realornoise --keep`
themselves to save daily counts, dates and accepted model and effort names in
`~/.realornoise/days-1.json` (or `$REALORNOISE_HOME/days-1.json`).
