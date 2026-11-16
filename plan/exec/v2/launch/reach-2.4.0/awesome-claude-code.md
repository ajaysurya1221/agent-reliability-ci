# awesome-claude-code: the recommendation form (facts only)

Venue: https://github.com/hesreallyhim/awesome-claude-code
Form: https://github.com/hesreallyhim/awesome-claude-code/issues/new?template=recommend-resource.yml
Rules read on 2026-11-16 from the raw `CONTRIBUTING.md` and the form's template, and
re-opened by a second agent.

## The rule that shapes this file

`CONTRIBUTING.md` says "resource recommendations must be created by human beings", that
the `gh` command may not be used, and "Do not open a PR. Just fill out the form." Read
plainly, that covers the description you type. **So this file holds checked facts and no
description. Write the description yourself**, in the web form, signed in.

## Eligible today?

Yes, by age: a resource must be at least 14 days old with active development, or have 100
stars. The first commit on `main` is from 2026-09-21 (56 days), and the last push was
today. Not by stars (0). Submissions that fail a rule are closed automatically.

## The form's fields

| Field | What fits |
|---|---|
| Display Name | `realornoise` |
| Category | `Observability & Monitoring` (entries that read session logs sit there). The form has sub-choices; pick the nearest. |
| Link | `https://github.com/ajaysurya1221/agent-reliability-ci` (the form says to prefer the repository) |
| Author Name | your GitHub name or an alias; your real name only if you want it public |
| Author Link | `https://github.com/ajaysurya1221` |
| Description | yours to write: one line, 1 to 3 sentences, 10 to 500 characters, no sales wording, no emoji, no "you" |
| Checklist | tick only what you did yourself, "with my own eyes"; the list says one box is a trap, so read each |

## Facts you can lean on (each true of 2.4.0, checked against the released files)

- It is a Claude Code plugin and a command-line tool. Since pull request 29 (2026-11-16)
  the plugin's skill tells Claude to run one pinned command,
  `uvx --python 3.14 realornoise==2.4.0`, once, with nothing added, and to show the output
  unchanged. Claude does not start it on its own; the user types
  `/realornoise:realornoise`. It is an instruction to Claude, not a lock, and whether
  Claude Code asks before the command runs depends on the permission mode.
- It reads the Claude Code and Codex session logs already on disk. For each tool it
  compares recent days with earlier days, for the model and effort used most in the
  recent days.
- It answers REAL DROP, NO DROP or CANNOT TELL. With a short history the usual answer is
  CANNOT TELL.
- It runs no model. The command opens no connection. Through the plugin the printed
  numbers enter the conversation, and `uvx` downloads the package.
- It cannot show a cause, answer quality, or a change to a model.
- Licence Apache-2.0. No sign-up, no payment.
- It also has a Codex skill, so the repository is not only about Claude Code. The plugin
  is. The checklist has a required box "This resource is specific to Claude Code";
  `CONTRIBUTING.md` calls that focus "a guideline", not a hard requirement. Decide
  honestly whether you can tick it.

## How nearby entries read (for the style, not to copy)

- seedeep: "Reads the JSONL session logs Claude Code already writes and shows, live during"
- bough: "Reads Claude Code JSONL session transcripts and draws a project's history as a"

## What would get it closed

Using `gh` or a pull request; ticking the trap box; a promotional description; more than
one resource in one form; a reviewer judging it not specific to Claude Code. The list warns
against using it as a promotion channel, and a review is best effort.

## Not verified

The rendered form in a browser (only its template was read); how the list's bot checks the
licence and the age.

## Closed to new submissions for now (seen 2026-11-16)

When the maintainer opened the form, GitHub answered: "An owner of this repository has
limited the ability to create an issue to users that are collaborators on this
repository." Checked the same day through the public API: the list received 24 issues on
11 Nov and 25 on 12 Nov 2026 (the newest eight are from people who are not collaborators;
the rest were not checked one by one), and none since.
So the owner limited issue creation on about 12 or 13 Nov. No notice about it was found in
the contributing file, the pinned issues or the discussions. GitHub's limits of this kind
end by themselves after the period the owner chose (one day to six months); the period is
not public.

What to do: nothing now. The list's rules allow the web form only (no pull request, no
`gh`), so there is no other permitted route, and a discussion post would be the promotion
the list warns against. Look again at each snapshot (19 Nov, 26 Nov, 12 Dec): when new
issues from other people appear after 12 Nov, the form is open again.
