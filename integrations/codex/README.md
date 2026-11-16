# realornoise as a Codex skill

Copy the folder `skills/realornoise` into `~/.agents/skills/` (Codex reads user skills from
there), then ask Codex to run the `realornoise` skill. The skill tells Codex to run only `uvx --python 3.14 realornoise==2.4.0`
and to show what it prints. What it prints (counts, rates, dates and the bounded model, effort and client-version names)
then becomes part of the conversation.

For a terminal run, use `uvx --python 3.14 realornoise`; uv fetches Python 3.14 to
read compressed Codex logs. The skill does not keep days. To keep daily counts, dates
and accepted setting names, run `uvx --python 3.14 realornoise --keep` yourself.
