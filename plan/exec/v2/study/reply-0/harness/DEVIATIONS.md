# Reply-0 design corrections, 25 November 2026

- **Answer-only grading.** Exact normalised lines implement the asks. Both a negated key
  and a contact followed by a negated alternative fail. A complete good reply is tested
  on all 72 tasks. Only the two G2-b4 variants legitimately pass the paste test: the
  shipped reply is the single requested branch, with leading spaces. All 16 G1 transcripts
  contain metadata and fail. File selectors identify the requested field or numbered item.
- **F2 parity.** A negative character list admitted minimatch extglobs and the proposed
  server edit admitted question marks. Use one positive full-match expression and sentence
  from tasks.json. Against the pinned filesystem server, 16 openings and 48 later calls
  agreed on complete MCP results. The check used the reference relay transform and an
  isolated edited package; production relay parity remains a separate pre-freeze check.
- **C0 and delivery.** The eight server startups require order_id. At seed zero the original
  lookups match the bridge snapshots. The ledger, ARCI injection and model-facing text
  therefore have distinct expectations. The released plain gate writes a decision without
  a stored-decision comparison (ops review). Use both counts for the plain pair rows.
- **Projection reference.** Astra's 0.047 and 5.96 bounds use the eight-task, 15-round
  design as the reference. Across 32 rate pairs and four sizes the largest differences
  from that design are 0.04619923 in probability and 5.950095 expected pairs (rounded up).
  The maximum suite has seven tasks and 18 rounds, hence 252 trials. The joint-null
  0.125% bound requires a fresh confirmation and a conditional 2.5% bound after selection.
- **Freeze evidence.** The task-level check used a separate output directory so day-one
  tasks/check files retain their original provenance. The new tasks.check.json SHA-256
  is `80aff1c9fb3f14d094e20a17594bda672183bd4c93e071c8802263ea2ba5d64a`.
  Regenerate it in tasks/check before freezing. Both reference-server feeder inputs were
  byte-identical to day one. The ordered offline check keeps fresh task evidence under
  its own output directory and passes that directory to the suite audits.

- **Receipt identity.** ARCI 2.4.1 exposes workdir, task file and seed. Its command
  expander has no trial-ID or scheduled-arm placeholder. The descriptors put the side
  in REPLY0_ARCI_ARM for the receipt only. Join (descriptor run, key_id, seed, side)
  to the released schedule. This also distinguishes identical clean commands.
- **C0 seeds.** The draft says all orders share one amount per round. The released
  per_round scheduler derives a seed from both cell index and round. Compiling an
  eight-order C0 descriptor and enumerating round one gave eight distinct seeds.
  Each *pair* shares a seed. Grade and verify each task's actual seeded order total.
- **G1 optional timestamp.** MCP accepts an explicit JSON null. The shipped Python
  handler receives None for both null and omission. Treat arg_present as a non-null
  value. An empty log selected by end_timestamp alone, with or without a null
  start_timestamp, passes through on both paths. The check exercises both cases.
- **Local rehearsal transport.** In this workspace a Unix-domain bind returned EPERM.
  The released runner produced two harness_error envelopes on the offline C0 pair.
  REPLY0_CHECK_TRANSPORT=stdio routes the checker's agent through the released serial
  boundary handlers using anonymous pipes. It keeps their fault and recording logic
  and exercises the actual relay, servers and stand-ins. The default matrix and the
  default C0 check still use arci run. A component recording supplies no sealed-run
  evidence. The package rehearsal staged fresh copies under the study workspace.


- **Offline proof of push.** Run 6b cloned the remote, which requires a network and
  writes Git state. Reply-0 reads the named branch's origin tracking ref and requires
  an ancestor recorded by a push or fetch in its local reflog. It compares the
  registration, digest list and each study input with the blobs at that commit.
  The descriptor note uses the same check and must postdate the clean row. This is
  evidence of publication at the recorded time. A missing reflog prevents launch.
