# S3: MCP reality check (10 November 2026)

Question: does ARCI's existing stdio MCP bridge interoperate with a current MCP client SDK?

**Answer: no.** The official Python SDK `mcp` 2.3.0 cannot list tools from
`arci.mcp_toolset_server` in any of its three connect modes.

## Evidence

```text
$ PYTHONPATH=src <python with mcp 2.3.0> plan/exec/v2/spikes/s3/mcp_client_check.py
mcp SDK 2.3.0
mode=auto FAIL RuntimeError: Unsupported protocol version from the server: 2026-07-28
mode=legacy FAIL RuntimeError: Unsupported protocol version from the server: 2026-07-28
mode=2026-07-28 FAIL ValidationError: 3 validation errors for ListToolsResult
exit: 1
```

Run by the orchestrator. Interpreter: Python 3.13, a separate environment outside the
repository with `mcp==2.3.0`. Server: the recipe world in `examples/recipes/mcp_agent`.

## Cause

Two separate mismatches, both in the bridge's protocol shape, neither in the SDK:

1. **Handshake.** The bridge answers `initialize` with `protocolVersion: "2026-07-28"`
   (`src/arci/mcp_toolset_server.py:20`, `:152-156`). In SDK 2.3.0 that revision is a
   "modern" stateless revision reached through `server/discover`, and the `initialize`
   handshake negotiates only earlier revisions (`mcp/client/session.py:650-667`). So a client
   that handshakes rejects the answer, and the bridge does not implement `server/discover`.
2. **Result shape.** With the revision pinned and the handshake skipped, `tools/list` is
   reached, but the bridge's result fails the SDK's validation for that revision: required
   fields are missing (`cacheScope` and `resultType` among them).

The October finding (decision D-11) was that no SDK supported revision 2026-07-28 yet. That
has changed: the SDK now supports it, and the bridge does not match how the SDK speaks it.

## Consequence for the plan

- No mainstream MCP client can be put behind ARCI's boundary today. This confirms that the
  MCP route is real work, not a configuration change, and stays out of v2.0.
- A second-target decision after launch should price a bridge update (answer
  `server/discover`, emit the revision's required result fields, or negotiate an earlier
  revision on `initialize`) against the Claude Agent SDK adapter.
- Changing the bridge touches `schema.py:276` wording and ADR 0002, so it needs its own
  design record.
- Nothing was changed under `src/`. The boundary process (`arci.mcp_boundary`) was not
  probed separately; it relays the same handshake, so the same failure is expected there.
  That last point is an inference, not a measurement.
