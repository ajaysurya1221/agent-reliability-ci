"""Verbatim qualifications and text reports for imported outcomes."""

from __future__ import annotations

import re
import string
import unicodedata

from arci.outcome_schema import OutcomeDecision

# Terminal layout, separate from the statistical statements and notices.
TERMINAL_TASK_HEADING = "Tasks where the candidate did worse or a pair errored, through round {k}"
TERMINAL_TASK_OVERFLOW = (
    "{n} more such tasks: add --markdown PATH or --json PATH for the full table"
)

# Single source for ADR 0015 fixed text, including all validation reasons.
FIXED_TEXT: dict[str, str] = {
    "F1": (
        "Descriptive verdict: the rule file declares it was written after outcomes existed. The "
        "error bound is not claimed."
    ),
    "F2": (
        "Imported outcomes: ARCI did not run these trials. No fault injection, fault "
        "accounting, tool outcomes or replay."
    ),
    "F3": (
        "The error bound depends on six conditions ARCI cannot check: (a) the rule and its task "
        "list were fixed before either evaluated arm ran, which the author declares in the rule "
        "file; (b) outcomes are independent across tasks and rounds, with no response cache "
        "shared across pairs or rounds; (c) each task behaves the same in every round; (d) "
        "pairing and logical round order were fixed before outcomes were observed, and no "
        "registered round was omitted or replaced; (e) infrastructure failures are labelled "
        "error, not fail; (f) the protocol was fixed before execution and both arms were graded "
        "by the same criterion."
    ),
    "F4": (
        "ARCI checked the rule, the file structure of every input, the task ids against the "
        "rule, and that both arms cover rounds 1 to <k>. It did not verify execution or any of "
        "those conditions."
    ),
    "F5": (
        "Under (a) to (f) and the assumptions of docs/STATISTICS_SUITE.md, a wrong PASS and a "
        "wrong BLOCK each have probability at most alpha/2."
    ),
    "F6": (
        "at alpha = <alpha>, a wrong PASS and a wrong BLOCK each have probability at most <bound>"
    ),
    "F7": ("<k> of <N> registered rounds supplied"),
    "F8": (
        "if every further pair is a non-errored tie, PASS is reached after <r> more complete "
        "rounds (<p> more pairs)"
    ),
    "F9": (
        "if every further pair is a non-errored tie, PASS is not reached inside the registered "
        "rounds"
    ),
    "F10": ("<n> rounds after the stopping round were excluded from inference"),
    "F11": ("errored pairs through round <k>"),
    "F12": ("rounds were assigned from the order of the files given"),
    "F13": (
        "task ids were extracted from the given files. This does not establish that the rule "
        "preceded the data. Fix the rule before either evaluated arm is run."
    ),
    "F14": (
        "the packaged example's rule was written from the study's stored outcomes, so it "
        "declares fixed_before_runs: false; the study's own suite rule was registered before "
        "its run."
    ),
    "F15": ("PASS threshold crossed"),
    "F16": ("BLOCK threshold crossed"),
    "E1": ("unknown task id: <id>"),
    "E2": ("duplicate outcome for <arm> <id> round <n>"),
    "E3": ("round <n> is outside 1 to <max_rounds>"),
    "E4": ("rounds are not contiguous from 1"),
    "E5": ("arms supply different rounds: baseline <rounds>, candidate <rounds>"),
    "E6": ("unreadable or unsupported input: <path>"),
    "E7": (
        ".eval files are not read: run inspect log dump FILE.eval > FILE.json and pass the JSON"
    ),
    "E8": ("<path> has no recognised extension: use --format"),
    "E9": ("<arm> supplies more than one Inspect log"),
    "E10": ("outcome <value> for <id> cannot be read as pass, fail or error"),
    "E11": ("<path> reports more than one scorer and the rule sets no score"),
    "E12": ("the rule's score <name> is absent from <path>"),
    "E13": ("task id <id> appears as both an integer and a string"),
    "E14": ("<path> gives round on some rows and not others"),
    "E15": ("the rule file is not a valid arci-outcomes/1 rule: <reason>"),
    "E16": ("no input files were given for <arm>"),
    "E17": ("<path> is both an output and an input, or is named twice"),
    "E18": ("the directory for <path> does not exist"),
    "E19": ("cannot write <path>"),
    "E20": ("<option> was given more than once"),
    "E21": ("--example takes no other input"),
    "E22": ("--out already exists: <path>"),
    "E23": ("the previous decision was made under another rule: <digest>"),
    "E24": ("the previous decision is not a usable arci-outcomes/1 decision: <reason>"),
    "E25": ("the previous decision is an ERROR decision: <path>"),
    "E26": ("the previous decision supplied <k> rounds; this call supplies <j>"),
    "E27": ("the previous decision used normalisation <v>; this call uses <w>"),
    "E28": ("round <n> differs from the previous decision"),
    "E29": ("a test case has an empty classname or name: <path>"),
    "W1": ("max_rounds below 3: few looks"),
}


