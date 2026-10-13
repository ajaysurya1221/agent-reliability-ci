# TTFV receipts

One JSON file per reader per track, filled in by hand from
[../receipt.template.json](../receipt.template.json) following
[../ttfv-protocol.md](../ttfv-protocol.md). ARCI collects no telemetry; this directory is the
only place these measurements live.

- **Naming:** `YYYY-MM-DD-<handle>-<track>.json`, where `<track>` is `demo` or `own-agent` and the
  date is the day of the attempt.
- **Failures are kept.** An attempt that stalled, errored, was abandoned or was coached is
  committed like a successful one, with what went wrong in `failures` or `coaching_events`.
  Receipts are never edited after merge except to fix a transcription error, stated in the PR.
- **No personal data** beyond a public handle. No names, emails, hostnames, usernames in paths or
  machine serials; trim paths in pasted errors to the part after your project directory.
- **Contributing:** fork, add your file here, open a PR titled `receipt: <handle> <track>`. The
  maintainer checks the file parses and follows the template; it is merged whatever it shows.
- **Maintainer and AI-agent receipts** set `reader.kind` to `maintainer` or `ai-agent`. They are
  kept and reported separately and never counted as cold readers.
