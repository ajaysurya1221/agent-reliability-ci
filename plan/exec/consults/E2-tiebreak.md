1: F — Defaulting omitted `task_id` to `experiment_id` matches ADR 0008 while preserving an explicit override for tasks shared across experiments.

2: F — Deriving `<last module segment>.<function>` distinguishes `v1.run` from `v2.run` without requiring explicit labels.

3: F — Preventing silent coercion protects hand-written task values, which `arci init`’s quoting cannot protect.

Implement the descriptor loader with isolated resolver tables and a matching integer constructor: changing only the resolver leaves PyYAML’s leading-zero octal conversion intact. Specify `010 → 10`, `0o10 → 8`, and timestamps as strings. Keep generated strings quoted, document the descriptor’s parsing rules separately from `load_contract`, and test scalar conversions, quoted equivalents, and unchanged global `yaml.safe_load` behavior.