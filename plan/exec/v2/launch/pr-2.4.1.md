# Pull request for 2.4.1 (the maintainer creates and merges it)

Branch `v2/release-2.4.1` (`17b034c`), cut from `main` at `06a01f5`. Compare link (title
filled in):
https://github.com/ajaysurya1221/agent-reliability-ci/compare/main...v2/release-2.4.1?expand=1&title=v2.4.1%3A%20fixes%20since%202.4.0

Title: v2.4.1: fixes since 2.4.0

Paste everything below the line into the description box, in place of the template.

---

## What changed

Release 2.4.1: the version in every release location, the changelog section, and design
record 0018. No code changes in this pull request beyond the version and one docstring; the
fixes it releases are already on `main` (pull requests 34, 35 and 37, and the README theme
in 36).

What 2.4.1 ships, against 2.4.0:

- **Whole-file `state.json`**: the tool server for Python toolsets writes a temporary file
  and moves it into place. A stop during a write left an empty file and the trial ended
  `ERROR`.
- **A staged stop of the MCP tool server** at the end of a command trial, when waiting can
  change what is graded: close the server's input, SIGTERM at half of the time left,
  SIGKILL at three quarters. An idle server is closed and killed at once, as before.
- **The kept-table read** in `arci logs --keep` reads the path again when another run put
  the table in place during the read (four attempts, no waiting).
- The plugin's skill as an instruction to Claude, with plugin manifest version 2.4.1; the
  plugin README, icon and privacy page; one theme for the README pictures; run 3 of the
  order-desk study and its post; updated GitHub Actions pins.

No new command, option, exit code, schema, record field or fixed text.

What can differ from 2.4.0: for a command agent with an MCP tool server, `final_state` and
so `record_sha256` for the same spec, in the cases where the boundary now waits; a trial
can last longer when a server does not exit after its input is closed. The changelog's
first entry lists the cases and the limits.

Known limits, not fixed in 2.4.1 (also the last changelog entry):

- `arci logs --keep`: when only the read under the directory lock finds the table
  unreadable, the run writes no table and prints no message about it. Record 0017 says such
  a run says so; this path does not. Record 0018 lists it as an open defect.
- The graded final state can still depend on timing in the cases the changelog lists.
- The pinned fixture server still writes its state file in place (a test file, not shipped).

Also in this pull request:

- `README.md`: one sentence that a third run of the study exists and is not in the table.
- `docs/COMPATIBILITY.md`: a section "Command trials in 2.4.1". `docs/ROADMAP.md`: "Done in
  v2.4.1". `docs/RELEASING.md`: the files record 0018 re-freezes, and a section saying the
  release page is published by hand.
- Three sentences about an installed copy of plugin version 2.4.0 now say that plugin
  version 2.4.1 holds the instruction. None says that a plugin updates by itself.

## How it was checked

- Before the branch: a read-only consult (kept in the working records) and seven read-only
  audits of `main` with a completeness check. No blocker. Both views: a patch release from
  what is on `main`, with the open limits stated.
- After the branch was built: five reviews (leftover versions, changelog facts, the record,
  wording, the release guards), each finding checked by a second reader. Seven wording
  corrections were confirmed and applied; no failing guard or test was found.
- Whole suite locally (macOS, Python 3.13): 5,272 passed, 21 skipped. Format, lint and
  types clean. `uv lock --check` passes; `uv.lock` differs from `main` in one line, the
  project's own version.
- Both packages built the way `release.yml` builds them. The source archive holds 83
  entries, all inside the allowlist. `.github/scripts/wheel_smoke.sh` passes on Python 3.11
  and 3.14 (macOS) with both wheels.
- The publish action's pin (`pypa/gh-action-pypi-publish`, updated since 2.4.0) is the
  commit of its tag v1.14.3, and the three inputs the workflow uses exist at that commit.
  It runs for the first time at this release's tag.
- Version 2.4.1 is unused on PyPI for both projects (checked 18 Nov 2026).
- Not checked locally: Linux, Windows, the adapter jobs and the SciPy oracle job. This pull
  request's CI is the first run of the branch there.

## Pinned files touched

Three lines of `FROZEN.sha256` change, under design record 0018
(`docs/design/0018-v2.4.1-release.md`), as `docs/RELEASING.md` step 4 describes:

- `pyproject.toml`: version 2.4.1 (re-hashed).
- `uv.lock`: the project's own version entry only (re-hashed).
- `docs/design/0018-v2.4.1-release.md`: new, pinned.

77 entries; every other hash is unchanged and `shasum -a 256 -c FROZEN.sha256` passes.

- [x] This pull request does not change any file listed in `FROZEN.sha256`, or it links the
      design record that authorizes the change.

## Privacy

- [x] No session logs, log lines or log file paths are attached anywhere in this pull request.

## After the merge

The tag `v2.4.1` goes on the merge commit only after CI on it is green. From the merge
until both publish jobs finish, the skills and the plugin on `main` name
`realornoise==2.4.1`, which is not on PyPI yet, so a run of the skill in that window fails
at install.
