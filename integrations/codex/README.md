# realornoise as a Codex skill

Copy the folder `skills/realornoise` into `~/.agents/skills/` (Codex reads user skills from
there), then ask Codex to run the `realornoise` skill. The skill tells Codex to run `uvx --python 3.14 realornoise==2.5.0` once, with no other arguments,
and to show what it prints. Everything the command prints (counts, rates, dates, the bounded model, effort and client-version names,
and any message from uvx itself) then becomes part of the conversation.

For a terminal run, use `uvx --python 3.14 realornoise`; uv fetches Python 3.14 to
read compressed Codex logs. The skill tells Codex not to add `--keep`. To keep daily counts, dates
and accepted setting names, run `uvx --python 3.14 realornoise --keep` yourself.
