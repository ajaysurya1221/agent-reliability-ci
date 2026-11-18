**Prepare 2.4.1 from the reviewed main commit, with explicit limitations.**

1. **Release: now, through the documented preparation and release gates. I agree with your leaning.**  
   **Version: 2.4.1.** [COMPATIBILITY.md:77](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/docs/COMPATIBILITY.md:77): “Existing commands and records retain their meaning.”

   The document gives no explicit patch/minor classification rule; choosing patch is judgment. Correcting snapshot publication changes observed results without redefining their meaning. Cleanup remains inside the existing deadline: [AGENT_SEMANTICS.md:84](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/docs/AGENT_SEMANTICS.md:84) says it “runs through process exit.” Longer cleanup and occasional timeout therefore do not themselves require 2.5.0.

2. **No inspected frozen sentence requires immediate server killing.** I searched shutdown, killing, deadlines, snapshots and determinism across `AGENT_SEMANTICS.md`, `TRUST_MODEL.md` and `docs/design/`, then inspected the relevant passages against the implementation.

   However, existing implementation gaps remain against these promises:
   
   - [AGENT_SEMANTICS.md:211](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/docs/AGENT_SEMANTICS.md:211): “Determinism: for a scripted client the envelope must be identical across runs.” The mitigation does not establish this for timing-sensitive snapshot publication.
   - [0017-logs-2.md:562](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/docs/design/0017-logs-2.md:562): “the run goes on, F24 says so, and the exit code is the one of the result.” The late unreadable-table path omits that notice.

   These are residual implementation nonconformances, not newly discovered requirements to preserve immediate killing. A release record must not silently weaken the frozen promises.

3. **Dropped write: ship with a prominent note.** [cli.py:400](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/src/arci/logs/cli.py:400) removes the table output when the locked read is unreadable; the already-rendered report still describes the initial read.

   This predates the patch, preserves the unreadable file, and is narrower than the race being fixed. A rushed fix is hazardous: merely adding F24 can falsely say previously used rows were unused; changing the exit to 3 needs reconciliation with record 0017’s continue-with-result rule. State that `--keep` can silently skip saving and that subsequent log deletion can make missed captures unrecoverable.

4. **The design record must state:**
   
   - Exact release scope, patch rationale, authorized re-freeze paths and unchanged dependency resolutions.
   - Atomic replacement, preservation of the previous snapshot on failure, and the unchanged frozen fixture.
   - Idle predicate, EOF/half-budget SIGTERM/three-quarter SIGKILL, unchanged parent deadline and latch precedence.
   - Possible snapshot/hash changes, extra latency, timeout, unrecorded late effects, and remaining determinism and kept-write gaps.
   - Plugin instruction/permission changes, version-triggered updates and publication ordering.

5. **Additional checks and overlooked risks.** Before tagging, verify the tag’s target is the approved release commit on main: the workflow guard checks versions, not ancestry or approval. Review the upstream publishing-action change and preferably rehearse its attestation path on TestPyPI; green ordinary CI does not execute production publishing.

   I found no definite workflow defect. The new publishing pin at [release.yml:243](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/.github/workflows/release.yml:243) remains unverified here. Approval delays or failed publishing can extend the unavailable-pin window beyond minutes. Directory review may retain the old plugin snapshot; a version bump alone does not establish review or update propagation. Shutdown stages are unrecorded, so retain the runtime version alongside experimental evidence.

Files changed: **none**. Tests: **not run**. Frozen checksum check passed; last line: `uv.lock: OK`. Hosted CI and test totals remain supplied evidence.

Next: draft the release record with these explicit exceptions.