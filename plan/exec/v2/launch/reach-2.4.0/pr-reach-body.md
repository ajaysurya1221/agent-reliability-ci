## What

- `plugins/realornoise/README.md`: what the plugin reads, runs, fetches, writes, prints and sends; three uses; what each result means and what it cannot show; what to do when something goes wrong.
- `plugins/realornoise/.claude-plugin/icon.png`: the README banner reduced to a square (earlier days in one band, recent days below). Drawn by `docs/assets/src/make_plugin_icon.py` with the standard library.
- Both skills give the `--keep` command with the pinned version, so every launcher command they show is pinned.

## Why

A plugin directory reads the README inside the plugin folder and blocks a submission without one (at least 40 words). It asks that the README describe everything the plugin runs, sends or fetches, that every launcher package be pinned, and it takes the icon at the first submission only.

## Checked

- `claude plugin validate --strict plugins/realornoise`: passes with nothing to report (before: one warning, no icon).
- New tests: the README exists, has 40 words or more of prose and the six disclosure lines; every `uvx ... realornoise` in the plugin README and both skills is pinned to the package version (an unpinned one fails a test); the icon is a square PNG of 512 to 2048 pixels under 2 MB whose pixels equal the generator's.
- Plugin, packaging, docs and logs suites: 1,547 passed, 4 skipped. Lint and type check clean. All 76 pinned hashes match.

No behaviour changes. No release is needed: the plugin is installed from the repository.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
