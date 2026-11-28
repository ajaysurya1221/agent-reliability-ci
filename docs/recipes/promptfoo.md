# Compare two versions with promptfoo

The reader was tested with JSON exports from promptfoo 0.125.1 and 0.126.0.
Both versions ran word checks with a scripted provider, with and without repeats.
In 0.126.0, the scripted provider tested exports containing two prompts or two
providers. Separate runs used a local HTTP server to check cache behavior.
See the [0.125.1 fixture notes](../../tests/unit/outcomes/real/README.md)
and [0.126.0 fixture notes](../../tests/unit/integrations/real/README.md).

## Use a run you already have

Start with promptfoo's JSON export. A cell is one prompt paired with one
provider. Write one new JSONL file per cell. If you have a separate export
for each version, convert them like this.

```sh
arci convert --from promptfoo old.json --out old.jsonl
arci convert --from promptfoo new.json --out new.jsonl
```

If both prompts are in one export, select each by its `promptIdx`.
Use this pair of commands in place of the pair above.

```sh
arci convert --from promptfoo prompts.json --prompt 0 --out old.jsonl
arci convert --from promptfoo prompts.json --prompt 1 --out new.jsonl
```

If the versions are providers labelled `old` and `new`, use their labels instead.
You can combine `--prompt` and `--provider` when it takes both to select one cell.

```sh
arci convert --from promptfoo providers.json --provider old --out old.jsonl
arci convert --from promptfoo providers.json --provider new --out new.jsonl
```

Use the old version's file to build the task list in `rule.yaml`, then compare
the two versions. Each repeat in a saved export counts as one round. If your
export contains more rounds than the default cap, set `--max-rounds` to cover
them. For 200 tasks repeated three times, the default cap is two. Add
`--max-rounds 3` to the `arci verdict-rule` command below.

```sh
arci verdict-rule --tasks old.jsonl --out rule.yaml
arci verdict rule.yaml --baseline old.jsonl --candidate new.jsonl
```

This is a descriptive verdict. The rule was written after the results existed,
so the statistical error bound does not apply. ARCI refuses exports that report
cache hits. If the cache was on and the file shows no hits, conversion succeeds
with a notice.

ARCI pairs tasks by id. The id starts with up to 80 characters of the
description (or `test` for a missing or empty description). After a space and
`#` come 16 leading hex digits of a SHA-256 hash. ARCI hashes a JSON object
with two keys, `description` and `vars`, using sorted keys and no extra spaces.
It uses the full description and all variables. A missing description is
`null` and missing variables are `{}`. Changing the description or a variable
changes the id, including a variable inherited from `defaultTest.vars`.
A variable that refers to a file contains its full `file://` path. Moving the
file can change the id even when its contents stay the same. Keep the same
inputs on both sides and give each task a distinct description or set of variables.

## Compare fresh runs

Put one prompt and one provider in each config. Use the same tasks and
assertions in both. Run this beside `old.yaml` and `new.yaml`.

```sh
arci check-change --format promptfoo \
  --baseline 'promptfoo eval -c old.yaml --no-cache --no-table --no-progress-bar --no-share -o {out}' \
  --candidate 'promptfoo eval -c new.yaml --no-cache --no-table --no-progress-bar --no-share -o {out}' \
  --out-dir promptfoo-comparison
```

Turn the cache off with `--no-cache`. The environment variable
`PROMPTFOO_CACHE_ENABLED=false` does not show up as a disabled cache in the
export. ARCI requires the file to record `runtimeOptions.cache` as false.
Leave repeats off. Each file covers one round for one side. ARCI schedules
the rounds and refuses a file with repeats.

ARCI accepts promptfoo exit statuses 0 and 100 and still checks the file.
Exit status 1 stops the comparison with ERROR. ARCI also refuses a file
reporting an HTTP status from 400 to 599, since promptfoo can save a partial
run after a server error. An assertion that throws counts as a failure.
If the judge breaks inside an assertion, the verdict counts that as a worse
answer. If your setup can detect that fault, have the command exit 1 to stop
the comparison.

With repeats, promptfoo's `results.repeatStability` reports per-test pass-rate
ranges. MLflow also has a paired comparison, `mlflow.genai.compare_evaluations`.
ARCI lets you choose a margin of allowed loss before fresh paired runs. It
registers the rule, launches both versions and checks the evidence after each
round. At the round limit it can say “cannot tell” (`INCONCLUSIVE`). See
[check-change](check-change.md) for the conditions behind the error bound.
