# L-CONTRACT: shared rules and module interfaces for `arci logs` (tasks L2 to L10)

Every L brief refers to this file. Read `AGENTS.md` first. The behaviour is specified by two
drafts in the records checkout (read them there; do not copy them into the worktree):

- `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/STATISTICS_LOGS-draft.md` (the contract)
- `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs/0016-logs-draft.md` (decisions, record model, fixed texts)

Log format facts: `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L0-logs-spike.md`.
Spike code you may read and adapt: `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/L0-logs/`
(it predates the review: where it differs from the two drafts, the drafts win).

## Rules for every L task

1. Work only in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs` (branch
   `v2/logs`). Edit only the files your brief says you own. Change no git state. No network.
   No new dependency: standard library, `pydantic`, `pyyaml`.
2. **Never open, list or read anything under `~/.claude` or `~/.codex`.** Develop on synthetic
   logs only. The orchestrator runs real logs.
3. `FROZEN.sha256` files are never edited. If one looks wrong, stop and say so.
4. Decisions use `fractions.Fraction` and integers only. No float decides anything. No random
   number anywhere in `src/arci/logs/`.
5. Nothing read from a log string may reach an output, a warning, an exception message or a
   record, except through the closed lists in `records.py`. Catch per-line faults and count
   them. Never format an exception into user-visible text.
6. `src/arci/logs/` may import only: the standard library, `pydantic`, and from `arci` only
   `arci.hashing`, `arci.html_base`, `arci.outcome_report` (for `escape_terminal`) and
   `arci.__version__`. It opens no socket and starts no process.
7. Code runs on Python 3.11 to 3.14. `compression.zstd` exists only on 3.14: import it lazily.
8. Finish with `.venv/bin/ruff format`, `.venv/bin/ruff check`, `.venv/bin/basedpyright` clean
   on your files (strict), and your tests passing with `.venv/bin/pytest`. Final message:
   files changed, the test command and its last lines, anything you could not do, risks.

## Module interfaces (all under `src/arci/logs/`)

```python
# records.py
Tool = Literal["claude-code", "codex"]
Effort = Literal["minimal", "low", "medium", "high", "xhigh", "max", "other"]
MODEL_WORDS: frozenset[str]            # closed vocabulary of vendor and family words
def render_model(raw: str) -> str | None   # the id as written if every part is a word in
                                           # MODEL_WORDS or a number of at most 8 digits
                                           # (parts split at "-", "." and "_"), else None
def effort_of(raw: object) -> Effort

@dataclass(frozen=True, slots=True)
class Response:
    tool: Tool
    when: datetime          # timezone-aware, UTC
    model: int              # index into ReadResult.models
    effort: Effort
    main_thread: bool
    reasoning: int | None   # non-negative, or None when the log gives none
    version: int            # index of the client version seen (identity only)
    workdir: int            # index of the working directory seen (identity only)
    in_project: bool        # True when no --project was given

@dataclass(frozen=True, slots=True)
class EditResult:
    tool: Tool
    when: datetime
    model: int
    effort: Effort
    main_thread: bool
    failed: bool
    in_project: bool

@dataclass(slots=True)
class ReaderCounters:       # all int, all start at 0
    files_read; files_unread_compressed; files_unreadable; lines; lines_not_json;
    lines_unknown_type; lines_lacking_field; records_in_future; responses;
    responses_without_reasoning; edits_denied; edits_unmatched

@dataclass(frozen=True, slots=True)
class ReadResult:
    tool: Tool
    responses: tuple[Response, ...]
    edits: tuple[EditResult, ...]
    models: tuple[str | None, ...]   # render_model() of each distinct raw id, by index
    counters: ReaderCounters

# discover.py
def claude_root(env: Mapping[str, str], home: Path) -> Path      # $CLAUDE_CONFIG_DIR/projects or ~/.claude/projects
def codex_root(env: Mapping[str, str], home: Path) -> Path       # $CODEX_HOME or ~/.codex
def claude_files(root: Path) -> list[Path]                       # sorted; skips journal.jsonl
def codex_files(root: Path) -> list[Path]                        # sorted; sessions/ and archived_sessions/

# claude_code.py and codex.py, same signature
def read(paths: Sequence[Path], *, project: Path | None, now: datetime) -> ReadResult

# rank_test.py  (values are Fractions oriented so that larger is better)
def p_real(before: Sequence[Fraction], after: Sequence[Fraction]) -> Fraction
def strict_count(moved_before: Sequence[Fraction], after: Sequence[Fraction]) -> int
def g_tail(n: int, m: int, u: int) -> Fraction
def p_none(moved_before: Sequence[Fraction], after: Sequence[Fraction]) -> Fraction
def p_streak(before_in_date_order: Sequence[Fraction]) -> Fraction

# schema.py: the pydantic models of record 0016, "Record model"
# measures.py
def build(result: ReadResult, *, utc_offset: timedelta, since: date | None,
          model: str | None, effort: Effort | None) -> ToolTable   # window, setting, day values, context counts
# decide.py
def decide_tool(table: ToolTable) -> ToolDecision
def exit_code(tools: Sequence[ToolDecision]) -> int
# report.py
def render_text(decision: LogsDecision) -> str
def render_markdown(decision: LogsDecision) -> str
# html.py
def render_html(decision: LogsDecision) -> str
# cli.py
def main(argv: Sequence[str] | None = None) -> int
```

The raw model id, client version and working directory strings live only inside the reader
that parsed them, as dictionary keys used to hand out the integer indexes. They are never
stored on a record and never returned.

Limits that keep the exact tests fast: the before period is 84 days; `--since` may be at most
83 days before the newest day (an earlier date is a usage error), so neither group exceeds 84
days.
