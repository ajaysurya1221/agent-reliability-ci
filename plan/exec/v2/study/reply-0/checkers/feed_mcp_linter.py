"""Feed recorded reply texts to mcp-linter 1.2.0 rule P4 without a server, a model or a network.

NOT YET RUN (written on 25 Nov 2026, day 1 of Reply-0; syntax-checked only).

Usage (network denied):

    sandbox-exec -p '(version 1)(allow default)(deny network*)' \
      env PYTHONDONTWRITEBYTECODE=1 python3 -I -B feed_mcp_linter.py \
      <unpacked mcp-linter wheel dir> <replies.json>

mcp-linter has no command that grades a saved reply: P4 runs only inside
`mcp-lint run` against a live server. This script builds the same record the
live run builds (mcp_lint/probe.py, ProbeResult) and calls the package's own
grader, mcp_lint.rules.probe.error_issues. Those modules import only the
standard library, so the MCP SDK is not needed.

How each input field maps to what the live run records:

- is_error true          -> status "tool_error"  (probe.py:85)
- is_error false/missing -> status "ok"          (probe.py:85)
- protocol_error true    -> status "protocol_error", text taken from the
                            exception message (probe.py:104-110, 45-48)
- bad_call "unknown_value" -> may_succeed True   (fixtures.py:237)
- expect_error false     -> P4 does not look at the reply at all
                            (rules/probe.py:186); reported as "not_graded"
"""

from __future__ import annotations

import json
import sys

USAGE = "usage: python3 -I -B feed_mcp_linter.py <unpacked mcp-linter wheel dir> <replies.json>"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(USAGE, file=sys.stderr)
        return 2
    sys.path.insert(0, argv[1])
    from mcp_lint import __version__
    from mcp_lint.probe import ProbeResult
    from mcp_lint.rules.probe import _P4_KINDS, error_issues

    with open(argv[2], encoding="utf-8") as fh:
        data = json.load(fh)

    out = []
    for reply in data["replies"]:
        text = reply.get("text") or ""
        expect_error = bool(reply.get("expect_error", True))
        if reply.get("protocol_error"):
            status, reason, body = "protocol_error", "MCPError: " + text, ""
        else:
            status, reason, body = ("tool_error" if reply.get("is_error") else "ok"), None, text
        probe = ProbeResult(
            tool=reply["tool"],
            label=reply.get("bad_call", ""),
            args=reply.get("args") or {},
            expect_error=expect_error,
            status=status,
            reason=reason,
            text=body,
            structured=reply.get("structured"),
            target=reply.get("target"),
            auto=True,
            may_succeed=reply.get("bad_call") == "unknown_value",
        )
        row = {"id": reply.get("id"), "checker": f"mcp-linter {__version__} P4", "status": status}
        if not expect_error:
            row.update(verdict="not_graded", issues=[],
                       note="P4 grades only replies to calls that were meant to fail")
        else:
            issues = error_issues(probe)
            severities = [_P4_KINDS[kind][0].value for kind in issues]
            worst = "warning" if "warning" in severities else ("info" if severities else None)
            row.update(
                verdict="pass" if not issues else "flagged",
                worst_severity=worst,
                issues=[{"kind": kind, "severity": sev, "meaning": _P4_KINDS[kind][1]}
                        for kind, sev in zip(issues, severities)],
            )
        out.append(row)

    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
