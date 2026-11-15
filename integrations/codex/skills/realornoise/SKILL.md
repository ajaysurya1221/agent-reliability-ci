---
name: realornoise
description: Run realornoise on the Claude Code and Codex session logs on this machine and show its result (real drop, no drop or cannot tell) unchanged. Use only when the user asks for it by name.
---

Run this command in the shell, once, with no other arguments:

    uvx realornoise

It reads local session logs and prints counts, rates, dates and the names of the model and
effort compared. The command itself sends nothing anywhere. Its output becomes part of
this conversation, so what it prints is visible to this assistant and goes wherever this
conversation goes.

Show the output to the user exactly as printed, in one code block, and add nothing to it. Do
not summarise it, soften it or draw a conclusion from it: the output already says what it
shows and what it cannot show. An exit status of 0, 1 or 2 is a normal result.

If `uvx` is not found, tell the user to install `uv` (https://docs.astral.sh/uv/) or to run
`pip install agent-reliability-ci` and then `arci logs`, and stop.
