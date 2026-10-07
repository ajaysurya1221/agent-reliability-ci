# Security policy

## Reporting a vulnerability

Report suspected vulnerabilities privately through GitHub's private vulnerability reporting:
[open a draft security advisory](https://github.com/ajaysurya1221/agent-reliability-ci/security/advisories/new)
(the repository's **Security** tab, then **Report a vulnerability**). Please do not open a public
issue or pull request for a suspected vulnerability.

Include the affected commit or tag, the command you ran, what you expected and what happened.
A minimal synthetic reproducer (a small manifest, toolset and agent) is the most useful
attachment.

**Do not attach private run stores, replay bundles or credentials.** A run store or bundle can
hold an agent's full task state and, for decision calls, full request state. Never include API
keys, tokens or `.env` files; redact them from logs and describe the shape of the data instead.

This is a single-maintainer project. Reports are read and handled on a best-effort basis; no
response time is promised. Fixes are made on `main`.

## What the tool trusts

The scope of what `arci` defends against is set by the frozen
[trust model](docs/TRUST_MODEL.md). In short:

- **Trusted code.** The harness, the manifest author, the toolset (environment) and the oracle are
  trusted. The agent under test is assumed to be your own code: buggy, flaky or crash-prone, but
  not hostile.
- **Not a sandbox.** Command agents run behind a harness-owned MCP boundary, which is isolation
  from accident, not containment. Anything an agent does outside the tool boundary (files,
  network, subprocesses) is not observed.
- **Replay executes embedded code.** A replay bundle embeds code, and replaying it runs that code.
  Bundle hashes are integrity checks, not signatures. Replay bundles only from sources you trust.

Behaviour that the trust model already lists as outside its guarantees, such as a deliberately
hostile agent forging or bypassing its own record, or code running when an untrusted bundle is
replayed, is a documented limit rather than a vulnerability. A way to break a guarantee the trust
model does make (for example, a real API key reaching the agent process or a sealed record, or a
bundle payload escaping its temporary directory) is in scope.
