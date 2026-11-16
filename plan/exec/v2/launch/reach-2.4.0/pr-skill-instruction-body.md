## What

The Claude Code plugin's skill becomes an instruction to Claude: run `uvx --python 3.14 realornoise==2.4.0` once, with nothing added, and show everything it printed, unchanged. Before, the skill ran that line itself when the command was typed and approved it ahead of time (`allowed-tools`).

- `plugins/realornoise/skills/realornoise/SKILL.md`: no shell line of its own and no `allowed-tools`. `disable-model-invocation: true` stays, so in Claude Code Claude does not start it on its own. It says what to do with text typed after the command name (run nothing and say so), with a refusal (stop), and with exit status 1 or 2 (that is the result). The reply is one code block.
- The plugin README, the privacy page, the threat model, the recipe, the release guide and the Codex README say what follows from this.
- The plugin and marketplace descriptions say "Tells Claude to run" instead of "Runs".

## Why

Anthropic's plugin directory refused the first submission automatically (the scan passed; the policy check did not). Its report: a skill with its own shell line, or with `allowed-tools` beyond Read, Grep, Glob and LS, is accepted only from a verified organization, and the step should be rewritten as an instruction to Claude.

## What changes for a user

- Nothing is approved ahead of time. Whether Claude Code asks before the command runs depends on the permission mode and settings: in a mode that asks, the prompt shows the command; in auto mode, with an allow rule or with a hook, it can run without a prompt and the transcript shows it; a mode, a classifier or a deny rule can also refuse it.
- An instruction is not a lock. The documents say so.
- Claude's shell tool reports exit status 1 (REAL DROP) or 2 (CANNOT TELL) as a failed command. The skill and the README say that this is the result.
- A copy of plugin version 2.4.0 installed earlier keeps the earlier skill until the plugin's version changes and the user updates the plugin, because the manifest version stays 2.4.0.
- Options typed after the command name are refused: `/realornoise:realornoise --example` runs nothing. Options work in a terminal.

## Checked

- Two rounds of independent review. A second round of two checkers read the corrected text; it found no high finding, and its two medium and seven low points are applied (typed options now run nothing; no date in the sentence about earlier copies; a refusal by a mode or a classifier is stated).
- First round: three reviewers read the first version of this change (stale sentences across the repository, the official skill and permission documentation, and the skill text as an instruction with 41 changed copies tried against the test). Their findings are applied: the permission wording no longer says that Claude Code always asks; typed arguments are handled; the test now holds the frontmatter keys, the single command line, every option named in the text and the guard sentences.
- The pinned design records 0016 (decision 9) and 0017 (decision 7, item 73) still hold: both skills name the pinned command, and no pinned file is touched. All 76 pinned hashes match.
- Plugin, packaging, docs and logs suites: 1,548 passed, 4 skipped. Lint and type check clean. `claude plugin validate --strict` passes for the plugin and the marketplace; that command does not run the directory's policy check.

## Not checked

- A real run of the new skill inside Claude Code: no session was started, so how Claude follows the text was not observed.
- Whether the directory accepts this version. Only its own report can say.

The package is unchanged. No release is needed.
