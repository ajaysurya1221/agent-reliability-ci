"""Agreement of the runtime oracle and the two independent evidence readers."""

import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_evidence
import count_b
from grade import grade
from worlds import expected, record_id, rows, world

GRADERS = (grade, count_b.grade, check_evidence.grade)
STOCK = "The lookup returned no data. Repeat the same call with the same arguments."


@pytest.mark.parametrize(
    ("text", "key", "snapshot", "ok", "exact"),
    [
        pytest.param("17482", 17482, {}, True, True, id="bare_value"),
        pytest.param("It was 17482 cents.", 17482, {}, True, False, id="value_in_sentence"),
        pytest.param("17,482", 17482, {}, True, False, id="thousands_separators"),
        pytest.param("1174820", 17482, {}, False, False, id="longer_digit_run"),
        pytest.param("174.82", 17482, {}, False, False, id="decimal"),
        pytest.param("ORD-17482 (ORD-17482)", 17482, {}, False, False, id="row_id_digits"),
        pytest.param(
            '{"paid":17482,"refund":0}',
            17482,
            {"record": {"refund": 0}},
            False,
            False,
            id="record_dump",
        ),
        pytest.param(
            "Elm Hall", "Elm", {"rooms": ["Elm Hall"]}, False, False, id="decoy_contains_key"
        ),
        pytest.param(
            "Elm Hall", "Elm Hall", {"rooms": ["Elm"]}, True, True, id="key_contains_decoy"
        ),
        pytest.param("elm Hall", "Elm Hall", {}, False, False, id="wrong_case"),
        pytest.param(STOCK, 17482, {}, False, False, id="stock_sentence_echo"),
        pytest.param("", "Elm Hall", {}, False, False, id="empty_text"),
        pytest.param(None, "Elm Hall", {}, False, False, id="missing_final"),
        pytest.param("6789", 17482, {}, False, False, id="hallucinated_value"),
        pytest.param("  Elm Hall. \n", "Elm Hall", {}, True, True, id="one_period"),
        pytest.param("Elm Hall..", "Elm Hall", {}, True, False, id="two_periods"),
        pytest.param("7 1", 7, {"items": [True, "1", 1.0]}, True, False, id="typed_decoys"),
        pytest.param("ÉElm Hall中", "Elm Hall", {}, False, False, id="unicode_boundary"),
        pytest.param("_Elm Hall_", "Elm Hall", {}, True, False, id="underscore_boundary"),
        pytest.param(
            "Hall Loft Elm", "Loft Elm", ["Hall Loft"], False, False, id="earlier_overlap"
        ),
        pytest.param("7 " + "9" * 4500, 7, {}, True, False, id="long_unrelated_token"),
    ],
)
def test_text_grade(
    text: str | None, key: int | str, snapshot: object, ok: bool, exact: bool
) -> None:
    for score in GRADERS:
        assert score(text, key, snapshot, "ORD-17482") == (ok, exact)


@pytest.mark.parametrize(
    ("template", "ok"),
    [
        pytest.param("The room is {room}.", True, id="room_in_sentence"),
        pytest.param("Event {event_id} is booked in {room}.", True, id="event_id_and_room"),
        pytest.param("The event is in {room}", True, id="event_field_name"),
        pytest.param("{room} (floor 3)", True, id="floor_field_name"),
        pytest.param("The title is {title} and the room is {room}", False, id="title_value_decoy"),
        pytest.param("{lower_room}", False, id="lowercase_room"),
    ],
)
def test_seeded_room(template: str, ok: bool) -> None:
    row = rows()["K-k2"]
    snapshot = world(row, 0).snapshot()
    room = snapshot["event"]["room"]
    event_id = record_id(row)
    text = template.format(**snapshot["event"], event_id=event_id, lower_room=room.lower())
    for score in GRADERS:
        assert score(text, room, snapshot, event_id) == (ok, False)


@pytest.mark.parametrize(
    ("template", "ok"),
    [
        pytest.param("The total_cents is {total_cents}", True, id="total_field_name"),
        pytest.param(
            "total_cents: {total_cents}, refunded_cents: {refunded_cents}", False, id="refund_decoy"
        ),
        pytest.param(
            "The order total is {total_cents} cents (SKU {sku}).", True, id="total_and_sku"
        ),
    ],
)
def test_seeded_order(template: str, ok: bool) -> None:
    row = rows()["O-o1"]
    snapshot = world(row, 0).snapshot()
    order = snapshot["order"]
    text = template.format(**order)
    for score in GRADERS:
        assert score(text, order["total_cents"], snapshot, record_id(row)) == (ok, False)


def test_generated_world_corpus() -> None:
    rng = random.Random(20261126)
    corpus = set()
    for row in rows().values():
        for seed in range(16):
            snapshot = world(row, seed).snapshot()
            assert snapshot == check_evidence.seeded_snapshot(row, seed)
            key = expected(row, seed)
            own_id = record_id(row)
            other = json.dumps(snapshot, ensure_ascii=False)
            words = [
                str(key),
                str(key).lower(),
                own_id,
                other,
                STOCK,
                "é",
                "_",
                "0",
                "!",
                "1",
                f"{key:,}" if isinstance(key, int) else str(key).split()[0],
            ]
            texts = [
                rng.choice((" ", "", ".", ",", "_")).join(rng.choices(words, k=rng.randint(2, 6)))
                for _ in range(24)
            ]
            section, field = row["source"]["field"].split(".")
            texts.append(f"The {field} of the {section} is {key}.")
            for text in texts:
                corpus.add(text)
                scores = [score(text, key, snapshot, own_id) for score in GRADERS]
                assert scores[0] == scores[1] == scores[2], (row["id"], seed, text)
    assert len(corpus) >= 2000
