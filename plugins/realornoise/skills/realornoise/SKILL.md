---
name: realornoise
description: Run realornoise on the Claude Code and Codex session logs on this machine and show its result (real drop, no drop or cannot tell) unchanged. Runs only when the user types the command.
disable-model-invocation: true
allowed-tools: Bash(uvx realornoise), Bash(uvx realornoise *)
---

The command below has already run on this machine. It read local session logs and printed
numbers only; it sent nothing anywhere. Its output is now part of this conversation, so the
numbers it printed are visible to this assistant.

!`uvx realornoise 2>&1 || true`

Show the output above to the user exactly as printed, in one code block, and add nothing to
it. Do not summarise it, soften it or draw a conclusion from it: the output already says what
it shows and what it cannot show. An exit line of 0, 1 or 2 is a normal result.

If the output says that `uvx` was not found, tell the user to install `uv`
(https://docs.astral.sh/uv/) or to run `pip install agent-reliability-ci` and then
`arci logs`, and stop.
