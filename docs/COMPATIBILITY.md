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
