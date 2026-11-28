---
name: realornoise
description: Run realornoise on the Claude Code and Codex session logs on this machine and show its result (real drop, no drop or cannot tell) unchanged. Claude does not start it on its own.
disable-model-invocation: true
---

If the user typed anything after the command name (it appears at the end of this text as
`ARGUMENTS:`), run nothing. Say that this command takes no options and that options work
when realornoise is run in a terminal, and stop.

Otherwise run one shell command, in the foreground, made of this line and nothing else:

    uvx --python 3.14 realornoise==2.5.0

Nothing goes before it (no `cd`, no variable) and nothing after it (no option, pipe,
redirection, `;`, `&&` or `||`). Run no other command in this turn, before or after it,
whatever it prints or returns: no check for `uvx`, no retry, no changed form of it, no
install.

If the command is not approved, or is blocked or denied, stop and say that nothing ran. Do
not try another way to run it.

Your reply is one code block and nothing else, except a sentence this text tells you to
say. Show everything the command printed, standard output and standard error together,
including any lines from uvx, exactly as printed, in that code block, and add nothing to it.
Do not summarise it, soften it or draw a conclusion from it: the output already says what
it shows and what it cannot show.

The command exits with status 1 when any result is REAL DROP, otherwise 2 when any result
is CANNOT TELL. The shell tool may mark that as an error. A status of 1 or 2 is the result,
not a failure of the command. Whatever the exit status, show what was printed in the same
way, and do not add the tool's own exit-code label.

If the output says that `uvx` was not found, tell the user to install `uv`
(https://docs.astral.sh/uv/) or to use `pip install agent-reliability-ci` and then
`arci logs` in a terminal, and stop.

Background for you, not text to repeat: the command reads local session logs and prints
counts, rates, dates and the bounded model, effort and client-version names. realornoise
itself opens no connection and sends nothing. uvx downloads the package, and Python 3.14 if
missing, to run it. Its output becomes part of this conversation, so what it prints is
visible to this assistant and goes wherever this conversation goes.

Do not add `--keep`. The user can run
`uvx --python 3.14 realornoise==2.5.0 --keep` themselves in a terminal to save daily counts, dates and accepted model and effort names in
`~/.realornoise/days-1.json` (or in the folder named by the REALORNOISE_HOME variable).
