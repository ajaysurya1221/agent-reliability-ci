# Pull request for the atomic state file (the maintainer creates and merges it)

Branch `v2/state-json-atomic` (`92f6ae0`), cut from `main` at `dd380d8`. Compare link:
https://github.com/ajaysurya1221/agent-reliability-ci/compare/main...v2/state-json-atomic?expand=1

Title: mcp: the tool server replaces state.json whole instead of writing it in place

---

## What

The tool server for Python toolsets (`arci.mcp_toolset_server`) wrote `state.json` in place,
which empties the file before the new content goes in. When a trial ends, the boundary closes
the server's input and, if it is still running, stops it with SIGKILL. A stop at that moment
left a 0-byte file, the grader reported "snapshot failed", and the trial ended `ERROR`.

Seen once in hosted CI (run 44040610550, `check / Python 3.14`): 1 trial of 100 in
`tests/acceptance/test_hero_decisions.py` ended `ERROR` instead of `FAIL`, which failed the
test (no trial may be `ERROR`).

The server now writes `state.json.tmp` in the same folder and moves it into place with
`os.replace`, so the grader reads no file or a complete file. The bytes and the file mode
are the same as before.

One behaviour changes: when a snapshot cannot be written (for example text that cannot be
encoded), `state.json` keeps the last complete state instead of being left empty. The tool
call still returns -32603 "snapshot failed".

## Not changed by this pull request

- For an agent that never uses the tool server, the graded final state is still `{}` or the
  starting state, by timing. That is handled separately on `v2/server-stop-wait`.
- The pinned fixture server (`tests/acceptance/mcp_fixture_server.py`) also writes in place.
  It is frozen and was not touched.

## How it was checked

- 7 new unit tests (`tests/unit/mcp_toolset/test_atomic_snapshot.py`). They read the file at
  every Python call and return during a write: 5 of the 7 fail when the old source file is
  put back, all 7 pass with the change.
- Two separate reviews of the change; their corrections are applied.
- Whole suite: 5,162 passed, 21 skipped. The hero acceptance test passed 20 times in a row.
  Lint, format and types clean.
- All of that on macOS. Not checked on Linux with Python 3.14, where the failure was seen;
  this pull request's CI is the first run there.

## Pinned files touched

None. All 76 hashes in `FROZEN.sha256` match.

- [x] This pull request does not change any file listed in `FROZEN.sha256`, or it links the
      design record that authorizes the change.

## Privacy

- [x] No session logs, log lines or log file paths are attached anywhere in this pull request.