def text(tag: str, **values: object) -> str:
    """Substitute ADR placeholders without rewording any fixed text.

    E5 uses the same placeholder twice; its callers supply ``baseline`` and
    ``candidate`` for the two round lists.
    """
    arms = iter(("baseline", "candidate"))

    def substitute(match: re.Match[str]) -> str:
        name = match[1]
        if tag == "E5" and name == "rounds":
            name = next(arms)
        if name not in values:
            return match[0]
        # POSIX paths may contain surrogateescape code points. Diagnostics must
        # remain valid UTF-8 so even an unreadable path can produce a sealed ERROR.
        return str(values[name]).encode("utf-8", errors="backslashreplace").decode("utf-8")

    # A single pass does not interpret placeholder-like characters in opaque ids.
    return re.sub(r"<([A-Za-z0-9_]+)>", substitute, FIXED_TEXT[tag])


def _reason(reason: str, descriptive: bool) -> str:
    if descriptive:
        if reason == "non-inferiority established":
            return text("F15")
        if reason == "regression established":
            return text("F16")
    return reason


def escape_terminal(value: str) -> str:
    """Render opaque text visibly, without terminal controls or ambiguous escapes."""
    result: list[str] = []
    for char in value:
        if char == "\\":
            result.append("\\\\")
        elif unicodedata.category(char).startswith("C") or char in "\u2028\u2029":
            code = ord(char)
            result.append(
                f"\\x{code:02x}"
                if code <= 0xFF
                else f"\\u{code:04x}"
                if code <= 0xFFFF
                else f"\\U{code:08x}"
            )
        else:
            result.append(char)
    return "".join(result)


def _escape(value: str, *, markdown: bool) -> str:
    safe = escape_terminal(value)
    if markdown:
        safe = "".join("\\" + char if char in string.punctuation else char for char in safe)
    return safe


def _message(value: str, *, markdown: bool) -> str:
    """Keep fixed prose verbatim; escape only opaque diagnostic placeholders.

    Records store rendered reasons, so recover their fixed template at the display
    boundary. Captured values are never interpreted again as templates or markup.
    """
    if not markdown:
        return escape_terminal(value)
    for tag, template in FIXED_TEXT.items():
        parts = re.split(r"<[A-Za-z0-9_]+>", template)
        if len(parts) == 1:
            if value == template:
                return value
            continue
        # Standing notices interpolate generated integers/rationals, never raw text.
        placeholder = "(.*?)" if tag.startswith("E") else r"([0-9]+(?:/[0-9]+)?)"
        match = re.fullmatch(placeholder.join(re.escape(part) for part in parts), value, re.DOTALL)
        if match is not None:
            if not tag.startswith("E"):
                return value
            return parts[0] + "".join(
                _escape(group, markdown=True) + part
                for group, part in zip(match.groups(), parts[1:], strict=True)
            )
    if value in {
        "non-inferiority established",
        "regression established",
        "no test crossed",
        "both tests crossed",
        "errored pairs exceed max_errored_pairs",
    }:
        return value
    return _escape(value, markdown=True)


