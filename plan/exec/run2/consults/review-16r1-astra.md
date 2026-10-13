Tighten the stderr guard and qualify the errno changelog claim.

1. [ci.yml:250](/Users/ajay/Developer/.arci-worktrees/wt-t16/.github/workflows/ci.yml:250): matching stderr correctly fails. Existing BLOCK, byte-equality, output, and exit assertions prevent empty-summary vacuity. However, the new guard silently accepts `grep` errors, including a missing report. Require exit **1** specifically for absence; reject other statuses.

2. **Bash reasoning is correct:** read-only probes confirmed `! grep` continues under `-e`, whereas `if grep …; then exit 1; fi` stops on a match.

3. [CHANGELOG.md:7](/Users/ajay/Developer/.arci-worktrees/wt-t16/CHANGELOG.md:7): exclude **EEXIST** alongside unsupported links. `init.py:673–674` retains the dedicated “exists; use --force” message without errno. The remaining changelog claims match the code. README words are unchanged.

No files changed; full filesystem/hosted CI checks were not rerun.

VERDICT 16r1: REVISE