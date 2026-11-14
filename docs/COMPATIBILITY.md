# The v1 public contract

ARCI 1.x supports the documented CLI, its exit meanings, and the versioned native
experiment, evidence and diagnostic formats. Existing frozen specifications and
acceptance tests remain authoritative. A major version is a compatibility
commitment, not evidence of production safety, adoption or novel algorithms.

Within 1.x, a valid existing documented command and supported record must retain
its meaning. Additive commands or optional output fields may arrive in minor
releases. Consumers should select JSON by its `schema_version`, read the fields
they need and tolerate additional fields. Removing or reinterpreting a documented
field or exit requires an explicit compatibility decision and major-version
change; frozen semantic changes also require the existing amendment process.

Human-readable text, formatting and diagnostic wording are presentation, not a
parsing API. Use `--format json` where supported. Internal Python modules are not
a promised general-purpose SDK; documented agent/oracle interfaces remain governed
by [their frozen contracts](AGENT_SEMANTICS.md).

The boundaries that matter for the new diagnosis workflow are:

- `arci triage` preserves the complete gate's PASS/0, BLOCK/1, INCONCLUSIVE/2 or
  ERROR/3. Invalid diagnosis also exits 3 and is identified separately.
- `arci trace-check` reports diagnostic MATCH/0, DRIFT/1 or INVALID/3. These labels
  do not replace a statistical decision or establish causation.
- Native integrity seals detect inconsistent records; they do not authenticate
  execution. Replay is a separate operation over trusted code and recorded
  boundaries, not a promise of deterministic fresh model inference.
- Existing archived evidence stays immutable. The release does not migrate or
  rewrite historical stores, change denominators or reinterpret prior decisions.

See [the trust model](TRUST_MODEL.md), [statistics](STATISTICS.md) and
[release procedure](RELEASING.md) for the complete constraints. POSIX is the
supported runtime; Windows installation/help smoke coverage is not full runtime
support. Live providers and arbitrary external trace formats are not covered by
the offline demo or these native-store diagnostics.

## The 2.x additions

2.0.0 added the `arci-suite/1` record kind (a grid of tasks by fault conditions,
run in balanced rounds), suite support in `run`, `gate`, `report`, `triage`,
`diff` and `plan`, Markdown/JSON/HTML suite reports with fault accounting, and
the optional `langchain` extra. 2.1.0 added a "tool outcomes" section to suite
reports and did not change any record kind, command or exit code. 2.2.0 added
the `arci-outcomes/1` record kind (a verdict from pass/fail outcomes another
tool already produced) and the commands `arci verdict`, `arci verdict-rule`
and `arci verdict --example`; it did not change any existing record kind,
command or exit code.

Kept stable through 2.x, each because an existing test pins it:

- The `arci-suite/1` schema version and the `SuiteManifest`/`SuiteDecision`
  shapes it validates against: `tests/acceptance/test_suite_schema.py` (frozen).
- Suite exit codes PASS/0, BLOCK/1, INCONCLUSIVE/2, ERROR/3, including that an
  unsupported suite operation refuses with exit 3: `tests/unit/suite_cli/test_cli.py`.
- The keys of the suite JSON report keep their names and meaning; keys may be
  added, as 2.1.0 added `tool_outcomes`. The current content is checked against
  stored fixtures: `tests/unit/suite_report/test_reports.py`.
- `arci` import and `arci --help` never load `langchain`, so the core stays
  importable without the extra: `tests/unit/adapters/test_lazy_import.py`.
- The v1 (`arci/0.5`) JSON report is pinned byte for byte:
  `tests/unit/suite_report/test_v1_json_pin.py`.
- The `arci-outcomes/1` schema version, verdict exit codes PASS/0, BLOCK/1,
  INCONCLUSIVE/2, ERROR/3, the `OutcomeDecision` JSON artifact's fields, and the
  fixed texts (including F1's descriptive-verdict label and the F15/F16 crossing
  reasons it renders in place of the suite's): `tests/acceptance/test_outcomes.py`.

Not promised: the wording and layout of the suite Markdown and HTML reports; `minimize`,
`bundle`, `replay`, `trace-check` and JUnit for suites (each currently refuses); the
LangChain adapter's internal call shape, async agents or interrupts; the terminal and
Markdown layout of an `arci verdict` report; and anything else design records 0011-0015
list as not built. Each of those may change without a major-version bump.
