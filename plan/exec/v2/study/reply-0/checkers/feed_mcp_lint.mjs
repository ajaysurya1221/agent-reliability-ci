// Feed recorded reply texts to mcp-lint 1.0.4 "recover" without a server, a model or a network.
//
// NOT YET RUN (written on 25 Nov 2026, day 1 of Reply-0; syntax-checked only).
//
// Usage (network denied):
//   sandbox-exec -p '(version 1)(allow default)(deny network*)' \
//     node feed_mcp_lint.mjs <unpacked mcp-lint package dir> <replies.json>
//
// It imports only dist/recover/score.js from the package. That file imports only
// dist/recover/types.js, so none of the package's dependencies are needed.
//
// For each reply it does what the package's live probe does (dist/recover/probe.js:35-51):
// trim the text, let the package's own classifyFailure() pick the failure kind, then score.
// A reply may carry its own "kind" to override the classifier; the output says which was used.
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [packageDir, inputPath] = process.argv.slice(2);
if (!packageDir || !inputPath) {
  process.stderr.write('usage: node feed_mcp_lint.mjs <unpacked mcp-lint package dir> <replies.json>\n');
  process.exit(2);
}

const score = await import(pathToFileURL(resolve(packageDir, 'dist/recover/score.js')).href);
const input = JSON.parse(await readFile(inputPath, 'utf8'));
const hangMs = input.hang_ms ?? 15000;
const out = [];

for (const reply of input.replies) {
  const message = (reply.text ?? '').trim();
  // The live probe sets isError true for a protocol error and otherwise passes the
  // result's own flag through, which is undefined when the server left it out.
  const isError = reply.protocol_error ? true : (reply.is_error ?? undefined);
  const durationMs = reply.duration_ms ?? 0;
  const classified = score.classifyFailure({ message, isError, durationMs, hangMs, timedOut: false });
  const kind = reply.kind ?? classified;
  const report = score.scoreRecovery(
    [{ id: reply.id, tool: reply.tool, kind, message, isError, durationMs }],
    { hangMs, tools: input.tools },
  );
  out.push({
    id: reply.id,
    checker: 'mcp-lint@1.0.4 recover',
    kind,
    kind_source: reply.kind ? 'given in the input' : 'classifyFailure',
    kind_by_classifier: classified,
    verdict: report.errors === 0 ? 'recoverable' : 'not_recoverable',
    errors: report.errors,
    warnings: report.warnings,
    findings: report.findings.map((f) => ({ rule: f.ruleId, severity: f.severity, message: f.message })),
  });
}

process.stdout.write(JSON.stringify(out, null, 2) + '\n');
