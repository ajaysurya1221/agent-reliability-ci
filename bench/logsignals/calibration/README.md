# Simulation files of the design rounds

The registration (`plan/exec/v2/study/logsignals/PREREGISTRATION.md` on branch `v2/phase0`,
section "Files") lists these eleven files by digest. Five of them are committed here as
copies with one kind of passage withheld: the session counts of single repositories, which
disclosure rule 2 of the registration does not allow in print. Each withheld passage is
marked `[WITHHELD: ...]`. The implementation record beside the registration gives, for every
file, the digest of the original and the digest of the copy here.

The scripts carry a `.txt` suffix so the repository's linter and type checker skip them. The
three round 2 scripts cannot run as they stand, because the withheld list is their input. The
round 3 scripts need a private table (one row per repository) that is not committed; the
implementation record gives its digest and how it is rebuilt from the dataset.

All of it is simulation on made-up data. No file here pairs a real signal with a real outcome.
