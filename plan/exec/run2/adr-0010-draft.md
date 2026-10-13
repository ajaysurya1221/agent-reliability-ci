# 0010 (DRAFT, not under docs/design until accepted): the imported-session record (memo D2)

Status: draft v3, ACCEPTED as the design for the memo's D2 by Astra (CONSULT run2-D2 round 3,
2026-10-13 18:24Z) after two REVISE rounds; written by the orchestrator (Claude Fable 5.1). Implementation,
the fixture tests and the move to `docs/design/` with a re-freeze are D3 work. Becomes
`docs/design/0010-imported-session-record.md` plus a re-freeze only when accepted and when D3 (the
first importer) is scheduled. No code in this run.

## Problem

The memo's thirty-day plan makes OTLP the "first durable external trace seam" (D3) and wants Claude
and Codex session output consumed through the same model (D5, D6). All of that needs one record
shape for data ARCI did not schedule: a production trace, an exported observability session, a
coding-agent transcript. The memo's constraint (line 109) is absolute: an imported trace "cannot
retrospectively become a valid ARCI gate record", because the gate requires the rule, schedule,
seeds and experiment identity to have been fixed before execution. The record must be useful for
diffing, cohort discovery and manifest drafting, and structurally incapable of being mistaken for
a scheduled trial. Separately, "unsupported or incomplete semantics stay explicit" (D3 acceptance).

## Decision (proposed)

1. **A separate schema id, refused by every evidence loader.** `ImportedSession` is a `Sealed`
   record (reusing `src/arci/schema.py`'s `Sealed`/`record_sha256` and `src/arci/hashing.py`'s
   `canonical_json`/`hash_record`) with `schema_version: Literal["arci-import/0.1"]`, in a new
   module `src/arci/imports/record.py`; `schema.py` (frozen) is not changed. `arci gate`, `arci
   report`, `arci diff` (default mode) and `arci replay` keep requiring `arci/0.5` records and
   refuse `arci-import/*` with one line naming this design record. Shared field names with
   `RecordedCall` are harmless (Astra Q1): the refusal is structural, not by field shape. This
   prevents accidental misuse; it does not authenticate producers (a digest is not provenance
   proof), and the record says so in its docstring.
2. **Provenance, versions and immutability.** `source`: `producer` (free string, e.g.
   `"opentelemetry-python-contrib/openai-v2"`), `producer_version` (the producing software's
   version), `format` (`"otlp-json" | "otlp-protobuf" | "openinference-jsonl" |
   "claude-session-jsonl" | "codex-otlp"`), `format_version` (the spec/schema version the file
   declares or the importer assumed, marked which), `obtained_from` (URL or path as given, never
   rewritten), `original_ids` (trace/session/span ids verbatim). `raw_sha256` covers the raw bytes
   only (Astra Q3); the raw file is stored beside the record. `importer` (`arci` version, importer
   name, importer version, configuration used) and the normalised content are bound by the record
   seal (`record_sha256`), so the parse is reproducible. **The import is a pure function of its
   stated inputs**: `(raw_bytes, importer_configuration, provenance_inputs)` where
   `provenance_inputs` = `{obtained_from, producer, producer_version, imported_at}` are supplied
   explicitly by the caller (the CLI fills `imported_at` from the clock *before* calling the pure
   function and records what it passed). Identical bytes imported with identical inputs seal
   identically; a different `obtained_from` or `imported_at` is a different stated input and
   therefore a different record, by design, and `arci diff --imported` compares records by
   `raw_sha256` + importer when asked whether two records are "the same import". Nothing in the
   record is volatile. The record is deeply immutable: models are frozen (`Model` config), every
   sequence is a tuple, and JSON values are preserved recursively with objects and arrays kept
   distinct (an empty object and an empty array are different values; the canonical JSON used by
   the seal already preserves this), so re-serialising a record reproduces the source structure.