- **Complete freeze list.** Both the launcher and make_digests.py now use the
  launch preflight's input inventory. It includes the fixture manifest, probe,
  order desk, checker feeders, registration, diffs, and every harness and task input.
  Generate this list again in the neutral checkout after the registration is filled.
- **One generic comparison.** The registration names one shown-only follow-up
  without assigning its model and cell. After the measured runs, use the first
  eligible main statistical BLOCK with valid reading conditions in this fixed order:
  F1 4B, F1 12B, G1 4B, F2 4B, G1 12B, F2 12B. With no such BLOCK, use the first
  retained set in that order with five or more tasks. The ordinary time limit applies.
  Prepared descriptors are possible assignments. Only the selected slot may start.
- **Wiring evidence and interruption.** Independent model slots write each response
  before the next send. A locked merge preserves both models' evidence in wiring.json.
  A failed non-empty check requires its saved output, a revised agent and a revised
  registration in the single pushed amendment. A run claim survives process exit.
  An OS file lock distinguishes an active suite from an interrupted, consumed attempt.
  Interrupted confirmation cannot block publication of the other measured cells.
- **F1 edited-package path.** The interface and blind counter specify
  `F1/package/dist/index.js`. The builder and operating audit previously accepted
  `F1/server-filesystem/dist/index.js`. For F1-d1 trial `F1:00000:baseline`,
  the ledger showed read_text_file, list_directory and read_text_file, with zero
  relay rewrites. Its answer, `steel bracket`, matches the registered key. The
  candidate gave up. The hand count is one minus pair. Count A had the right grade
  but accepted the wrong launch path. Count B correctly rejected the launch.
  The filesystem builder, descriptor and audit now require the documented path.
  A fresh sealed held-out pair yields one minus pair in both independent counts.
- **Sealed offline rehearsal transport.** Native ARCI returned two harness errors
  with `Operation not permitted` before the C0 agent could run here. The dedicated
  offline runner uses two local FIFOs and the released boundary's serial request,
  reply, fault, recording and framing methods. ARCI 2.4.1 launches the actual
  agents and graders, seals the envelopes, orders pairs, stops and writes the stores.
  Section 12.4 uses the task checker's sealed-pair assertions for all 432 trials.
  The adapter changes the client transport and uses a study-local temporary
  directory. It requires stand-ins in both commands. The released gate is run
  separately on disk. This check covers serial stand-in delivery; the native Unix
  listener and nonblocking socket loop still need a socket-capable host.
  Run `REPLY0_NO_SANDBOX=1 sh harness/check-offline.sh` under network denial.
  Set `REPLY0_REHEARSAL_TRANSPORT=native` to select the original transport.

## Round 3 decisions

| Finding | Decision and evidence |
|---|---|
| 1. Missing opening fault | Repinned the independent checker output from the fixture. The default PATH selected an installer shim which failed during server initialization. The offline checker resolves the installed Node binary by its registered digest before launching servers. All 72 rows carry the raw reply. A simulated different failure and a predicate-matching ENOENT for the wrong path must both fail. Confirmation checks the edit derived from that pinned shipped reply. C0 keeps its original lookup, injection and delivery checks. |
| 2. Transport mutation | The HTTP writer captures the body at send time. The stand-in returns a digest of its own input. A changed body between capture and receipt by the stand-in yields a digest mismatch even when the saved request is internally consistent. |
| 3. Grade | Recompute the released contract's violations using the verified tool events, and grade the answer against the registered key. A terminal response missing string content leaves an incomplete receipt and exits 75. Tests cover an invented hard violation and the intact malformed reply. |
| 4. Count A | Count A runs the shared delivery and grading audit before tallying. The same resealed histories must be rejected by both entry points. Only the subsequent tally and stopping-round count comparison are Count A's own calculations. |
| 5. Confirmation | Admission hashes `F1/package`, the builder's actual output. The admission test accepts a built package and rejects a changed handler. |
| 6. Wiring and C0 | A timeout, unrelated client rejection or server error supplies insufficient evidence for the fallback. Only an explicit empty-text rejection selects it. The registration now follows the released schedule. Each order's pair shares a seed and is graded from its own order total. |
| 7. One live start | A study-wide lock covers all models and phases. The canonical durable claim survives interruption. Each live trial send validates the launch capability, active claim, input digests and scheduled identity. The remote receipt pins the registration commit independently of the checkout. Competition, stale claim, wrong seed and changed input tests exercise these checks. |
| 8. Deadlines | Admission waits at most 30 seconds. Audit and both count subprocess groups each have 1,800 seconds. A real sleeping subprocess leaves its partial output and consumed claim on expiry. |
| 9. Privacy | Require the neutral checkout and environment for a live start. Scan escaped JSON strings, nested or encoded payloads and the operator's runtime identifiers before assembling the publication. Synthetic identifier tests verify rejection and byte preservation. |

