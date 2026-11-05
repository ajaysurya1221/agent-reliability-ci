# Independent agent first-use protocol

Product commit: cb2ab9e. Two fresh non-author readers use the same installed
v0.9.0 candidate wheel from a clean directory with PYTHONPATH cleared. The recipe,
CLI help and cases.json are their only task context. They may use the CLI on the
supplied stores but must not parse JSONL, inspect implementation, import the
package directly, execute recorded agents or use network. They may hash input
files without displaying contents. This is agent QA, not human adoption.

For each case, record start/end UTC, elapsed seconds, exact commands and exits,
observed operation or containing-event difference, gate interpretation, and what
cannot be concluded. Target five minutes per diagnosis once stores are available.
The repeat case provides an explicit candidate ID. Readers must not infer that
first-difference output proves benignness, root cause or later equivalence.

Each reader owns only its report and command-log paths. Retain failures,
assistance and mistakes. The recipe describes the generic retry example, so this
is not a blinded study. No runtime help or answer key is supplied by the author.
Integrator verifies receipts and all pre/post source hashes independently.
