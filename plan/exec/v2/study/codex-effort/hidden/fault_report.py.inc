@pytest.mark.parametrize("starts,occurrence,index", [((9, 2), 6, 1), ((3, 11), 8, 0)])
def test_reordered_declarations(
    starts: tuple[int, int], occurrence: int, index: int
) -> None:
    condition = Condition(
        condition_id="faults",
        faults=tuple(fault("decision_unavailable", occurrence=start) for start in starts),
    )
    trial = trial_with_injections(("decision_unavailable", "decision:systemone", occurrence))
    rows = [r for r in fault_accounting((condition,), (trial,)) if r["arm"] == "baseline"]
    assert len(rows) == 2
    assert rows[index]["status"] == "observed" and rows[index]["injections"] == 1
    assert rows[1 - index]["status"] == "declared, never fired"
