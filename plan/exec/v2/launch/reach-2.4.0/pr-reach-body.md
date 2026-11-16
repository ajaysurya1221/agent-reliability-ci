## What

- `plugins/realornoise/README.md`: what the plugin reads, runs, fetches, writes, prints and sends; three uses; what each result means and what it cannot show; what to do when something goes wrong.
- `plugins/realornoise/icon.png`, named in the manifest: the README banner reduced to a square (earlier days in one band, recent days below). Drawn by `docs/assets/src/make_plugin_icon.py` with the standard library.
- `docs/PRIVACY.md`: what the command reads, prints, writes and sends, what the plugin and the skill add, what a download involves, how long things are kept and what the maintainer can see.
- The plugin manifest names the privacy page, the guide and the issue tracker, and sets a display name and keywords.
- Both skills give the `--keep` command with the pinned version, so every launcher command they show is pinned.

## Why

A plugin directory reads the README inside the plugin folder and blocks a submission without one (at least 40 words). It asks that the README describe everything the plugin runs, sends or fetches and that every launcher package be pinned. Its form reads the listing links and the icon from the manifest, and asks the submitter to confirm a privacy policy. Without `documentationUrl` it took the first documentation-like link in the README, which is uv's.

## Checked

- `claude plugin validate --strict plugins/realornoise` (Claude Code 2.1.322): passes with nothing to report (before: one warning, no icon).
- The directory's own validation was run on this branch before the second commit: 7 checks passed.
- Three reviewers read the privacy page against the code, the other documents and the official plugin documentation. Their corrections are applied: the page says the output also carries the UTC offset, the program version and a digest; that the kept table holds UTC offsets and no client versions; that through the plugin any message from `uvx` enters the conversation too; and it makes no promise about what PyPI, GitHub or an assistant's provider do.
- New tests: the README exists, has 40 words or more of prose and the six disclosure lines; every `uvx ... realornoise` in the plugin README and both skills is pinned to the package version; the manifest's links point at files that exist; the icon is the file the manifest names, a square PNG whose pixels equal the generator's, and `.claude-plugin` holds only the manifest.
- Plugin, packaging, docs and logs suites: 1,548 passed, 4 skipped. Lint and type check clean. All 76 pinned hashes match.

No behaviour changes. No release is needed: the plugin is installed from the repository.
