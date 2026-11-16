# Reach for 2.4.0: what is ready, in the order to do it

Prepared on 2026-11-16 by agents. Each venue's rules were read that day and re-opened by a
second agent. Later the same day the maintainer told the orchestrator to carry out the
steps itself in their signed-in browser ("use my chrome and do it yourself", then "take
full control"). Steps 1, 2, 3 and 5 were done that way; the table says what happened.
Step 4 stays with the maintainer, because that list requires a person to write and send
the recommendation. Step 6 stays with the maintainer, because it publishes their own
usage numbers.

| # | Step | Needs | File | State |
|---|---|---|---|---|
| 1 | Repository description, topics, Discussions | 30 seconds | `../repo-settings-2.4.0.md` | **done** 2026-11-16 (description set, four topics added, Discussions on; read back) |
| 2 | Merge the plugin README and icon | a pull request from `v2/reach` | `pr-reach.md` | **done** 2026-11-16: pull request 28 merged as `c4fcb66` (the icon approved by the maintainer; a privacy page and listing links added after the directory's form was read) |
| 3 | awesome-observability listing | click "Create pull request" | `awesome-observability.md` | **opened** 2026-11-16: pull request 223 at the list |
| 4 | awesome-claude-code form | the maintainer writes the description themself | `awesome-claude-code.md` | facts ready |
| 5 | Anthropic plugin directory | step 2 merged; a paid claude.ai plan | `anthropic-directory.md` | **submitted** 2026-11-16 (`main` at `c4fcb66`, listed for Claude Code only); waiting for the scan and a reviewer |
| 6 | Blog post about the maintainer's own run | the maintainer's yes to post their numbers | private draft, not in this branch | draft ready |
| 7 | OpenAI directory for the Codex skill | a manifest, an icon, a privacy page, a verified organization | `openai-codex.md` | not now |
| 8 | Two more lists | their rules are unclear today | `later-lists.md` | not now |

## What is already out

- `tensorchord/Awesome-LLMOps` pull request 1191: **merged** (seen 2026-11-16).
- `kelvins/awesome-mlops` 319: open, no comment.
- `Vvkmnn/awesome-ai-eval` 62 and the Inspect AI extensions listing: opened on 15 Nov; not
  re-checked today.

## Rules that hold for every text here

Plain words. No claim to be the only or first tool of its kind (is-it-nerfed and livenerf
exist). No claim of cause, of a changed model, or of answer quality. `CANNOT TELL` is a
normal result and is said so. "Sends nothing" is true of the command; through the plugin or
the skill the printed output enters the assistant's conversation, and `uvx` downloads the
package, so texts about the plugin or the skill say that.

## Not verified

- What each portal shows after sign-in (the Anthropic and OpenAI forms are not public).
- Whether a reviewer at Anthropic counts session logs as chat history under policy 1G.
- How the plugin behaves outside Claude Code (claude.ai chat, Cowork).
- The lists' lint jobs (awesome-observability's needs Docker; its CI runs it on the pull
  request).
