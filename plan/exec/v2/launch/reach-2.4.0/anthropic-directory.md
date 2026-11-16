# Anthropic plugin directory: submission for realornoise

Pages read on 2026-11-16 and re-opened by a second agent:

- S1 https://claude.com/docs/plugins/submit.md
- S2 https://claude.com/docs/plugins/pre-submission-checklist
- S3 https://claude.com/docs/directory/publish.md
- S4 https://code.claude.com/docs/en/plugins/publish.md
- S5 https://support.claude.com/en/articles/13145358-anthropic-software-directory-policy
- S6 https://github.com/anthropics/claude-plugins-official ("Pull requests to this repository are not monitored.")

## Before you start

| Requirement | Source | State |
|---|---|---|
| A paid claude.ai plan ("Free accounts can't submit") | S3 | yours to check |
| GitHub connected on claude.ai, with push access to the repository | S1 | yours to check |
| A README of at least 40 words inside the plugin folder | S2 | met once `v2/reach` is merged |
| Everything the plugin runs, sends or fetches is described in that README | S2 | met once `v2/reach` is merged |
| A licence (file or `license` in `plugin.json`) | S2 | met (`Apache-2.0`) |
| Every launcher package pinned to an exact version | S2 | met once `v2/reach` is merged (the `--keep` line in the skill was unpinned) |
| An icon (taken only at the first save or submission) | the CLI's directory check | met once `v2/reach` is merged |
| `claude plugin validate --strict plugins/realornoise` | CLI 2.1.322 | passes, nothing to report |

A pinned `uvx` package is always held for a person to review (S2). That is a hold, not a
refusal. The documentation gives no review time.

## Steps (portal: claude.ai/directory/manage)

1. What would you like to submit: **Plugin bundle**.
2. Source: repository `ajaysurya1221/agent-reliability-ci`, plugin path
   `plugins/realornoise`, branch `main`. Do not use the tag `v2.4.0`: it has no plugin
   README.
3. Select **Validate**. Fix anything marked Blocking, push, select Re-validate. Only the
   portal can say whether the name `realornoise` is free.
4. Listing details are read from `plugin.json` and the plugin README, not typed. Check the
   surfaces the portal derives: the plugin is meant for Claude Code only.
5. Data handling: answers below. They are your attestations; read each before you give it.
6. Compliance: a contact email you read, and four acknowledgements whose text the public
   pages do not show. Read each one.
7. Review and submit: leave "auto-publish passing versions" off for a first listing.

## Data handling (four questions named in S1; the answer choices are not public)

1. **Reads or stores personal data.** It reads local Claude Code and Codex session log
   files, which hold the user's conversations. It prints only counts, rates, dates and
   model, effort and client-version names that pass fixed accepted lists. Through the
   plugin realornoise writes no file (the plugin does not pass `--keep`). `uv` keeps the
   downloaded package, and a Python 3.14 build if it fetched one, in its own cache.
2. **Sends data to other services.** realornoise opens no network connection. To run it,
   `uvx` downloads the pinned package and the packages it depends on from the package index
   `uv` is set to use (PyPI by default), and a Python 3.14 build from the
   python-build-standalone project if none is installed. The printed output enters the
   Claude conversation, as the README says.
3. **How long data is kept.** realornoise keeps nothing. `uv`'s cache stays until the user
   clears it. The output stays in the conversation like any other message.
4. **Intended for people under 18.** No.

## What a reviewer may ask, and the honest answer

| Policy | Risk | Answer |
|---|---|---|
| 1G | The plugin reads Claude Code session logs, which are chat history. A refusal on this is possible. | Only counts leave the reader; the README and `docs/THREAT_MODEL_LOGS.md` say exactly what is printed. If refused, the "Appeal this decision" route exists; otherwise accept it. |
| 3D (sample data) | A reviewer's machine with no logs gets `ERROR` from the plugin. | `uvx --python 3.14 realornoise==2.4.0 --example` in a terminal shows a full run on packaged example data. The plugin command itself takes no option. |
| 3E (three examples) | | The "How to use it" list in the plugin README. |
| 3A (privacy policy) | There is no privacy policy page. | `docs/THREAT_MODEL_LOGS.md` is the nearest document. Add a page only if asked. |
| 2B (descriptions) | "Did your coding agent get worse?" in `plugin.json` could be read as a claim about answer quality. | Optional, your call: change the description to "Compares recent days with earlier days in your local Claude Code and Codex session logs and answers REAL DROP, NO DROP or CANNOT TELL. Shows the output unchanged." That is a change to a shipped file, so it goes through a pull request. |

