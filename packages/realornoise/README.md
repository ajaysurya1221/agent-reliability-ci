# realornoise

Reads the Claude Code and Codex session logs already on your disk and reports REAL DROP,
NO DROP or CANNOT TELL for recorded measures. Sends nothing. Writes nothing unless asked.
The output holds counts, rates, dates and the names of the model and effort compared.
Runs on Python 3.11 or newer. Compressed Codex logs are read only on Python 3.14;
the output reports how many files were not read. To read compressed logs, run
`uvx --python 3.14 realornoise` (uv fetches that Python if needed).

```sh
uvx realornoise
```

Try the packaged synthetic example without reading your own logs:

```sh
uvx realornoise --example
```

The example prints `RESULT: REAL DROP` and exits with status 1; that is the expected result.
The comparison cannot establish answer quality, a cause, or a change to a model. Tasks,
prompts, projects and client versions may have changed. Repeated checking until a result
appears is not covered by the method's error bounds.

The code lives in [`agent-reliability-ci`](https://github.com/ajaysurya1221/agent-reliability-ci).
This distribution installs its `arci.logs.cli:main` command and pins the matching version of
that package. See the repository for the method, assumptions and other ARCI commands.