### Integration evidence

- A physical copy of the Python environment alone left the checkout, plan, edited
  package and Node paths in offline descriptors. Stand-in descriptors now use the
  harness modules on the configured Python path and resolve study inputs relative to
  the study root. The neutral rehearsal stages a byte-identical pinned Node binary
  in its own evidence directory. The run logger renders ARCI's exact store-location
  announcement relative to the study. Other CLI output is preserved. The HOME scan
  covers retained artifacts and the FIFO matrix stores before their temporary cleanup.
- Count B rejected the synthetic F2-n1 baseline with `missing receiver digest`:
  its final answer matched the registered key and there was no contract violation.
  Only the stand-in emits the receiver echo. Count B now requires the echo on successful
  stand-in exchanges and verifies the captured sender bytes for live-format responses.
  A changed echo or sender digest still invalidates the count.
- The agent checks admission before it opens MCP or creates a receipt, and again at
  each live HTTP send. The direct-descriptor regression runs both generated commands
  through the released CLI with a ready-only test boundary and an instrumented endpoint.

## Round 4 decisions

1. The three checks cover faults in the harness, tool servers, transport and model
   backend. Deliberate operator modification and resealing of stored evidence are
   outside their threat model. The snapshot records whether the answer file exists,
   including a written null answer. ARCI 2.4.1 exposes a parent-observed exit-zero
   flag, wall time, tool usage, failure diagnostic and fingerprint. Audit checks these
   against the exchange history. Each arm lists supported infrastructure, crash and
   timeout diagnostics observed with a written answer, retaining their runner outcomes.
2. Each successful non-streaming exchange must name the requested model and set
   `done` to true. The receipt preserves the raw reply and its `done_reason`.
   A terminal length limit leaves the grade intact and contributes to the arm's
   `terminal_length` count. The stand-in supplies the same protocol fields.
3. A finished claim pins the complete export inventory. Assembly hashes each staged
   file before publication. A consumed, unfinished claim gets a staged `partial.json`.
4. Text exports and base64 payloads in MCP blobs, data and explicit base64 fields
   must decode as inspectable UTF-8. Publication uses the operator identifiers
   obtained at runtime. Kept tests include malformed base64, UTF-16 and a nested blob.
5. Claim creation precedes all metadata traffic. The launcher consumes each metadata,
   warm-up and wiring ordinal under the active suite and claim locks, with the pushed
   registration, model and exact request bytes checked before opening the connection.
6. One live suite holds the lock across models and phases. Its durable record names
   the launcher and process groups. The released runner creates new sessions for
   agents, boundaries and graders. A study wrapper registers each group before exec,
   under the same lock used to clear the record. A surviving member keeps its group
   active after launcher death. The interrupted claim remains consumed.
7. The shared environment supplies the filesystem server interpreter at
   `$ENV/node/bin/node`. The descriptor builder, reference launch and version check
   use that absolute executable, whose measured SHA-256 is pinned in ENVIRONMENT.md.
8. The initial pushed-blob comparison, Git preflight commands, executable version
   probes and fixture Git checks have a 15-second subprocess deadline each.
