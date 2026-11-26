# Board-0 harness

Board-0 compares the first request after a correct order or calendar lookup. The stock-sentence arm receives exactly `The lookup returned no data. Repeat the same call with the same arguments.` The empty-as-given arm receives an empty string. Both arms see the same two desk tools. The model sees the registered ask and system prompt from `tasks/tasks.json`. Temperature is 0.7, streaming and reasoning are off. The request sends neither a sampling seed nor a context override. Pin and run admission check the tag's configured 32768 context and the loaded model's digest and context.

## Preparation and live execution

Use a neutral checkout with the operator-owned environment at `$BOARD0_ENV/py`. It must contain released ARCI 2.4.1. The neutral checkout and the single host-wide claims directory must be accessible to the operator. Verify the registration and the five-slot `models.json` before preparing either day. The registry has the shape `{"ollama":"0.32.14","slots":[...]}`. Its rows follow M1 through M5 in slot order. Every pin and clean or measured admission checks the running server version and records it in the pin or suite audit. Each model has a distinct tag and lowercase 64-hex installed digest, a family and a size string. The two-slot example is exclusively for the FIFO rehearsal.

From the study directory:

```sh
"$BOARD0_ENV/py/bin/python" -B tasks/make_tasks.py
sh harness/run-board0.sh list
sh harness/run-board0.sh prepare
sh harness/run-board0.sh digests > board0-digests.sha256
```

Prepare scans each distinct clean and measured scenario for both days and writes the scalar matches to `scenario-collisions.json`. The scan visits the physical target record once, includes numeric components of identifiers such as SKUs, and preserves every scenario. The source list includes that report and the five registered projection files. Prepare writes each descriptor once and freezes the complete descriptor digest list for both dates. Changing any pinned input requires operator review before the study starts. Push the registered sources, inputs, both digest lists and descriptors to the registration branch `v2/phase0`. Supply the remote's commit receipt as a single line `<40-hex-commit> refs/heads/v2/phase0` in `/private/var/tmp/arci-board0-claims/push-receipt.txt`. The launcher hashes each local file and each corresponding Git blob against the digest lists at that commit and checks ancestry against the local origin tracking ref. These checks are offline.

```sh
sh harness/run-board0.sh check
sh harness/run-board0.sh real board0-pin-M1
sh harness/run-board0.sh real board0-d1-M1-clean
sh harness/run-board0.sh real board0-d1-M1-E
sh harness/run-board0.sh report
sh harness/run-board0.sh assemble OUTPUT_DIRECTORY
sh harness/run-board0.sh pack OUTPUT.zip
python3 harness/check_evidence.py OUTPUT.zip OUTPUT.zip.sha256
```

Use `list` for all canonical run names. Complete the pins first. For each of 20 scored probes the model receives a pebble ID, calls the toy reader with that ID, and answers in text. A fresh random token first appears in the tool result. The pin requires at least 16 passing answers under the string rule below, with no decoys. Two additional probes deliver an empty tool result after a scripted reader call. The pin verifies the outgoing empty string and a completed HTTP 200 response for both. Any completed assistant response suffices for these two delivery checks. The pin records the exchanges, elapsed seconds and peak memory per probe. Peak memory is null when unavailable. Claims are exclusive and permanent across interruption. The live lock covers metadata, pin probes, trials, grading and audit. Trial requests must belong to the active claim's frozen schedule. Day 1 runs ascending slots, day 2 descending. Each day starts with that slot's clean suite. Local dates come from the launcher clock. A model qualifies separately each day when six distinct tasks in each family pass either clean trial. Every measured run retains all 16 tasks.

## Boundary and grade

The release exposes one MCP server per suite. The relay selects the desk from the scheduled task, unwraps its task payload and runs the released stdio bridge with an explicit two-tool allowlist. The world receives only a seed and task payload. The relay records the seed, desk and bridge source hashes, advertised tools, ordered calls, arguments and complete original responses. Each family has exactly one opening tool. The single E condition targets occurrence zero of each family's opening tool. Only one of those tools exists in any given trial. The clean row uses 16 released plain-pair descriptors without faults. The measured descriptor uses up to 26 rounds of 16 pairs, for 416 pairs and 832 trials. The released gate uses alpha 1/20, margin 1/10, stakes 1/4 and 1/2, threshold 40 in both directions, per-round seeds and four tolerated errored pairs.

