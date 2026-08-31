from stockmarket.ui.onboarding import equal_allocations, validate_allocations


def test_equal_allocations_preserve_cash_reserve() -> None:
    allocations = equal_allocations(["AAPL", "MSFT", "NVDA"], 20.0)
    assert round(sum(allocations.values()), 2) == 80.0
    assert round(sum(allocations.values()) + 20.0, 2) == 100.0


def test_allocation_validation_requires_full_portfolio() -> None:
    valid, total, _ = validate_allocations({"AAPL": 35.0, "MSFT": 35.0}, 30.0)
    assert valid is True
    assert total == 100.0

    invalid, total, message = validate_allocations({"AAPL": 35.0, "MSFT": 35.0}, 20.0)
    assert invalid is False
    assert total == 90.0
    assert "100%" in message
