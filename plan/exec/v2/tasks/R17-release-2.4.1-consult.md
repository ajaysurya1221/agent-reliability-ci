# R17: consult on cutting release 2.4.1 (read-only)

You are the consultant. You change no file and run no git command that changes state.
Answer in under 600 words. Read the code in the worktree
`/Users/ajay/Developer/.arci-worktrees/wt-v2-logs` (detached at `main`, commit `06a01f5`),
not in the folder you were started in.

## Where we are

`main` has four changes merged since the tag `v2.4.0` that are not released (PyPI has 2.4.0
of `agent-reliability-ci` and `realornoise`). They are the first entries of `CHANGELOG.md`
under "Unreleased", together with earlier unreleased entries (documents, the plugin's skill
rewritten as an instruction, the plugin README and icon, the privacy page):

1. `src/arci/mcp_toolset_server.py`: `state.json` is written to a temporary file and moved
   into place (a kill during a write left a 0-byte file and the trial ended ERROR).
2. `src/arci/mcp_boundary.py`, `src/arci/runner.py`: at the end of a command trial the
   boundary stops its MCP tool server in stages (close input, wait, SIGTERM at half of the
   time left, SIGKILL at three quarters) when the server is not idle; an idle server is
   killed at once as before. Your answers R15 and R16 are in
   `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/`.
3. `src/arci/logs/kept.py`: the kept-table reader reads the path again (four attempts, no
   waiting) when it was absent at one call and present at the next.
4. README figures and badges redrawn with one theme (no code change).

Hosted CI on `main` at `06a01f5` is green (14 jobs: Python 3.11 and 3.14, Linux, macOS,
Windows install). Locally: 5,272 tests passed, 21 skipped.

Known and not fixed:

- The pinned fixture server `tests/acceptance/mcp_fixture_server.py` writes its state file
  in place (frozen file).
- In `arci logs --keep`, when the first (unlocked) read says absent or read and the locked
  read says unreadable, the write is dropped without a message
  (`src/arci/logs/cli.py`, `_execute`; `src/arci/logs/kept.py`).
- The timing dependence of the graded final state is narrowed, not removed (limits are in
  the changelog entry).

The release procedure is `docs/RELEASING.md`: a design record under `docs/design/`, the
version in every listed location, `uv.lock` regenerated, HTML goldens regenerated, the
changelog section, `FROZEN.sha256` recomputed for `pyproject.toml`, `uv.lock` and the new
record, pull request to `main`, tag `v2.4.1` after the maintainer merges, then
`.github/workflows/release.yml` publishes both packages.

The maintainer said "Yes, prepare 2.4.1". The maintainer merges and publishes the release
page; I prepare everything else.

## My leaning

Cut 2.4.1 now as a patch release with exactly what is on `main`, fix none of the three open
items in it, and state them in the release text. Reasons: all changes are fixes or
documents; no schema, command, option, exit code or record field changes; the two races
were seen in CI and users of 2.4.0 have them; a bump of the plugin's manifest version is
what lets an installed copy of the plugin pick up the skill that was rewritten after 2.4.0.

My doubts:

- Whether the staged stop is a patch-level change under `docs/COMPATIBILITY.md`: the graded
  final state can now differ from 2.4.0 for the same spec (that is the fix), a trial with a
  server that ignores EOF can last longer, and in a narrow case end in timeout instead of
  completed.
- Whether any pinned document (`docs/AGENT_SEMANTICS.md`, `docs/TRUST_MODEL.md`,
  `docs/design/**`) states the old behaviour (kill at once) in words the new behaviour
  contradicts, so that the record for 2.4.1 must say so.
- The dropped write without a message: fix before the release, or ship and state it.
- The skills and the plugin pin `realornoise==2.4.1` on `main` from the merge until the
  publish job finishes (minutes), so a user who runs the skill in that window gets an
  install error. The same window existed for 2.4.0.
- The plugin is "In review" at a plugin directory with manifest version 2.4.0.
- The publish action was updated by Dependabot after 2.4.0
  (`git diff v2.4.0..HEAD -- .github/workflows/release.yml`); this tag is its first run.

## What I need from you

1. Release now, or not yet; and the version number (2.4.1 or 2.5.0), with the sentence of
   `docs/COMPATIBILITY.md` you rest it on, quoted. One line each, and whether you disagree
   with my leaning.
2. Any pinned sentence the merged changes contradict, quoted with file and line. If none,
   say how you checked.
3. The dropped write: fix before release or ship with a note, and why. If fix: the smallest
   correct change and the smallest test.
4. What the design record for 2.4.1 must state, as a short list.
5. What you would check before the tag that the procedure in `docs/RELEASING.md` does not
   already check, and anything in `.github/workflows/release.yml` as it is now that could
   fail at this tag.
6. What could go wrong that I have not listed.
