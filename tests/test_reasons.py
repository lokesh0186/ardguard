from ardguard.reasons import REASON_DEFINITIONS, ReasonCode


def test_every_reason_is_documented() -> None:
    assert set(ReasonCode) == set(REASON_DEFINITIONS)


def test_all_uncertainty_reasons_fail_closed() -> None:
    for code in ReasonCode:
        if "unavailable" in code.value or "indeterminate" in code.value or "error" in code.value:
            assert REASON_DEFINITIONS[code].fail_closed
