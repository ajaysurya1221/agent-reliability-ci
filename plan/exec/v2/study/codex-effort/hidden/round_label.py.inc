def test_negative_zero_keeps_historical_value() -> None:
    from arci.importers import round_label

    assert round_label("-0") == 0
