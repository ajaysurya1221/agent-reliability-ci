# 0010 (DRAFT, not under docs/design until accepted): the imported-session record (memo D2)

Status: draft written by the orchestrator (Claude Fable 5.1) in run 2, 2026-10-13; for Astra review
(CONSULT run2-D2). Becomes `docs/design/0010-imported-session-record.md` plus a re-freeze only when
accepted and when D3 (the first importer) is scheduled. No code in this run.

## Problem

The memo's thirty-day plan makes OTLP the "first durable external trace seam" (D3) and wants Claude
and Codex session output consumed through the same model (D5, D6). All of that needs one record
shape for data ARCI did not schedule: a production trace, an exported observability session, a
coding-agent transcript. The memo's constraint (line 109) is absolute: an imported trace "cannot
retrospectively become a valid ARCI gate record", because the gate requires the rule, schedule,
seeds and experiment identity to have been fixed before execution. The record must therefore be
useful for diffing, cohort discovery and manifest drafting, and structurally incapable of being
mistaken for a scheduled trial.

## Decision (proposed)

1. **A new, separate schema id.** `ImportedSession` is a `Sealed` record (reusing
   `src/arci/schema.py`'s `Sealed`/`record_sha256` mechanism and `src/arci/hashing.py`'s
   `canonical_json`/`hash_record`) with `schema_version: Literal["arci-import/0.1"]`. It lives in a
   new module, `src/arci/imports/record.py`; `schema.py` (frozen) is not changed. Every loader of
   gate evidence (`arci gate`, `arci report`, `arci diff`, `arci replay`) keeps requiring
   `arci/0.5` records, so an imported record is rejected by construction, not by a flag.
2. **Provenance is mandatory and immutable.** Fields: `source` (`producer`: free string such as
   `"opentelemetry-python-contrib/openai-v2"`, `"langfuse"`, `"phoenix"`, `"claude-code"`;
   `format`: `"otlp-json" | "otlp-protobuf" | "openinference-jsonl" | "claude-session-jsonl" |
   "codex-otlp"`; `format_version`: the producer's or spec's version string; `obtained_from`: URL or
   path as given, never rewritten), `original_ids` (trace/session/span ids exactly as in the
   source), `raw_sha256` (digest of the raw bytes before any parsing; the raw file is kept beside
   the record), `imported_at` (ISO 8601) and `importer` (`arci` version + importer name/version).
3. **Completeness and capability flags are explicit.** `completeness`: `complete | partial |
   unknown` with a free-text reason; `capabilities`: booleans the analysis code checks before
   offering a feature: `has_tool_calls`, `has_tool_order`, `has_tool_args`, `has_tool_results`,
   `has_outcome`, `has_timestamps`, `has_model_io`. An importer that cannot establish a capability
   sets it false and lists the span/field it could not map under `unsupported` (a list of
   `{path, reason}`), so "unsupported or incomplete semantics stay explicit" (memo D3 acceptance).
4. **Calls reuse the boundary's vocabulary without its guarantees.** `calls` is a list of
   `ImportedCall` records shaped like `RecordedCall` (tool name, args, result or error kind,
   ordinal, timestamps) plus `confidence: "exact" | "inferred"` per field group; there is no
   `fingerprint`, no `seed`, no `occurrence` counter and no `trial_index`, because none were
   produced by ARCI's schedule. `events` reuses `Event` kinds only where the source states them;
   anything inferred is tagged.
5. **What the record is for.** `arci diff` gains an `--imported` mode in D3 that diffs two imported
   sessions or an imported session against a recorded trial on the shared call vocabulary
   (name, order, error kinds), labelling the imported side "imported, unscheduled". Cohort
   discovery (`arci import … --suggest-conditions`) proposes faults from observed error kinds.
   `arci init --from-import <record>` drafts an `arci.yaml` with the observed tool names as the
   toolset's expected tools and the observed fault kinds as `--fault` candidates; the draft is a
   smoke design like any other and seals only when run.
6. **What it is never for.** No verdict, no PASS/BLOCK, no report row, no replay (replay is of the
   boundary's own records, ADR 0002). `arci gate` and `arci report` refuse `arci-import/*`
   records with a one-line error that names this design record.

## Consequences

- One importer model for D3–D6; each importer is a pure function raw bytes → `ImportedSession`
  with a versioned fixture test, as the memo requires ("authentic versioned fixtures from at least
  two independent producers" for D3). Fixture provenance (URL, version, sha256) is recorded in the
  test file; no fixture is hand-written.
- Nothing frozen changes for D2 itself: `schema.py`, `interfaces.py`, `hashing.py` are reused, not
  edited. The record kind is additive. `docs/AGENT_SEMANTICS.md` gains a section only when D3
  ships (then re-freeze).
- The trust model (`docs/TRUST_MODEL.md`) is unchanged: imported data is untrusted input and is
  treated as data by every consumer; the raw file's digest makes tampering after import detectable,
  nothing more.

## Not decided here

Which producer's fixtures come first (memo open question 4: Claude vs Codex; the OTLP pair is
chosen in `plan/exec/run2/fixtures.md`); the protobuf path (D4) waits for JSON semantics; any
CLI surface beyond `arci import <file> --out <record.json>`.

## Review questions for Astra

1. Does a separate schema id plus loader refusal satisfy "cannot masquerade as a scheduled ARCI
   trial", or must the record also omit every field name shared with `RecordedCall`?
2. Is `confidence` per field group enough, or should inferred values be stored separately from
   exact ones?
3. Should `raw_sha256` cover the raw bytes only, or the raw bytes plus the importer version, to pin
   reproducibility of the parse?
