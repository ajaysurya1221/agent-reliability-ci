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

## Session logs in 2.3.0

2.3.0 adds `arci logs`, the `realornoise` distribution and the new record kind
`arci-logs/1`. Existing commands and records retain their meaning. Within this method
version, the record fields, exit codes and fixed texts in
[record 0016](design/0016-logs.md) are promised: REAL DROP/1, NO DROP/0, CANNOT TELL/2,
ERROR/3. With several tools the process uses the precedence in
[STATISTICS_LOGS.md](STATISTICS_LOGS.md); an ERROR for one tool does not erase the other
result. Usage and requested-output write errors exit 3.

The log formats of other vendors' tools are not promised. The checked client versions
are listed in [LOG_FORMATS.md](LOG_FORMATS.md); future formats can need reader changes.
Windows is untested for `arci logs`. A record seal checks consistency, not authenticity
or the truth of the statistical assumptions. The general presentation disclaimer above
does not remove the fixed-text commitment within this method version.

## Session logs in 2.4.0

2.4.0 writes `arci-logs/2`. [Record 0017](design/0017-logs-2.md) fixes its fields,
selection rule, tests, exits and texts. The default setting is selected by after-period
response counts, falling back to the whole window only when no candidate has an after
response. The record adds short-history dates, bounded client versions, keep options and
day sources. The result names and exit codes above are unchanged. One day uses one source
for every measure. Existing `arci-logs/1` records stay readable through
`arci.logs.schema.LogsDecisionV1`; they are not silently converted or reinterpreted.
`LogsDecision` validates version 2. Choose the model by `schema_version`.

In 2.4.0 the readers return client-version names and also return main-thread and
sub-agent responses that lack a model or an effort. Those responses count only toward
context counts and the version list, never toward responses or day values. The readers
take model and effort names from the kept table so labels stay stable across runs.
Context counts can therefore differ from those 2.3.0 printed for the same logs.
2.4.0 follows the definition in the records.

The optional kept table uses its own `schema` field, `realornoise-days/1`. Its strict row
format, merge, pruning and retention rules are defined in record 0017 and
[LOG_FORMATS.md](LOG_FORMATS.md#kept-day-table-realornoise-days1). It stores daily counts,
dates and accepted setting names. A malformed or unknown table is left unused, not
migrated or overwritten. It has no authentication; editing its counts can change a result.
The retention promise requires whole-day captures at most 29 days apart under the stated
file-deletion assumptions. It does not recover days that were never captured whole.

The 2.4.0 change leaves controlled-trial and imported-outcome contracts unchanged. Vendor
log formats, an error rate for repeated daily looks, and assumptions about a user's task
mix are not compatibility promises.

## Command trials in 2.4.1

2.4.1 changes no schema, command, option, exit code, record field or fixed text. At the
end of a command trial the boundary can now wait for its MCP tool server before stopping
it. For the same spec, `final_state`, and therefore `record_sha256`, can then differ from
what 2.4.0 sealed, in the cases the [changelog](../CHANGELOG.md) lists; that difference
is the fix. A trial can last longer when a server does not exit after its input is
closed, and in a narrow case the changelog names a trial can end in timeout instead of
completed. Nothing about the stop is recorded. Stored 2.4.0 records stay valid and are
not re-graded. `arci-logs/2` records and the kept table format `realornoise-days/1` are
unchanged. See [record 0018](design/0018-v2.4.1-release.md).

## 2.5.0

2.5.0 adds `arci check-change` and `arci convert`. Existing commands, exit codes, fixed
text and records keep their meaning. The log format `arci-logs/2` and the kept table format
`realornoise-days/1` are unchanged. `arci verdict` and `arci verdict-rule` keep their
behaviour. The `junit`, `csv`, `jsonl` and `inspect` readers handle existing input as before.

The input format in a sealed imported-outcome decision is still `csv`, `jsonl`, `junit`
or `inspect`. With `check-change --format promptfoo`, ARCI converts the results to JSONL.
The sealed decision names the converted snapshot. The `check-change` file `plan.json` is
new in 2.5.0. With `--format promptfoo`, it also records `reader`, `scored_format` and
`tool_version`. See [record 0021](design/0021-v2.5.0-release.md).
