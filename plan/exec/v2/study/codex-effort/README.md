# Codex effort comparison

The [registration draft](../PREREGISTRATION-codex-effort.draft.md) defines the question,
the ten tickets, the rule and the stopping conditions. No live invocation is needed
to build or check the study. The driver requires a separately finalized registration.

## Check locally

Run from `plan/exec/v2/study` on the registered laptop.

```sh
ARCI_PY=/Users/ajay/Developer/.arci-worktrees/run4-env/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
"$ARCI_PY" -m pytest -o addopts= -p no:cacheprovider -q codex-effort/tests
"$ARCI_PY" codex-effort/plan_size.py
shasum -a 256 -c codex-effort/digests.sha256
```

Each regression witness fails on its parent. Every registered preservation case passes
on the parent. Both groups pass on the historical fix. The production grader accepts a
stand-in's reference patch and rejects an untouched export. The two-round rehearsal
checks an INCONCLUSIVE followed by a BLOCK and reproduces the decision byte for byte.
The open-audit hook in the synthetic kept-read test schedules the race independently
of the Python open API. The campaign agent has no descendant file-open tracing.

### Qualified tickets

Reference grade seconds include export, inventory, diff application and pytest. The
visible cases and hidden preservation cases passed on both required qualification paths.

| Ticket | Visible | Hidden regression | Hidden preservation | Reference seconds |
|---|---:|---:|---:|---:|
| csv-spaces | 6 | 1 | 0 | 1.04 |
| fault-report | 2 | 3 | 0 | 1.01 |
| init-write | 5 | 1 | 0 | 0.97 |
| interrupted-report | 4 | 9 | 9 | 1.22 |
| keep-output | 4 | 1 | 1 | 1.17 |
| kept-read | 4 | 1 | 0 | 1.23 |
| round-label | 58 | 2 | 1 | 1.07 |
| shorthand | 50 | 1 | 0 | 1.04 |
| snapshot | 2 | 1 | 0 | 1.72 |
| store-lines | 2 | 3 | 0 | 1.21 |

The CSV reference applies only the blank-line hunk of the historical outcomes.py fix.
The keep-output prefix and round-label's acceptance of -0 follow their historical
versions. Hidden supplements and selected case IDs are covered by the digest manifest.

## Finalize and start once

1. **Before sealing the registration**, run the full stand-in suite from the owner's
   terminal outside any sandbox, in `plan/exec/v2/study`.

```sh
RUN5_CHECK_CONFINEMENT=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS='' /Users/ajay/Developer/.arci-worktrees/run4-env/bin/python -m pytest -o addopts= -p no:cacheprovider -q codex-effort/tests
```

   The environment variable name `RUN5_CHECK_CONFINEMENT` is historical.
   The probe runs pytest under the production macOS grader profile. It must read its
   exported test and write and read scratch. It must receive permission errors when
   rewriting the test or reading or changing a private campaign sentinel. A companion
   stand-in confirms the probe fails with confinement disabled. A skipped or failed
   probe leaves host confinement unverified. Keep the registration unsealed until the
   enabled full suite passes.
2. The owner fills the three draft fields, saves the sibling `PREREGISTRATION-codex-effort.md`,
   and publishes it together with the registered inputs on `v2/phase0`. Compute the
   manifest hash with `shasum -a 256 codex-effort/digests.sha256`. Record the actual
   commit and push time.
3. From the study directory, check publication, the fixed private work directory, both
   markers and dependency-only grading with OS confinement. The check exercises only
   stand-ins, including the file-permission probe, and leaves the start available.

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ajay/Developer/.arci-worktrees/run4-env/bin/python codex-effort/driver.py --check-start
```

4. At the authorized start, repeat all checks and atomically claim the campaign. The
   default is four pairs. Both commands run under caffeinate.

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ajay/Developer/.arci-worktrees/run4-env/bin/python codex-effort/driver.py
```