The agent supplies a scripted assistant tool call and its tool message before requesting its first model response. Only the baseline replaces the blank opening. Subsequent tools execute in response order. The first assistant message with no native tool calls ends the trial. Its content is the final text. Messages with calls can carry prose, which is ignored for grading. The released boundary rejects an unknown name before charging it (src/arci/mcp_boundary.py lines 1519–1521 in this checkout, lines 1587–1589 in release 2.4.1). A known tool that returns an application error consumes a call. The limits are 12 charged calls including the opening, eight chat requests, 120 seconds for the trial and 20 seconds for grading. A final text can arrive after the twelfth charged call or on the eighth request. Empty text, exhaustion without a final message, and timeout score FAIL. A malformed backend response is an infrastructure error verified against exit 75.

The oracle takes the typed key from the seeded world. Every scalar value of the key's type that differs from the key is a decoy. The scan follows dictionary values and list elements at every depth in the snapshot, skipping dictionary keys. Boolean values are excluded for integer keys. The grader removes all occurrences of the row's order or event ID from the text. For integers it extracts tokens with `(?<![\d.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?![\d]|[.,]\d)` and compares their numeric values after removing commas. For strings it scans case-sensitively from left to right, taking the longest nonoverlapping candidate at each position with a non-alphanumeric character or text edge on both sides. A trial passes when the key matches and no decoy matches.

The report shows `retrieved` for trials where a later lookup returned the target record after a blank opening. It also shows `exact`, the count whose original final text equals the canonical key after trimming outer whitespace and removing one trailing period. Only the primary grade enters the clean rating and the measured verdict.

## Evidence

On a native host, run `sh harness/tests/native-rehearsal.sh` from the study directory with port 11434 free. The rehearsal serves deterministic fake Ollama replies on loopback, pushes its copied inputs to a local bare remote, and sets `BOARD0_CLAIMS` to a fresh temporary claims directory. The production entry point `run-board0.sh` unsets this variable before starting Python. The rehearsal uses the released interpreter under `$BOARD0_ENV/py` (default environment `/Users/Shared/arci-reply0/env`), native Unix sockets and the relay's nested sandbox. It checks five pins and two complete model-days on day 1. A failed rehearsal prints the step and keeps its directory for inspection.

Elapsed seconds sum the complete clean and measured invocations for that slot and day, from monotonic claim creation through evidence verification and export. The audit checks tool event times and agent completion relative to the released runner deadline. Each run exports the descriptor, four ARCI files, sent-byte receipts, ledgers keyed by trial ID, audit and both counts, and the run log. Receipts join on run, task ID, seed and scheduled arm. Each exchange has the exact request bytes in base64, their SHA-256, status and exact response bytes. Count A uses the audited reconstructed conversation. Count B reads the exported receipts and sealed recordings separately. Both retain all scheduled trials through the stopping round. The independent archive verifier reconstructs both seeded worlds and grades the terminal text from response bytes. Run it from a trusted copy with the released `arci` on PATH. The SHA-256 sidecar should arrive through a trusted channel.

`check-offline.sh` uses the repository interpreter and the existing release in the shared Reply-0 environment by default. Set `BOARD0_ENV` to select another matching environment. It copies the inputs into a temporary directory, runs the released scheduler, boundary handlers, runner, oracle and gate with FIFOs, uses two artificial dates and two example slots, and verifies accepted and altered archives. The verifier's explicit `--rehearsal` mode requires two slots and offline commands. Its default mode requires five live slots. The rehearsal uses `BOARD0_NO_SANDBOX=1` inside the enclosing sandbox. Live servers use nested network denial unless the operator sets that switch inside an already isolated environment.

