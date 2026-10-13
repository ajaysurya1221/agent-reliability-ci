# E2 ruling (tie-break consult, plan/exec/consults/E2-tiebreak.md) — binding for TASK 03

1. `task_id` is OPTIONAL and defaults to `experiment_id` (explicit value still allowed).
2. A bare-string arm `app.v1:run` gets label `<last module segment>.<function>` → `v1.run`.
3. YAML loading uses a SafeLoader subclass with ISOLATED resolver tables (do not touch the global
   `yaml.SafeLoader` and leave `contracts.load_contract` unchanged): booleans only for `true|false`;
   integers only decimal (`010` → 10, no leading-zero octal), `0x`, `0o` (`0o10` → 8), `0b`, with a
   matching integer constructor; timestamps stay strings. Tests must cover: `yes`/`no`/`on`/`off`
   stay strings, `010` → 10, `0o10` → 8, a quoted `"true"` stays a string, a date-like scalar stays a
   string, and that the global `yaml.safe_load` behaviour is unchanged. Document the descriptor's
   parsing rules in docs/DESCRIPTOR.md separately from load_contract.
