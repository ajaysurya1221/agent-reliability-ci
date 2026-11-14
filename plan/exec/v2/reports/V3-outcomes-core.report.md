Review the V3 implementation: **689 combined tests passed**, with all required checks clean.

| Changed files | Final lines |
|---|---:|
| `src/arci/outcome_schema.py`, `outcomes.py`, `outcome_report.py` | 161, 862, 198 |
| `src/arci/importers/__init__.py`, `junit.py`, `inspect_log.py` | 79, 55, 142 |
| `src/arci/cli.py` | 1,480 (+211/−2) |
| `tests/unit/outcomes/__init__.py`, `test_cli.py`, `test_importers.py` | 0, 392, 349 |
| `test_kernel.py`, `test_previous_validation.py`, `test_schema_report.py`, `test_validation.py` under that directory | 357, 192, 226, 544 |

Verification:

```text
.venv/bin/pytest tests/unit/outcomes tests/unit/suite tests/unit/cli tests/unit/suite_cli -q -o addopts=
689 passed in 99.62s (0:01:39)

.venv/bin/pytest tests/acceptance/test_cli.py tests/unit/suite_report tests/unit/report -q -o addopts=
175 passed in 16.67s
```

- Ruff format/check clean; basedpyright: `0 errors, 0 warnings, 0 notes`.
- `shasum -a 256 -c FROZEN.sha256`: all **66 files OK**.
- Fresh-process `sys.modules` checks after importing `arci.cli` and executing the console script’s `--help` found no `arci.outcomes`, `arci.importers`, or `xml` imports.
- Only owned files changed. No dependencies, network operations, or git mutations.

Interpretations made:

1. **F4 conflict:** followed ADR’s “F2 with F4 when inputs were validated” over V3-CONTRACT’s “F2 alone as well.”
2. **Inspect headers:** “must … agree with the samples” means inconsistent headers or malformed error objects produce E6. Empty inventories retain their epochs as missing outcomes.
3. **Round assignment:** “file position supplies it only for a format carrying none” means empty unlabelled files supply missing positional rounds; empty labelled CSV files produce E6.
4. **Import-wide consistency:** enforced “One scorer serves the whole import” and integer/string identity conflicts across both arms.
5. **Diagnostics:** “one line on stderr” uses escaped CR/LF while preserving stored reasons. Malformed Unicode produces sealed errors. E26 compares readable round metadata without inventing counts when metadata is unreadable.

The packaged example remains the required exit-3 placeholder. Documentation and the second console command remain outside this brief. The F4 disagreement is the principal acceptance-compatibility risk.

This report is not acceptance evidence; the orchestrator must rerun checks.