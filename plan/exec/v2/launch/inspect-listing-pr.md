# Pull request to UKGovernmentBEIS/inspect_ai (prepared 2026-11-14, not yet opened)

Branch: `ajaysurya1221:inspect_ai:docs/list-arci-verdict` (commit `4a3d696`, one entry appended to `docs/extensions/extensions.yml`).

Title: docs: add ARCI verdict to the extensions listing

### Problem or current behavior
A user with two sets of eval logs (a baseline and a candidate) can compare their scores, but the listing has no tool that turns repeated epochs of both into a gate verdict under a rule written down beforehand. Issue #4206 (a proposal for paired deltas, multiplicity and power) was closed on 11 Sep 2026 with a collaborator's note that it would be useful as a standalone extension rather than part of Inspect core.

### Result or new behavior
Adds [ARCI verdict](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/recipes/verdict.md) to the listing (Analysis category). `arci verdict` reads one baseline and one candidate Inspect JSON log (`inspect log dump FILE.eval > FILE.json`), treats epochs as rounds and the sample `id` as the pairing key, and returns PASS, BLOCK or INCONCLUSIVE with exit codes 0, 1, 2 from a rule file (task list, margin, rounds). It is a sequential non-inferiority test in exact arithmetic: PASS means "not worse by the margin or more", never that the candidate is better. The error bound is printed only when the rule file declares it was fixed before the runs; a rule written after the logs exist gives a labelled descriptive verdict. It runs nothing and adds no dependency to Inspect. Apache-2.0, on PyPI as `agent-reliability-ci` (2.2.0).

Inspect MLflow, already listed, has an evaluation comparison with McNemar's test; this entry is a different thing (a pre-registered gate over repeated epochs), not a claim to be the only comparison tool.

### Compatibility and migration
No migration required. One entry is appended to `docs/extensions/extensions.yml`; nothing else changes.

### Validation
- The YAML file loads and the new entry has the same four keys as its neighbours.
- The tool's Inspect reader was tested against logs written by inspect-ai 0.3.289 (JSON form, 9 samples, 3 epochs, two scorers, one errored sample, an integer sample id); those logs and the generator script are in the tool's repository under `tests/unit/outcomes/real/inspect/`.
- The same generator was re-run on 15 Nov 2026 with inspect-ai 0.3.290 and the released 2.2.0 from PyPI: a JSON-format log and the output of `inspect log dump` on a `.eval` log both gave the verdict the recipe shows.
- Limits a reader should know: `.eval` files are not read directly (the JSON form is), and one log per arm is supported.

### Agent review
Entry and description drafted with Claude Code and read by me before opening. No separate review pass ran on this one-entry change.