def _lines(decision: OutcomeDecision, *, markdown: bool) -> list[str]:
    descriptive = decision.rule is not None and not decision.rule.fixed_before_runs
    lines = [text("F1")] if descriptive else []
    lines.append(f"VERDICT: {decision.verdict.value} (exit {decision.exit_code})")
    lines.append("")
    lines.extend(
        _message(_reason(reason, descriptive), markdown=markdown) for reason in decision.reasons
    )
    if not markdown:
        for notice in decision.notices:
            lines.extend(("", _message(notice, markdown=False)))
    if decision.rule_sha256 is not None:
        lines.extend(("", f"Rule SHA-256: {decision.rule_sha256}"))
    if decision.history:
        lines.append("")
        header = (
            "Round | Pairs | Minus | Zero | Plus | Errored | PASS wealth | BLOCK wealth | "
            "PASS crossed | BLOCK crossed | Verdict"
        )
        lines.append(f"| {header} |")
        if markdown:
            lines.append("| " + " | ".join(["---"] * 11) + " |")
        for look in decision.history:
            counts = look.counts
            row = (
                f"{look.round} | {look.pairs} | {counts.minus} | {counts.zero} | "
                f"{counts.plus} | {counts.errored} | {look.pass_wealth} | "
                f"{look.block_wealth} | {look.pass_crossed} | {look.block_crossed} | "
                f"{look.verdict.value}"
            )
            lines.append(f"| {row} |")
        lines.extend(
            (
                "",
                f"{text('F11', k=decision.last_round_evaluated)}: "
                f"{decision.history[-1].counts.errored}",
            )
        )
    tasks = decision.tasks
    omitted = 0
    if not markdown:
        qualifying = sorted(
            (task for task in tasks if task.counts.minus > 0 or task.counts.errored > 0),
            key=lambda task: (-task.counts.minus, -task.counts.errored, task.task_id),
        )
        tasks = tuple(qualifying[:10])
        omitted = len(qualifying) - len(tasks)
    if tasks or not markdown:
        heading = (
            "Task counts through round " + str(decision.last_round_evaluated)
            if markdown
            else TERMINAL_TASK_HEADING.format(k=decision.last_round_evaluated)
        )
        lines.extend(("", heading))
        if markdown:
            lines.append("")
        if tasks:
            header = (
                "Task | Pairs | Baseline successes | Candidate successes | "
                "Minus | Zero | Plus | Errored"
            )
            lines.append(f"| {header} |")
            if markdown:
                lines.append("| " + " | ".join(["---"] * 8) + " |")
        else:
            lines.append("none")
        for task in tasks:
            counts = task.counts
            task_id = _escape(task.task_id, markdown=markdown)
            row = (
                f"{task_id} | {task.pairs} | {task.baseline_successes} | "
                f"{task.candidate_successes} | {counts.minus} | {counts.zero} | "
                f"{counts.plus} | {counts.errored}"
            )
            lines.append(f"| {row} |")
        if markdown and tasks:
            lines.append("")
        if omitted:
            lines.append(TERMINAL_TASK_OVERFLOW.format(n=omitted))
    for statement in decision.statements:
        if descriptive and statement == text("F1"):
            continue
        lines.extend(("", _message(statement, markdown=markdown)))
    if markdown:
        for notice in decision.notices:
            lines.extend(("", _message(notice, markdown=True)))
    return lines


def render_terminal(decision: OutcomeDecision) -> str:
    """Render a complete report, with descriptive status before its verdict."""
    return "\n".join(_lines(decision, markdown=False)) + "\n"


def render_markdown(decision: OutcomeDecision) -> str:
    """Render the same evidence and verbatim qualifications as Markdown."""
    return "\n".join(_lines(decision, markdown=True)) + "\n"
