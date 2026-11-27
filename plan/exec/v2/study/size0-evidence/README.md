# Size-0 evidence

- `claims.zip`: the claim folders of all 14 runs as the launcher left them (sealed stores, one
  receipt per trial, both counts, identities, preflight records, the run logs and each run's
  read-only source snapshot), the preflight attempts and the push receipt. Left out: the process
  registry (`groups/`) and the lock file, which the checker does not read.
- `claims.zip.sha256`: its SHA-256.
- `report.txt`: the output of `sh run-size0.sh report` after day 2 (tab-separated).
- `day1.log`, `day2.log`: start and end of every run. `stop.log`: the 23:15 stop check.
  `go-decision.txt`: the timing estimate written before the first trial.

To check it: unpack `claims.zip`, then from `../size-0/` run the study's checker with an
environment that holds released ARCI 2.4.1 and the pins of Run 6:

    python -EsB check_evidence.py . --claims PATH/claims

It prints one line per run and, at the end, `14 finished runs verified`.
