Revise D2’s determinism and ordering rules before acceptance.

1. **Resolved:** schema separation and loader refusal; missing/unsupported states with references and inference reasons; conservative all-call capabilities; missing versus JSON null; source-reported versus oracle outcomes; ordinal limitations; raw-byte hashing and sealed importer configuration; separate producer/format versions; imported events without fabricated trial identity.

2. **Purity remains unresolved** ([draft:35–42](/Users/ajay/Developer/agent-reliability-ci/plan/exec/run2/adr-0010-draft.md:35)). Excluding `imported_at` makes the seal stable, not the returned record pure. Supply the timestamp explicitly or attach it outside the pure transformation. Also bind `obtained_from` and other caller-supplied provenance into the stated inputs: identical bytes imported from different paths otherwise produce different seals.

3. **Ordering needs stronger evidence** ([draft:43–58](/Users/ajay/Developer/agent-reliability-ci/plan/exec/run2/adr-0010-draft.md:43)). Monotonic export positions do not establish execution order. Require source-defined, globally comparable execution-order keys for `total`; retain evidenced edges or ordering domains for `partial`. Deep immutability is now required, but specify recursive JSON preservation: tuple encoding must distinguish objects from arrays, including empty ones. These fixes can remain entirely within the new module; no existing frozen-file edit is needed for D2.

4. **D-11’s corrected architecture is sound:** standalone mode, connection-scoped negotiation, tested subsets, pinned trial responses and deferred ADR 0011 address round 1. During ADR 0011, ensure compatibility cannot activate through inherited environment variables; the [server environment currently inherits them](/Users/ajay/Developer/agent-reliability-ci/src/arci/mcp_boundary.py:772).

Read-only: no files changed; no tests or external probes run.

VERDICT D2 draft v2: REVISE  
VERDICT D-11 corrected: AGREE