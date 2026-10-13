# Run 2 plan (approved 2026-10-13 ~18:10Z; from the plan-mode file, planned jointly with Astra)

## Final plan: autonomous run 2, "post-release hardening and reference measurement"

Budget: 8 h wall-clock from Task 00 (stop starting tasks at 7 h 15 min). Same CONTRACT, lane
worktrees, review rule, tie-break order and HUMAN_INBOX protocol as run 1 (`plan/exec/PLAN.md`,
`plan/exec/CONTRACT.md`); records go to `plan/exec/run2/` with the same TASK/REPORT/REVIEW/CONSULT
formats; DECISIONS.md continues at D-11. Nothing in this run touches the decision rule, calibration,
`docs/STATISTICS.md`, `schema.py`, `interfaces.py` or any recorded result.

### Lanes and tasks
1. **T16 leftovers, code (lane `sprint/t16-code`, Opus coder; reviews: Fable + reviewer + Astra
   because `init.py` publication and the sealing path are touched).** (a) `arci run` prints
   `run store: <path>` on stderr after the verdict (stdout last line and report bytes pinned;
   `tests/acceptance/test_cli.py` must pass untouched); (b) `src/arci/init.py`: "hard links
   unsupported" only for `EOPNOTSUPP`/`ENOTSUP`/`EPERM`, otherwise append `strerror`; docstring
   notes macOS `fsync` is not `F_FULLFSYNC`; (c) `mcp_boundary.py` `sys.stdout.buffer` moved out of
   import time; (d) `.github/scripts/wheel_smoke.sh` runs `arci schema`; `release.yml` lists the
   sdist and fails on any path outside the allowlist (`src/arci/**`, README, LICENSE, NOTICE,
   CHANGELOG, pyproject, PKG-INFO, .gitignore); the action-fixture job asserts the step-summary
   file contains the report; (e) recipe-test nits from REVIEW 08-09 (inverse-control fixture
   checks `bare.json` on the unedited tree first; "INVALID whichever sources run" wording); (f) per
   the tie-break: README "Gate your own agent" command (below the fold; the first screen stays as
   ADR 0009 fixed it) carries `--task '{"order_id": "order-7"}'` for the sample and the T15 sentence
   is reworded to match; no sample `make_world` default; no dead-branch removal in `descriptor.py`.
   Done when: `just check`, `just frozen`, pinned-bytes tests (`tests/unit/report`,
   `tests/unit/examples`, `tests/unit/stats`) unchanged, first screen 191 words, lane CI green.
2. **T17 protocol and measurement docs (lane `sprint/t17-protocol`, Opus coder; reviews: Fable +
   reviewer).** `docs/measurement/ttfv-protocol.md`: §7.1 "one file per reader per track per
   attempt" and the §8.2/§8.4 rule for repeat attempts (first attempt counts; repeats listed, not
   ranked); `trials_started` across several stores; Track A installed-version check via
   `importlib.metadata`; q2 key reads "either integration route, correctly described"; failure
   taxonomy by milestone; `receipts/README.md` line 3 aligned. Also `plan/exec/scripts/`: stopwatch
   wrapper uses `$pipestatus`/`bash -c` (zsh-safe), `cohort_receipts.py` persists `agent_execution`
   and the trials lines in the result JSON and fixes `sentence()`; no existing receipt is edited.
3. **T18 reference-machine demo timing (lane `sprint/t18-refmachines`, Opus coder; reviews: Fable
   + reviewer + Astra for the workflow).** A new workflow `.github/workflows/ttfv-reference.yml`
   (push on `sprint/**` and `workflow_dispatch`; no secrets; `permissions: contents: read`) that on
   `ubuntu-latest` and `macos-latest` runs `uvx --from agent-reliability-ci==0.8.0 arci demo`
   five times each from an empty directory with a fresh `UV_CACHE_DIR` for the first run and warm
   for the rest, stamping command_start/demo_banner/demo_verdict/all_steps_held, and uploads a JSON
   artifact. The orchestrator downloads it and commits
   `docs/measurement/reference-machines/2026-10-<dd>-<os>.json` plus a short
   `docs/measurement/reference-machines/README.md` (what a reference machine is; these are machine
   timings, not receipts, per protocol §1.4). Why: the memo's demo target is "p50 ≤ 2 min, p95 ≤ 3
   min on clean reference machines"; Astra observed a macOS runner at 206 s. Done when: ten
   samples per OS recorded with p50/p95 computed in `plan/exec/measurements.md` and the result
   stated against the target, whichever way it falls.
