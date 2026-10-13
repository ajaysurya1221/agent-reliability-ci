Accept v3 as the design for D2.

1. **Purity resolved:** item 2 explicitly includes caller-supplied provenance and `imported_at` among the transformation’s inputs, binds `obtained_from`, and places clock access outside the pure function.
2. **Ordering resolved:** items 3–4 require source-defined, globally comparable execution-order keys for `total`, preserve evidenced edges/domains for `partial`, and prevent export ordinals from implying execution order. Item 2 explicitly preserves objects versus arrays recursively, including empty values.
3. **No design blockers.** Nonblocking editorial cleanup: [line 87](/Users/ajay/Developer/agent-reliability-ci/plan/exec/run2/adr-0010-draft.md:87) should include `provenance_inputs` in its abbreviated function signature to match item 2.

Schema separation and loader refusal retain D2’s anti-masquerading boundary. Implementation verification and frozen-file re-freezing remain D3 work.

Read-only: no files changed; no tests run.

VERDICT D2 draft v3: ACCEPT