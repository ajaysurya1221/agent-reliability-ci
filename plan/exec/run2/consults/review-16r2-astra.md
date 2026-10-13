Both fixes are resolved at `dfdb11f`.

1. The `&& … || …` list safely captures grep’s status under `bash -e`. Only status 1 passes; matches and errors explicitly fail. Executing the extracted guard with `bash -eo pipefail` confirmed clean input passes, while leaks and missing files fail; simulated statuses 0/1/2/127 also passed expectations.
2. CHANGELOG now correctly excludes existing files (`EEXIST` → `FileExistsError`) and unsupported links, matching `src/arci/init.py`.

No files changed. Verification covered this delta; full CI was not rerun.

VERDICT 16r2: ACCEPT