4. **T19 Inspector compatibility check (orchestrator, read-only, ≤ 2 h; Astra consult).**
   Per fork F2 (tie-break below): check Inspector/TS-SDK release notes for support of revision
   2026-07-28, probe the latest Inspector once with network, and write a decision (D-11) with
   the exact negotiation change the bridge would need, which frozen files it touches (ADR 0002,
   `schema.py`, `mcp_toolset_server.py`), and whether an ADR is justified without an MCP pilot.
   No code change in this run unless the check shows a one-line, honest fix.
5. **T20 D2 import-record provenance model, design only (orchestrator + Astra; ADR 0010 draft in
   `plan/exec/run2/adr-0010-draft.md`, not under `docs/design/` until accepted).** The schema for an
   immutable imported-session record (source, version, original ids, completeness, raw digest,
   capability flags) that "cannot masquerade as a scheduled ARCI trial" (memo D2). Plus a fixture
   search (orchestrator, with network): public, versioned OTLP GenAI exports from two independent
   producers (OpenTelemetry semconv examples, Langfuse or Phoenix docs), each recorded with URL,
   version and sha256 in `plan/exec/run2/fixtures.md`. D3 (the importer) is **not** built in this
   run: it starts only when two authentic fixtures are in hand and the ADR is accepted (memo
   kill criterion line 306).
6. **T21 wrap-up (orchestrator).** `plan/exec/run2/FINAL_REPORT.md` (shipped vs this plan,
   deviations, review coverage, measurements incl. the reference-machine p50/p95 vs target,
   usage, known issues, next three steps) and an updated `plan/exec/HUMAN_INBOX.md`: the launch
   and outreach drafts unchanged and marked "waiting on you"; every memo metric with a date listed
   as unmeasured with the reason "no external users recruited"; the Nov 12 kill-criteria
   checkpoint listed as "cannot be evaluated without cold users". Push; main green.

### Explicitly not in this run (and why)
- D1 (user decision; memo kill criterion on broader schedulers); D3–D6 (no authentic fixtures yet;
  memo line 306); D7 (cookbook kill rule: recipe one not yet validated by a cold reader); D8 and
  every posting (user decision); R1–R8 (all conditional on external evidence); any change to the
  README first screen (ADR 0009), the decision rule, calibration or STATISTICS; Windows; HTML/PR
  reporting; resumability; telemetry; ADR 0005 `httpcore2` typo and hatchling hash pinning (wait
  for a justified re-freeze; a version bump alone is not one).
- No new maintainer or AI receipts: they move no metric. The reference-machine timings are the one
  measurement that the memo's target definition allows without users.

### Order and parallelism
T16 ‖ T17 (disjoint files) → T18 (needs nothing from them; starts when a coder slot frees) → T19 and
T20 run on the orchestrator's side throughout → merges in the order T17, T16, T18 (each after lane
CI and two reviews) → T21. At most two coders at once (user rule).

## Verification
- Every merge: isolated worktree `uv sync --frozen` + `just check` + `just frozen` + figure check +
  `arci schema` diff; pinned-bytes tests unchanged; lane CI green before the push; main CI green
  after.
- T16: `tests/acceptance/test_cli.py` untouched and green; a unit test that `arci run` writes the
  store line to stderr only; `init.py` errno tests (EOPNOTSUPP vs EIO messages); the release
  workflow's sdist allowlist exercised locally with `uv build --no-sources` + `tar -tzf`.
- T17: receipts README and protocol consistent (grep for "per attempt"); existing receipts byte-
  identical; `cohort_receipts.py` rebuild reproduces the ten cohort receipts from the persisted JSON
  without the temp stores.
- T18: the workflow runs green on the lane; the artifact parses; p50/p95 computed by a script
  under `plan/exec/scripts/` from the JSON (stdlib only).
- T19/T20: consults recorded under `plan/exec/run2/consults/`; decisions D-11/D-12 in
  `plan/exec/DECISIONS.md`.
- End state: main green; every lane merged or on a pushed branch with a REPORT; nothing
  half-applied; `plan/exec/run2/FINAL_REPORT.md` and HUMAN_INBOX pushed.
