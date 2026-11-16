---
name: realornoise
description: Run realornoise on the Claude Code and Codex session logs on this machine and show its result (real drop, no drop or cannot tell) unchanged. Use only when the user asks for it by name.
---

Run this command in the shell, once, with no other arguments:

    uvx --python 3.14 realornoise==2.4.0

It reads local session logs and prints counts, rates, dates and bounded model, effort
and client-version names. realornoise itself opens no connection and sends nothing.
uvx downloads the package, and Python 3.14 if missing, to run it. Its output becomes part of
this conversation, so what it prints is visible to this assistant and goes wherever this
conversation goes.

Show the output to the user exactly as printed, in one code block, and add nothing to it. Do
not summarise it, soften it or draw a conclusion from it: the output already says what it
shows and what it cannot show. An exit status of 0, 1 or 2 is a normal result.

If `uvx` is not found, tell the user to install `uv` (https://docs.astral.sh/uv/) or to run
`pip install agent-reliability-ci` and then `arci logs`, and stop.

The skill does not pass `--keep`. The user can run
`uvx --python 3.14 realornoise==2.4.0 --keep` themselves to save daily counts, dates and accepted model and effort names in
`~/.realornoise/days-1.json` (or `$REALORNOISE_HOME/days-1.json`).
