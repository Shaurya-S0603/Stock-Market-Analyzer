from stockmarket.storage import Store


def test_portfolio_profile_round_trip(tmp_path) -> None:
    store = Store(str(tmp_path / "paper.db"))
    store.save_portfolio_profile(
        starting_capital=125_000.0,
        cash_target_pct=20.0,
        risk_profile="Balanced",
        trader_mode="OBSERVE",
        allocations={"AAPL": 30.0, "MSFT": 25.0, "NVDA": 25.0},
    )

    profile = store.portfolio_profile()
    assert profile is not None
    assert profile["starting_capital"] == 125_000.0
    assert profile["cash_target_pct"] == 20.0
    assert profile["risk_profile"] == "Balanced"
    assert profile["trader_mode"] == "OBSERVE"
    assert profile["allocations"] == {"AAPL": 30.0, "MSFT": 25.0, "NVDA": 25.0}

    store.clear_portfolio_profile()
    assert store.portfolio_profile() is None
