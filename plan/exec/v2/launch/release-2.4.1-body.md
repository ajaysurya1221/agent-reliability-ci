Release page text for the tag v2.4.1. The maintainer publishes the page. Both packages are
on PyPI and verified (18 Nov 2026); the four hashes at the end are the workflow's SHA256SUMS
and equal what PyPI serves. Title and everything below the line go on the page.

Title: v2.4.1: fixes since 2.4.0

---

A patch release: fixes, a changed plugin skill, updated Action pins and documents. No new command, option, exit code, schema, record field or fixed text.

```sh
uvx --python 3.14 realornoise==2.4.1 --example
```

### Fixed
- **An empty `state.json` could end a trial in `ERROR`.** The tool server for Python toolsets (`arci.mcp_toolset_server`) wrote the file in place, and a stop during a write left it empty. It now writes a temporary file and moves it into place. When a snapshot cannot be written, the last complete state stays. Seen once in hosted CI, in 1 trial of 100.
- **The graded final state of a command agent that never used its MCP tool server could depend on timing** (`{}` or the server's starting state). 2.4.1 narrows this and does not remove it (see Known limits). At the end of a command trial the boundary now waits for its tool server when waiting can change what is graded: it closes the server's input and, if the server is still running, sends SIGTERM after half of the time left before the trial's deadline and SIGKILL after three quarters. An idle server is closed and killed at once, as before.
- **Two `arci logs --keep` runs that started together with no kept table yet could leave one run's rows out of the table.** The reader now reads the path again when it was absent at one call and present at the next (four attempts, no waiting). A run affected in 2.4.0 printed that the kept table could not be read, and the next run with `--keep` writes the missing rows.

### Changed
- The Claude Code plugin's skill is an instruction to Claude: run `uvx --python 3.14 realornoise==2.4.1` once, with nothing added, and show the output unchanged. If anything is typed after the command name, Claude runs nothing (options work when `realornoise` is run in a terminal). An exit status of 1 or 2 is the result, not a failure. Nothing is approved ahead of time; whether Claude Code asks first depends on your permission mode and settings. Plugin version 2.4.1 holds the instruction; a copy of plugin version 2.4.0 installed before the skill became an instruction keeps the earlier skill until the plugin is updated.
- Pinned GitHub Actions in the workflows and in `action.yml` are updated.

### What can differ from 2.4.0
- For a command agent with an MCP tool server, `final_state`, and so `record_sha256`, can differ for the same spec in the cases where the boundary now waits. That difference is the fix. Records stored by 2.4.0 stay as they are; nothing in 2.4.1 re-grades them.
- A trial can last longer when a server does not exit after its input is closed, and in a narrow case can end in timeout instead of completed. A tool call fully written to the server when the agent left may complete during the wait: its effect can reach the final state, and its reply is not recorded. The [changelog](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.1/CHANGELOG.md)'s first entry lists the cases.

### Known limits, not fixed in 2.4.1
- `arci logs --keep`: when the read before the directory lock finds no table or a readable one, and the read under the lock then finds the table unreadable, the run writes no table and prints no message about it. The rows are not lost while the logs still exist; if the vendor has deleted those days by the next run with `--keep`, they cannot be recovered.
- The graded final state can still depend on timing: a server that answers before it writes its state, that saves only when its input closes, that writes its state in reaction to a notification, or whose start-up takes longer than half of the time left. The changelog's first entry lists every case. The stop's stages are not recorded, so keep the version of arci beside a stored result.
- Not verified: Windows beyond install and `--help`.

### Documents
- A third pre-registered run of the [order-desk study](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.1/docs/results/order-desk-study.md), with its sealed store and a [post](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.1/docs/blog/2026-11-order-desk-run-3.md).
- A [privacy page](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.1/docs/PRIVACY.md) and a README inside the plugin folder; one theme for the README pictures.

Changelog: [v2.4.1](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.1/CHANGELOG.md) · Design record: [0018](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.1/docs/design/0018-v2.4.1-release.md) · Compatibility: [docs/COMPATIBILITY.md](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.4.1/docs/COMPATIBILITY.md) · PyPI: [realornoise](https://pypi.org/project/realornoise/2.4.1/), [agent-reliability-ci](https://pypi.org/project/agent-reliability-ci/2.4.1/)

SHA-256 of the files on PyPI:
- `9e3e41e43959ece5b0ad11c6f3754674d97275bd499fc643d45ef89202e31ca7` (agent-reliability-ci wheel)
- `b828e1ca33462c0918f6e27abf6fce4ece22bcdc861aaa28d6040a385bfcd463` (agent-reliability-ci sdist)
- `287652432b591ffb9b30830616136fa6e158d7f084f3b4a5538fef998147102b` (realornoise wheel)
- `2415763eac04ac62a410c055f04d33bb0175a61606937d6151ff23c911ccdf73` (realornoise sdist)
