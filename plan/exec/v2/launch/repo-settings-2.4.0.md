# Repository settings for 2.4.0 (the maintainer's to change)

Read on 2026-11-16: the description and topics still describe the product as it was at
2.1.0, and Discussions is off. Nothing here is changed by an agent.

## Description (one line, 232 characters)

```
Did your coding agent get worse, or is it noise? Reads the Claude Code and Codex session logs already on your disk and answers REAL DROP, NO DROP or CANNOT TELL. Also regression testing for AI agents in CI with a stated error bound.
```

Before: "Regression testing for AI agents in CI: compare a candidate with its baseline under
injected tool faults and get PASS, BLOCK or INCONCLUSIVE with a stated error bound."

## Topics

Keep the twelve there now (`ai-agents`, `fault-injection`, `mcp`, `python`, `reliability`,
`statistics`, `evaluation`, `github-actions`, `agent-evaluation`, `langchain`,
`llm-evaluation`, `regression-testing`). Add four: `claude-code`, `codex`,
`coding-agents`, `cli`.

## Discussions

Turn on. The stop rule counts issues or discussions opened by other people, and a
question about a `CANNOT TELL` result fits a discussion better than an issue.

## One command for all three

```bash
gh repo edit ajaysurya1221/agent-reliability-ci --description "Did your coding agent get worse, or is it noise? Reads the Claude Code and Codex session logs already on your disk and answers REAL DROP, NO DROP or CANNOT TELL. Also regression testing for AI agents in CI with a stated error bound." --add-topic claude-code,codex,coding-agents,cli --enable-discussions
```

Or by hand: the gear beside "About" on the repository page (description, topics), and
Settings, General, Features, Discussions.