## Not verified

The portal's own Validate result; the text of the acknowledgements and the answer choices;
whether the form has a category, support or privacy-policy field; how the portal reads the
interpreter request `--python 3.14`; the archive size GitHub builds (the limit is 50 MiB;
GitHub reports about 11 MB).

## What the form asked when read signed in (2026-11-16)

Read in the maintainer's signed-in browser, first against branch `v2/reach` as an unsent
draft, then against `main`.

- **Step 1, Source.** Its list of checks: a README that explains what the plugin does and
  any data it sends; a licence; "An icon in plugin.json"; a privacy policy URL if it talks
  to a remote server; pinned `npx` and `uvx` launchers. A folder link with a branch name
  that contains a slash is split wrongly (`v2/reach` became branch `v2`); the path and
  branch fields had to be typed.
- **Validation on `v2/reach` at `cb9fbc4`:** passed, 7 checks, name and publisher checks
  passed. Notes only: the inline shell line, and that inline shell and `allowed-tools`
  beyond Read, Grep, Glob and LS will later be accepted only from Verified organizations.
- **Step 2, Listing details**, read from the manifest and the README: the display name was
  shown as "Realornoise"; keywords were not set; the privacy policy was not set; and
  "Documentation" was taken from the README as `docs.astral.sh/uv/`, which is uv's page.
  Listed surfaces were ticked for Claude Code, Cowork and the Claude apps, with the note
  that inline shell does not run on the last two.
- **Step 3, Data handling:** four questions with fixed answers. Read or store personal
  data (No, Reads only, Reads and stores); send data to a service other than the declared
  connectors (No, Yes listed in README); how long the service retains data from Claude
  (Not retained, Under 30 days, Longer); intended for under 18 (No, Yes). Choosing "Reads
  only" brought a warning that no privacy policy URL was found.
- **Step 4, Compliance:** a contact email (filled in by the site from the account) and four
  boxes: agreement to the Software Directory Terms and the Directory Policy; "The plugin's
  privacy policy accurately describes the data it handles."; "The plugin does not
  exfiltrate credentials or execute code outside its declared MCP servers."; and that
  Anthropic may contact that address.

What changed in the repository because of it (commit `d8a8a57`, in pull request 28):
`docs/PRIVACY.md`; `displayName`, `keywords`, `documentationUrl`, `supportUrl`,
`privacyPolicyUrl` and `icon` in the manifest; the icon moved from `.claude-plugin/` to the
plugin folder (the plugin reference says to name it in `icon` and to keep only the
manifest in `.claude-plugin`). Three reviewers checked the privacy page against the code,
the other documents and the official plugin documentation before the commit; ten
corrections to the page and two to the plugin README were applied. The plugin installs
with the new fields in an empty configuration folder (Claude Code 2.1.322).

## Submitted (2026-11-16)

- Source: `ajaysurya1221/agent-reliability-ci`, path `plugins/realornoise`, the default
  branch; validated at `main` @ `c4fcb66`: passed, 7 checks, 4 warnings (three listing
  fields that released Claude Code builds do not read, and `icon`, which only the
  directory reads; the form says no action is needed).
- Listing as read: name `realornoise`; links to the privacy page, the issue tracker, the
  repository and the guide; no terms of service link.
- Listed on: Claude Code only. Cowork and the Claude apps were unticked, because the
  plugin's one shell line does not run there.
- Data handling answers: Reads only; Yes, listed in README; Not retained; No.
- Compliance: the four boxes were ticked in the maintainer's browser while the
  orchestrator was working elsewhere; the orchestrator did not tick them.
- Auto-publish of later versions: turned off. The status page says no version goes live
  without an Anthropic reviewer for now.
- Submitted by the orchestrator at the maintainer's instruction ("use my chrome and do it
  yourself"; "take full control"). Status page:
  https://claude.ai/directory/manage/plugins/64c64d0b-5eca-4054-bc02-ee514f0fd7ea
  (version v2.4.0 at `c4fcb66`, "Scanning" at the time of writing).

Open point for the maintainer: the third box says the plugin does not "execute code
outside its declared MCP servers". The plugin declares no MCP server and runs one pinned
shell command, which the form's own scan lists as an accepted note and the README states.
If a reviewer reads that box literally, expect a question.

Not verified: the result of the security scan and of the review; how long either takes.
