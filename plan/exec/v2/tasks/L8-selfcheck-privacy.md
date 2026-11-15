# L8: the self-check script and the privacy tests

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` and follow
its rules. Behaviour: the statistics contract in full, above all "Checks that agents run"
and "What the method cannot see"; record 0016, decision 6. The code under `src/arci/logs/`
exists; use it, do not edit it (a bug you find: stop and report it). Another agent is
editing `report.py`, `cli.py`, `html.py` and the example at the same time; do not touch
those, and do not depend on exact output text.

## You own

- `bench/selfcheck_logs.py`
- `tests/unit/logs/privacy/` (`__init__.py`, `test_canary.py`, `test_audit_hook.py`,
  `test_imports.py`, `test_json_leaves.py`)
- `tests/unit/logs/test_selfcheck_quick.py`
- `docs/results/logs-selfcheck.md` (the script's printed tables, written by the script)

## `bench/selfcheck_logs.py`

A script in the style of `bench/selfcheck_suite.py` (read it first), with `--quick` for the
test suite and a full mode. It uses the product's `rank_test`, `measures.build` and
`decide.decide_tool` on hand-built `ReadResult`s (build `Response` objects directly; no log
files), so that setting selection, usable-day rules, the streak check and the ladder are all
exercised. Seeds, counts and elapsed time are printed; every simulated rate is printed with
its count and a 95% interval (Wilson). Sections:

1. **Exact.** `g_tail`, `p_real` and `p_streak` equal brute-force enumeration for every case
   with at most 12 days in total (full mode: 14); for those cases the share of labelings on
   which each test rejects at its level is at most the level.
2. **Null, final rule.** For designs (usable after/before days) 5/10, 7/21, 14/42, 28/84:
   20,000 seeded histories (quick: 300 at 7/21 only) with day values drawn independently
   and identically (log-normal reasoning medians with log standard deviation 0.45; shares
   from a smooth bounded distribution), once with independent measures and once with all
   three measures sharing ranks. Report the rate of REAL DROP; gate: at most 0.0283. With
   one measure moved exactly to its margin and the others unchanged: the rate of NO DROP;
   gate: at most 0.0283.
3. **Power, final rule.** REAL DROP rates for reasoning drops of 33%, 45%, 50%, 55% at log
   standard deviations 0.35, 0.45, 0.55 for the four designs, and the NO DROP rate when
   nothing changed, 2,000 runs per cell (quick: skipped). Also the single cell the contract
   names: a 45% drop at 14/42 with log standard deviation 0.40. No gate.
4. **Days that come in streaks.** AR(1) day values with coefficient 0.3, 0.5 and 0.7 for the
   four designs, 5,000 runs per cell (quick: skipped): the rates of REAL DROP and NO DROP
   with the streak check as built, and the rate of REAL DROP with the streak check switched
   off (compute the ladder from the findings yourself with `p_streak` ignored). No gate;
   these are the figures the contract promises to publish.
5. **Two counterexamples of the review**, each shown to break the bound when its assumption
   is dropped: choosing the model by after-period counts (construct the 15-day, 3,003-model
   case and show the selected model's `p_real` is 1/3003 every time, while the product's
   pooled-count selection does not select by period); and a change that swaps which days
   are usable (construct the 98-day case and report the NO DROP rate when assumption A4 is
   violated). Clearly labelled as demonstrations, not product behaviour.
6. A final table of gates with PASS or FAIL and a non-zero exit when any gate fails.

Full mode writes `docs/results/logs-selfcheck.md` (plain Markdown tables, the command line,
seeds, counts, the date passed in with `--date`, no machine-specific path). Keep full mode
under about 20 minutes on a laptop; if a cell is too slow, lower its count and print the
count used. Run full mode once and commit nothing (the orchestrator does).

## Privacy tests (`tests/unit/logs/privacy/`)

Use `tests/unit/logs/synth_logs.py` to make logs with canaries.

1. `test_canary.py`: run `arci.logs.cli.run` on synthetic logs for both tools with every
   output option; no canary token (upper case, lower-case model-shaped, digit version-shaped,
   `acme-payroll-secret`, `gpt-12345678-87654321`, working directories, file names of the
   log files) appears in `out`, `err` or any written file; also when a log file is corrupt
   and when an output path is unwritable.
2. `test_audit_hook.py`: with `sys.addaudithook` (install once per process; filter by a
   flag), a full `run` over synthetic logs triggers no `socket.*`, `subprocess.Popen`,
   `os.system`, `os.exec*`, `os.posix_spawn` or `urllib.Request` event, and every `open`
   for writing targets only the paths given to `--json`, `--markdown`, `--html`.
3. `test_imports.py`: parse every module under `src/arci/logs/` with `ast`; imports are only
   from the standard library allow-list written in the test (no `socket`, `subprocess`,
   `urllib`, `http`, `ssl`, `requests`, `ctypes`, `multiprocessing`, `random`), `pydantic`,
   and the `arci` modules the contract names (plus `arci.logs.*`). `random` is banned in
   `src/arci/logs/`.
4. `test_json_leaves.py`: every string leaf of the `--json` output is a date, a rational, a
   hex digest, a version of the package, or a name the code can generate (closed lists from
   `schema.py`, accepted model grammar, `model-N`, `effort-N`).

`tests/unit/logs/test_selfcheck_quick.py` runs the script's quick mode in-process and
requires exit 0.

## Done when

`.venv/bin/pytest tests/unit/logs -q` passes; the full self-check has run and its gates
pass; ruff format, ruff check and basedpyright are clean on your files;
`shasum -a 256 -c FROZEN.sha256` still passes. Final message: the gate table, the streak
table (with and without the check), files changed, anything you could not do.
