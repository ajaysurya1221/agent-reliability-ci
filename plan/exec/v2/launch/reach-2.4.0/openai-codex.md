# OpenAI's directory for the Codex skill: not now

Read on 2026-11-16 (official pages under developers.openai.com/codex, re-opened by a second
agent).

## What the route is

One public route: the plugin directory shared by ChatGPT and Codex, by uploading a ZIP at
platform.openai.com/plugins. Plugins that hold only skills are allowed. The repository
`openai/skills` says it is deprecated and points to plugins.

## What is missing

| Needed | State |
|---|---|
| A plugin manifest (`plugin.json`) with listing fields | not in the repository |
| A square icon, at least 48 pixels | not in the repository |
| A published privacy policy | none (the threat model page is the nearest) |
| A verified OpenAI Platform organization with the right to submit | the maintainer's to check |
| `requires_local_executor` (the skill runs a local program), which makes it desktop only | if the portal refuses the field, the documentation only says to send the organization's ID to an OpenAI representative |
| Unpublished "additional eligibility requirements" for skills-only plugins | unknown until review |

Also open: the guidelines say a connector "must not pull, reconstruct, or infer the full
chat log". That rule is written for connectors, but this skill reads local session
transcripts, so a reviewer may raise it.

## Decision

Not now. Two of the six items can stop a submission from a single maintainer with no
OpenAI contact, and the manifest, icon and privacy page are new shipped files that need
their own review. What works today and is documented in the README: copy
`integrations/codex/skills/realornoise` into `~/.agents/skills/`.

Drafts of a manifest, an icon, a marketplace file and a privacy page exist in the session's
scratch folder. A second agent found seven wording problems in them, so they are not in
this branch. If this route is taken up, start from the rules above, not from those drafts.