All worktrees use `/Users/ajay/Developer/.arci-worktrees/codex-effort.started`.
The local `codex-effort/codex-effort.started` and `runs-codex-effort` guards also apply. Keep the markers
after interruption. The driver checks the actual remote tip twice with read-only Git.
The private work root is fixed at `/Users/ajay/Developer/.arci-worktrees/codex-effort-private`
and must be empty and owner-only. The agent uses the owner's signed-in profile.
`--ephemeral` prevents saving this session to disk. The registered trial argv appears
in the draft. The start log records the SHA-256 of CODEX_BIN and its resolved native
executable. Every trial checks and records both digests before launching the agent.

## Trial evidence and reading the decision

| Location | Contents |
|---|---|
| Fixed private work root | Complete stdout JSONL per trial (`.transcript`), separate stderr and last message. Temporary exports are removed after grading. |
| `runs-codex-effort/start.json`, `preflight.log` | UTC start, published commit, registered manifest, CLI version and digest, runtimes and stand-in results. |
| `runs-codex-effort/schedule.json`, `trials.jsonl` | Assigned arm order and one result per admitted trial in completion order. |
| `runs-codex-effort/rNN-TICKET-ARM/` | Start receipt, patch and digest, grade, applicable private-log digest, event IDs and grader evidence. |
| `runs-codex-effort/stop.json` and round files | Complete-round CSVs, decisions and replay, stop reason, partial work and audit counts. |

The agent and every grader use codex-effort-agent-env with the export's src on PYTHONPATH.
Only the harness tests and ARCI verdict use run4-env. The live grader confines writes
to its temporary scratch, protects tests and excludes the campaign evidence from
its readable roots. In a nested sandbox, offline tests use trusted stand-ins without
this additional boundary. The start check requires the complete suite with confinement
enabled, including a write/read probe. The submitted code shares the pytest process.

Both arms receive 1,200 seconds. A confirmed agent crash, wrong patch or genuine
deadline miss fails. Terminal CLI diagnostics plus exit status attribute service
errors, including a documented stall at timeout. Tool output has no authority over
this label. An unattributed termination is an error and blocks interpretation.
Ambiguous pytest exits, timeouts and incomplete or malformed case identities trigger a
matched-budget reference control and, if green, a fresh submission control. An unstable
result or reference fault counts as error. The two initial grading stages share 90
seconds. Controls can add wall time.

The full preflight has 30 minutes and the CLI version check has 30 seconds. Each Git,
tar, native-path resolver and ARCI verdict subprocess has 60 seconds. Git prompts are
disabled. An infrastructure timeout records an error or, during preflight, refuses
admission with ERROR before consuming the start.

The audit runs before export cleanup. It resolves observable paths, scans commands,
tool arguments and command results, and counts denied attempts independently. A
crossing requires zero outside_read, unauditable and unattributed terminations in
each arm across complete and partial rounds, plus the registration's other checks.
The original grades stay in complete-round CSVs. The stop record gives counts by arm
and ticket and distinct affected pairs. An ineligible crossing is retained and exits 3.
Inspect private evidence before publication and document redactions.

Admission lasts up to eight hours. Finish admitted work and keep partial-round JSONL.
Only complete rounds enter CSVs. With no completed round there is no CSV verdict.
An unmatched start after a hard interruption invalidates interpretation. Total elapsed
time includes setup and grading. Publish time-limit counts by arm separately from the
120, 300 and 1,200 second elapsed-time bands. A null patch digest means capture did
not finish. A zero-byte patch has the SHA-256 of empty bytes.

## Recompute the last complete look

From `codex-effort/runs-codex-effort`, for example if round two was the last complete round, run

```sh
"$ARCI_PY" -I -B -m arci verdict ../rule.yaml --baseline baseline.csv \
  --candidate candidate.csv --previous round-01.json
```

Omit `--previous` for round one. Otherwise use the immediately preceding decision.
The driver repeats the final invocation with the identical rule path and input path
spellings and compares decision bytes. It also checks the CSV rows against the trial
records, the start receipts and the saved patch hashes. Read the campaign stop record
alongside the prefix verdict whenever an incomplete round exists.