3. **Completeness and capabilities, stated conservatively.** `completeness`: `complete | partial
   | unknown` with a reason. `capabilities` are computed over **all** relevant calls, not any
   (`has_tool_calls`, `has_tool_args`, `has_tool_results`, `has_model_io`, `has_timestamps`,
   `has_outcome`), plus `ordering: "total" | "partial" | "none"`. `total` requires a
   **source-defined, globally comparable execution-order key** on every call (for example start
   timestamps from one clock, or a sequence number the producer documents as execution order); an
   export position or file order is never such a key. `partial` keeps the evidence: `order_edges`
   (pairs of call ids the source orders, e.g. parent-before-child, or same-span sequence) and
   `order_domains` (sets of calls comparable among themselves), and nothing else is claimed. `none`
   means the importer found no order evidence.
   `unsupported`: a list of `{path, reason, source_ref}` for every span/field the importer saw and
   could not map (including attributes of unknown semantic-convention version). Nothing is
   inferred silently.
4. **Calls and events with per-field provenance.** `calls: tuple[ImportedCall, ...]`, each with
   `name`, `args`, `result`, `error_kind`, `started_at`, `ended_at`, and for each field group a
   `Provenance` of `state: "exact" | "inferred" | "missing" | "unsupported"`, `source_ref` (span
   id / line number / attribute path) and, when inferred, `reason`. "missing" (the source has no
   value) is distinct from a JSON `null` result (the source says the result was null).
   `source_outcome` (what the producer reported: success/error) is separate from ARCI's oracle-
   graded outcome and is never written into an `Outcome` field. `ordinal` is the position in the
   source's export order and never implies observed execution order; execution order is only what
   `ordering`, `order_edges` and `order_domains` state.
   `events: tuple[ImportedEvent, ...]` reuse `EventKind` names only where the source states them
   and carry the same `Provenance`; there is no `trial_index`, `seed`, `occurrence`,
   `fingerprint`, manifest reference or verdict anywhere in the record.
5. **What the record is for.** `arci diff --imported`: diff two imported sessions, or an imported
   session against a recorded trial, on the shared call vocabulary (name, order where total, error
   kinds), labelling the imported side "imported, unscheduled". `arci import … --suggest-conditions`:
   proposes faults from observed `error_kind`s. `arci init --from-import <record>`: drafts an
   `arci.yaml` with the observed tool names as the toolset's expected tools and the observed error
   kinds as `--fault` candidates; the draft is a smoke design like any other and seals only when run.
6. **What it is never for.** No verdict, no PASS/BLOCK, no report row, no replay (replay is of the
   boundary's own records, ADR 0002); the loaders refuse it (item 1).

## Consequences

- One importer model for D3–D6: each importer is a pure function `(raw_bytes, importer_configuration,
  provenance_inputs)` → `ImportedSession`, with a versioned fixture test. Fixtures are genuine producer output (an
  instrumentation replaying its own recorded cassettes through a genuine OTLP exporter qualifies;
  hand-written or reconstructed spans do not), pinned by instrumentation, cassette and exporter
  versions, with the capture command and the exported bytes' sha256 in the test (Astra, point 2).
  A producer counts towards D3's "two independent producers" only once its fixture demonstrates
  useful tool identity and order, not generic LLM spans alone.
- Nothing frozen changes for D2 itself: `schema.py`, `interfaces.py`, `hashing.py` are reused.
  `docs/AGENT_SEMANTICS.md` gains an "imported records" section when D3 ships (then re-freeze).
- `docs/TRUST_MODEL.md` unchanged: imported data is untrusted input, treated as data by every
  consumer; the raw digest makes tampering after import detectable, nothing more.

## Not decided here

Which producer's fixtures come first (memo open question 4; candidates in
`plan/exec/run2/fixtures.md`); the protobuf path (D4); any CLI surface beyond
`arci import <file> [--format …] --out <record.json>`.
