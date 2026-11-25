"""Reply-0: write tasks.json, the registered tasks of every cell (study code, stdlib only).

    python3 -B make_tasks.py            # writes tasks.json next to this file

No model, no server, no network. Every task is written out from the small tables below, so the
whole set can be read here in one place. `{FX}` stands for the fixture directory and is filled
in by whoever reads tasks.json (check_tasks.py now, the harness later).

A cell is one reply of one server. Each cell has
  server            filesystem | git | orderdesk
  kind              the bad-call kind of the probe (missing_required, bad_enum, unknown_value),
                    or injected_empty for the control
  role              eligible for (b), with only F1 eligible for (c,d) | descriptive | control
  reply_pattern     a regular expression the server's reply to the bad call must match
  reply_is_error    the isError flag the server sends with that reply
  sentence          the baseline arm's text; {arg:NAME} is an argument of the bad call,
                    {parent:NAME} the directory part of that argument. Nothing else goes in:
                    no file content, no fixture fact, nothing from the task
  sentence_when     when the sentence replaces a reply, besides the tool, reply_pattern and
                    reply_is_error: `arg_present` (these arguments were sent) and
                    `arg_matches` (argument -> regular expression). It replaces EVERY reply
                    of the trial that fits, as an edit in the server itself would
  main, held_out    lists of tasks
and each task has
  id                also repeated as key_id (ARCI strips `id` before the agent sees the task)
  ask               the one sentence the model is given
  bad               the scripted first call: {"name", "arguments"}
  good              the calls that lead to the answer, in order (the last reply holds it)
  expect            exact answer lines, one for a scalar
  decoys            competing values or other facts in the source
  source            how expect is recomputed from the fixture without any MCP server
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from file_keys import SELECTORS, file_key  # noqa: E402

FIXTURE = Path("/Users/Shared/arci-reply0/fx")
FILES = "{FX}/files"
REPO = "{FX}/repo"

SYSTEM_PROMPT = (
    "You answer questions by using the tools you are given. Call a tool when you need "
    "information. Never invent a tool result. When you know the answer, reply with the "
    "answer only."
)
GENERIC_SENTENCE = (
    "The previous tool call did not return a usable result. Check its arguments against the "
    "tool descriptions and make a corrected call."
)
CONTROL_SENTENCE = (
    "lookup_order returned an empty result. Call lookup_order again with the same order_id."
)

# id, file, question, expect, decoys, wrong file name (F1), bare search pattern (F2)
FACTS: dict[str, list[tuple[str, str, str, list[str], list[str], str, str]]] = {
    "notes": [
        ("n1", "notes/todo.txt", "What is the second item on the to-do list?",
         ["Renew the fire certificate before 30 April"],
         ["Order packing tape", "Count the stock in bay 7"], "todo-list.txt", "todo"),
        ("n2", "notes/todo.txt", "What is the third item on the to-do list?",
         ["Count the stock in bay 7"],
         ["Order packing tape", "Renew the fire certificate"], "to-do.txt", "todo.txt"),
        ("n3", "notes/contacts.txt", "Who on the contact list works in transport?",
         ["Bram de Wit"], ["Asha Verma", "Chidi Okeke", "Dana Lind"], "contacts.csv", "contact"),
        ("n4", "notes/contacts.txt", "Who on the contact list works in accounts?",
         ["Chidi Okeke"], ["Asha Verma", "Bram de Wit", "Dana Lind"],
         "contact-list.txt", "contacts.txt"),
        ("n5", "notes/meeting-2026-01-05.txt",
         "What is the reference of the lorry booked at the meeting of 5 January 2026?",
         ["LRY-4417"], ["Present:", "Decision:"],
         "meeting-2026-01-05.md", "meeting-2026-01-05"),
        ("n6", "notes/meeting-2026-01-12.txt",
         "Who was asked to update the price list at the meeting of 12 January 2026?",
         ["Dana"], ["Present:", "Decision:"],
         "meeting-01-12.txt", "meeting-2026-01-12.txt"),
        ("n7", "notes/glossary.md", "What does the glossary say a pick list is?",
         ["the items to collect for one order"],
         ["a numbered storage area", "the code of one product"], "glossary.txt", "glossary"),
        ("n8", "notes/glossary.md", "What does the glossary say a bay is?",
         ["a numbered storage area"],
         ["the code of one product", "the items to collect for one order"],
         "glossary.markdown", "glossary.md"),
    ],
    "data": [
        ("d1", "data/prices.csv", "Which product has the code SKU-1003 in the price list?",
         ["steel bracket"], ["oak shelf", "pine shelf", "wall plug"], "price-list.csv", "price"),
        ("d2", "data/prices.csv", "Which product has the code SKU-1002 in the price list?",
         ["pine shelf"], ["oak shelf", "steel bracket", "wall plug"], "prices.txt", "prices.csv"),
        ("d3", "data/orders.csv", "What is the status of order ORD-503?",
         ["waiting for stock"], ["shipped", "packed"], "order-list.csv", "order"),
        ("d4", "data/orders.csv", "What is the status of order ORD-502?",
         ["packed"], ["shipped", "waiting for stock"], "orders.txt", "orders.csv"),
        ("d5", "data/suppliers.txt", "Which supplier sells brackets and plugs?",
         ["Fastfix"], ["Norden Timber"], "supplier-list.txt", "supplier"),
        ("d6", "data/suppliers.txt", "Which supplier sells oak and pine?",
         ["Norden Timber"], ["Fastfix"], "suppliers.csv", "suppliers.txt"),
        ("d7", "data/config.json", "Which currency does the configuration file name?",
         ["EUR"], ["Larch Street", "open_days"], "config.yaml", "config"),
        ("d8", "data/stock.csv", "How many of SKU-1003 are in stock?",
         ["260"], ["14", "0", "35"], "stock.txt", "stock.csv"),
    ],
}  # fmt: skip

MESSAGES = [
    "Add the price list",
    "Add the total calculator",
    "Add brackets and wall plugs to the price list",
    "Round totals to whole cents",
    "Raise the oak shelf to 135",
]
# id, the date in words, ISO form (the good call), compact form (the bad call), commits expected.
# No date is the date of a commit: git reads a bare date as that day at the present time of day.
DATES: dict[str, list[tuple[str, str, str, str, int]]] = {
    "main": [
        ("g1", "7 January 2026", "2026-01-07", "20260107", 3),
        ("g2", "9 January 2026", "2026-01-09", "20260109", 3),
        ("g3", "11 January 2026", "2026-01-11", "20260111", 3),
        ("g4", "15 January 2026", "2026-01-15", "20260115", 2),
        ("g5", "25 January 2026", "2026-01-25", "20260125", 2),
        ("g6", "1 February 2026", "2026-02-01", "20260201", 2),
        ("g7", "10 February 2026", "2026-02-10", "20260210", 1),
        ("g8", "20 February 2026", "2026-02-20", "20260220", 1),
    ],
    "held_out": [
        ("h1", "8 January 2026", "2026-01-08", "20260108", 3),
        ("h2", "10 January 2026", "2026-01-10", "20260110", 3),
        ("h3", "14 January 2026", "2026-01-14", "20260114", 2),
        ("h4", "20 January 2026", "2026-01-20", "20260120", 2),
        ("h5", "30 January 2026", "2026-01-30", "20260130", 2),
        ("h6", "5 February 2026", "2026-02-05", "20260205", 1),
        ("h7", "15 February 2026", "2026-02-15", "20260215", 1),
        ("h8", "25 February 2026", "2026-02-25", "20260225", 1),
    ],
}

C1 = "0b956b19a23106abe9fdf3d48ef021b56dd1b33a"
C3 = "25018bef76af977432b507d764ac7f5123fa9752"
C4 = "911021e1ef1ae2a50fbf18ce67fb7fdd84aadce2"
# id, question, extra arguments, expect, decoys
BRANCH_ASKS: list[tuple[str, str, dict[str, str], list[str], list[str]]] = [
    ("b1", "Which local branches does the git repository at {REPO} have?",
     {}, ["main", "release-1"], []),
    ("b2", "Which local branches of the git repository at {REPO} contain commit " + C1 + "?",
     {"contains": C1}, ["main", "release-1"], []),
    ("b3", "Which local branches of the git repository at {REPO} contain commit " + C3 + "?",
     {"contains": C3}, ["main", "release-1"], []),
    ("b4", "Which local branch of the git repository at {REPO} does not contain commit "
     + C4 + "?", {"not_contains": C4}, ["release-1"], ["main"]),
]  # fmt: skip
BAD_BRANCH_TYPES = ("everything", "both")
ORDERS = ("ORD-103", "ORD-106", "ORD-109", "ORD-112", "ORD-115", "ORD-118", "ORD-121", "ORD-124")

Task = dict[str, Any]


def call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"name": name, "arguments": arguments}


def task(tid: str, ask: str, bad: Any, good: list[Any], expect: list[str], decoys: list[str],
         source: dict[str, Any]) -> Task:  # fmt: skip
    return {"id": tid, "key_id": tid, "ask": ask, "bad": bad, "good": good, "expect": expect,
            "decoys": decoys, "source": source}  # fmt: skip


def file_tasks(cell: str, group: str) -> list[Task]:
    out: list[Task] = []
    for fid, rel, question, expect, decoys, wrong, pattern in FACTS[group]:
        path = f"{FILES}/{rel}"
        folder = path.rsplit("/", 1)[0]
        read = call("read_text_file", path=path)
        selector = SELECTORS[fid]
        source = {"kind": "file_field", "path": f"files/{rel}", "selector": selector}
        key = file_key(FIXTURE / "files" / rel, selector)
        if [key] != expect:
            raise ValueError(f"{fid}: fixture selector disagrees with the registered answer")
        if cell == "F0":
            ask = f"The file {path} answers this question: {question} Reply with the answer only."
            bad, good = call("read_text_file", head=20), [read]
        elif cell == "F1":
            ask = (f"One of the files in the folder {folder} answers this question: {question} "
                   "Reply with the answer only.")  # fmt: skip
            bad = call("read_text_file", path=f"{folder}/{wrong}")
            good = [call("list_directory", path=folder), read]
        else:
            ask = (f"A file somewhere under {FILES} answers this question: {question} "
                   "Reply with the answer only.")  # fmt: skip
            bad = call("search_files", path=FILES, pattern=pattern)
            good = [call("search_files", path=FILES, pattern=f"**/*{pattern}*"), read]
        out.append(task(f"{cell}-{fid}", ask, bad, good, [key], decoys, source))
    return out


def date_tasks(group: str) -> list[Task]:
    out: list[Task] = []
    for gid, words, iso, compact, count in DATES[group]:
        ask = (f"Which commits in the git repository at {REPO} were made on or after {words}? "
               "Reply with their commit messages only, one per line.")  # fmt: skip
        expect, decoys = MESSAGES[-count:], MESSAGES[:-count]
        out.append(task(
            f"G1-{gid}", ask,
            call("git_log", repo_path=REPO, start_timestamp=compact),
            [call("git_log", repo_path=REPO, start_timestamp=iso)],
            expect, decoys,
            {"kind": "git_lines", "args": ["log", f"--since={iso}", "--format=%s", "main"]},
        ))  # fmt: skip
    return out


def branch_tasks() -> list[Task]:
    out: list[Task] = []
    for bad_type in BAD_BRANCH_TYPES:
        for bid, question, extra, expect, decoys in BRANCH_ASKS:
            flag = [f"--{k.replace('_', '-').replace('not-', 'no-')}={v}" for k, v in extra.items()]
            ask = question.replace("{REPO}", REPO)
            ask += " Reply with the branch names only, one per line."
            out.append(task(
                f"G2-{bid}-{bad_type}",
                ask,
                call("git_branch", repo_path=REPO, branch_type=bad_type, **extra),
                [call("git_branch", repo_path=REPO, branch_type="local", **extra)],
                expect, decoys,
                {"kind": "git_lines", "args": ["branch", "--format=%(refname:short)", *flag]},
            ))  # fmt: skip
    return out


def control_tasks() -> list[Task]:
    out: list[Task] = []
    for index, order in enumerate(ORDERS, start=1):
        lookup = call("lookup_order", order_id=order)
        t = task(f"C0-c{index}",
                 f"How many cents were paid in total for order {order}? "
                 "Reply with the number only.",
                 lookup, [lookup], [], [],
                 {"kind": "world_state", "field": "order.total_cents"})  # fmt: skip
        t["order_id"] = order
        out.append(t)
    return out


def document() -> dict[str, Any]:
    cells: dict[str, Any] = {
        "C0": {
            "server": "orderdesk", "kind": "injected_empty", "role": "control",
            "tool": "lookup_order",
            "fault": {"name": "empty_result", "tool": "lookup_order", "occurrence": 0},
            "reply_as_given": "",
            "sentence": CONTROL_SENTENCE,
            "sentence_applied_by": "agent",
            "main": control_tasks(), "held_out": [],
        },
        "G1": {
            "server": "git", "kind": "unknown_value", "role": "eligible", "tool": "git_log",
            "reply_pattern": r"^Commit history:\n?$", "reply_is_error": False,
            "sentence": ('No commit matched start_timestamp "{arg:start_timestamp}". If that is '
                         "meant as a date, write it as YYYY-MM-DD (for example 2024-01-15) and "
                         "call git_log again with the same repo_path."),
            "sentence_applied_by": "relay",
            "sentence_when": {"arg_present": ["start_timestamp"]},
            "main": date_tasks("main"), "held_out": date_tasks("held_out"),
        },
        "F2": {
            "server": "filesystem", "kind": "unknown_value", "role": "eligible",
            "tool": "search_files",
            "reply_pattern": r"^No matches found$", "reply_is_error": False,
            "sentence": ('No entry matched the pattern "{arg:pattern}". A pattern with no '
                         "wildcard matches only an entry whose path below the given path is "
                         "exactly that text. Call search_files again with the same path and "
                         'the pattern "**/*{arg:pattern}*".'),
            "sentence_applied_by": "relay",
            "sentence_when": {"arg_matches": {"pattern": r"^[A-Za-z0-9._-]+$"}},
            "main": file_tasks("F2", "notes"), "held_out": file_tasks("F2", "data"),
        },
        "F1": {
            "server": "filesystem", "kind": "unknown_value", "role": "eligible",
            "tool": "read_text_file",
            "reply_pattern": r"^ENOENT: no such file or directory, ", "reply_is_error": True,
            "sentence": ("There is no file at {arg:path}. Call list_directory with path "
                         '"{parent:path}" to see the files that exist, then call '
                         "read_text_file with the full path of the right one."),
            "sentence_applied_by": "relay",
            "main": file_tasks("F1", "notes"), "held_out": file_tasks("F1", "data"),
        },
        "F0": {
            "server": "filesystem", "kind": "missing_required", "role": "descriptive",
            "tool": "read_text_file",
            "reply_pattern": (r"^Input validation error: Invalid arguments for tool "
                              r"read_text_file: path: Invalid input: expected string, "
                              r"received undefined$"),
            "reply_is_error": True,
            "sentence": ('read_text_file needs the argument "path". Call read_text_file again '
                         "with path set to the full path of the file."),
            "sentence_applied_by": "relay",
            "main": file_tasks("F0", "notes"), "held_out": [],
        },
        "G2": {
            "server": "git", "kind": "bad_enum", "role": "descriptive", "tool": "git_branch",
            "reply_pattern": r"^Error executing tool git_branch: Invalid branch type: ",
            "reply_is_error": True,
            "sentence": ('branch_type "{arg:branch_type}" is not allowed. The allowed values are '
                         '"local", "remote" and "all". Call git_branch again with the same other '
                         "arguments and branch_type set to one of them."),
            "sentence_applied_by": "relay",
            "main": branch_tasks(), "held_out": [],
        },
    }  # fmt: skip
    return {
        "note": "Reply-0 registered tasks. Written by make_tasks.py; do not edit by hand.",
        "variables": {"FX": "the fixture directory built by fixture.py"},
        "system_prompt": SYSTEM_PROMPT,
        "generic_sentence": GENERIC_SENTENCE,
        "matching": {
            "normalise": "Per line: NFKC, casefold, collapse whitespace, strip outer quotes, "
            "backticks and brackets, one final period, then outer wrappers again. "
            "Remove commas only in a complete correctly grouped unsigned integer.",
            "pass": "At most 600 raw characters. Trim the answer. Its normalised lines must "
            "equal the complete expected lines once each in any order. No commentary, "
            "negations, extra values or internal blank lines.",
        },
        "run_order": [
            "clean",
            "unscripted",
            "C0/4B",
            "F1/4B",
            "F1/12B if needed",
            "one eligible F1 confirmation",
            "measured and descriptive rows",
        ],
        "cells": cells,
    }


def main() -> None:
    path = HERE / "tasks.json"
    doc = document()
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for name, cell in doc["cells"].items():
        print(name, cell["role"], len(cell["main"]), "main,", len(cell["held_out"]), "held out")


if __name__ == "__main__":
    main()
