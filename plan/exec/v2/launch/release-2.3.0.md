# Release page text for 2.3.0 (paste into the description box)

Open: https://github.com/ajaysurya1221/agent-reliability-ci/releases/new?tag=v2.3.0

Title: `v2.3.0: a result from session logs you already have`

Leave "Set as a pre-release" off and "Set as the latest release" on. Attach no files.

---

`uvx realornoise` (the same as `arci logs`) reads the Claude Code and Codex session logs already on your disk, compares recent days with earlier days for the same model and effort, and answers `REAL DROP`, `NO DROP` or `CANNOT TELL` (exit 1, 0, 2; `ERROR` is 3). It runs no model. Nothing is sent anywhere. The output holds counts, rates, dates and the names of the model and effort compared.

Try it (no logs needed):

```sh
uvx realornoise --example
```

On your own logs:

```sh
uvx realornoise
```

Compressed Codex logs need Python 3.14: `uvx --python 3.14 realornoise`.

### Added
- `arci logs`, also published as a second PyPI distribution, `realornoise`, which pins `agent-reliability-ci==2.3.0` and exposes the one command. Python 3.11 onward.
- Method `arci-logs/1`: exact rank tests on day values, no random numbers. Each wrong result is at most 2.5% per tool under four printed assumptions that the tool does not check.
- Text, Markdown (`--markdown`, made to paste into an issue), JSON (`--json`) and one-file HTML (`--html`) output; a packaged generated example (`--example`).
- A Claude Code plugin and a Codex skill that only run the command. Both put the printed numbers into that assistant's conversation.
- The [self-check](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.3.0/docs/results/logs-selfcheck.md): exact enumeration and simulated wrong-result rates with counts, seeds and intervals.

### Changed
- The README starts with logs, then imported results (`arci verdict`), then controlled trials (`arci run`). `arci verdict` and `arci run` are unchanged and remain the stronger evidence.

### Not in this release
- A scan over split dates, a comparison of two models, a range for the change, other coding agents, usage-limit or cost measures.

### Limits
- It shows what your logs recorded, not why. It cannot show a cause, answer quality or a change to a model: your tasks, prompts, projects and client changed too.
- With a short history the usual answer is `CANNOT TELL`.
- When days come in streaks the bound does not hold. In the self-check at day-to-day correlation 0.5, wrong `REAL DROP` was 0.080500 at 5 days after against 10 before, 0.035500 at 7 against 21, and 0.002500 at 14 against 42 (2000 histories each). The first two are above 0.025.
- Not verified: Windows, and log formats older than Claude Code 2.1.309 and Codex CLI 0.154.0.

Recipe: [docs/recipes/logs.md](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.3.0/docs/recipes/logs.md) · Statistics and limits: [docs/STATISTICS_LOGS.md](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.3.0/docs/STATISTICS_LOGS.md) · Design record: [0016](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.3.0/docs/design/0016-logs.md) · PyPI: [realornoise](https://pypi.org/project/realornoise/2.3.0/), [agent-reliability-ci](https://pypi.org/project/agent-reliability-ci/2.3.0/)

SHA-256 of the files on PyPI:
- `08c31a799dce59bf89d4ad0a12e556a0c7b2cebf2e472b74e8a8cd1ed0c76f53` (agent-reliability-ci wheel)
- `23b6f5b8a4646b012b2fe6a094d1e93d9c7638845fb17a399ef8784acf296114` (agent-reliability-ci sdist)
- `e6ae04497cdb57090519a1122ff267fa4b3855d79fc4ba13d7c9fde2dab7e724` (realornoise wheel)
- `a7a83788d1413ba63daa61acdf3bf40ac3b89f189cb570a51f9dec7db7134006` (realornoise sdist)
