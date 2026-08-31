import numpy as np
import pandas as pd
import pytest

from stockmarket.backtest import run_backtest
from stockmarket.data import MarketDataError, normalize_ohlcv
from stockmarket.features import FEATURE_COLUMNS, build_features
from stockmarket.modeling import train_model, walk_forward_scores
from stockmarket.signals import make_signal
from stockmarket.trading import PaperPortfolio, TradingError


def bars(rows=180):
    index = pd.date_range("2025-01-01", periods=rows, freq="5min")
    close = pd.Series(100 + np.linspace(0, 8, rows) + np.sin(np.arange(rows)), index=index)
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": 1000,
        },
        index=index,
    )


def test_normalize_flattens_yahoo_multiindex():
    frame = bars()
    frame.columns = pd.MultiIndex.from_tuples([(column, "MSFT") for column in frame.columns])
    result = normalize_ohlcv(frame)
    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert result.index.is_monotonic_increasing


def test_empty_data_is_rejected():
    with pytest.raises(MarketDataError):
        normalize_ohlcv(pd.DataFrame())


def test_features_support_training_and_live_rows():
    market = bars()
    training = build_features(market, horizon=3, include_target=True)
    live = build_features(market, horizon=3, include_target=False)
    assert set(FEATURE_COLUMNS).issubset(training.columns)
    assert "target_return" in training.columns
    assert "target_return" not in live.columns
    assert training.index[-1] < market.index[-1]
    assert live.index[-1] == market.index[-1]
    assert np.isfinite(training["target_return"]).all()


def test_training_and_walk_forward_validation_work():
    features = build_features(bars(), horizon=3)
    result = train_model(features)
    assert set(result.metrics) >= {"rmse", "mae", "directional_accuracy", "baseline_rmse", "strategy_return"}
    prediction = result.predict(build_features(bars(), horizon=3, include_target=False).iloc[[-1]])
    assert prediction.shape == (1,)
    scores = walk_forward_scores(features, splits=3)
    assert len(scores) == 3
    assert all("fold" in score for score in scores)


def test_signal_uses_configured_thresholds():
    assert make_signal(0.012, buy_threshold=0.005, sell_threshold=-0.005, round_trip_cost=0.002).action == "Buy"
    assert make_signal(0.004, buy_threshold=0.005, sell_threshold=-0.005, round_trip_cost=0.002).action == "Hold"
    assert make_signal(-0.010, buy_threshold=0.005, sell_threshold=-0.005, round_trip_cost=0.002).action == "Sell"


def test_portfolio_rejects_invalid_orders_and_tracks_pnl():
    portfolio = PaperPortfolio(1_000, commission_rate=0, slippage_rate=0)
    with pytest.raises(TradingError):
        portfolio.execute("MSFT", "buy", 20, 100)
    portfolio.execute("MSFT", "buy", 2, 100)
    with pytest.raises(TradingError):
        portfolio.execute("MSFT", "sell", 3, 120)
    portfolio.execute("MSFT", "sell", 1, 120)
    assert portfolio.summary({"MSFT": 120})["pnl"] == pytest.approx(40)


def test_backtest_equity_starts_after_first_execution_bar():
    market = bars(80)
    features = build_features(market, horizon=1)
    predictions = pd.Series(0.02, index=features.index)
    report = run_backtest(
        "MSFT",
        market.loc[features.index],
        predictions,
        starting_cash=10_000,
        commission_rate=0,
        slippage_rate=0,
    )
    assert report["equity_curve"].index[0] == features.index[1]
    assert report["summary"]["trades"] >= 1


def test_purged_walk_forward_splits_respect_forecast_gap():
    from stockmarket.validation import purged_walk_forward_splits

    folds = purged_walk_forward_splits(160, splits=3, purge=6)
    assert len(folds) == 3
    assert all(fold.test_start - fold.train_end == 6 for fold in folds)
    assert all(fold.train_start == 0 for fold in folds)


def test_walk_forward_reports_purge_and_fold_sizes():
    from stockmarket.validation import walk_forward_scores as leakage_safe_scores

    features = build_features(bars(220), horizon=4)
    scores = leakage_safe_scores(features, splits=3, purge=4)
    assert len(scores) == 3
    assert all(score["purge_rows"] == 4 for score in scores)
    assert all(score["train_rows"] >= 30 for score in scores)


def test_live_model_is_refit_on_all_labeled_rows():
    features = build_features(bars(200), horizon=3)
    model = train_model(features)
    from stockmarket.modeling import fit_model

    full = fit_model(features)
    assert np.allclose(model.coefficients, full.coefficients)
    assert model.metrics["holdout_rows"] > 0


def test_benchmark_ladder_includes_simple_and_current_models():
    from stockmarket.benchmarks import benchmark_models

    features = build_features(bars(240), horizon=3)
    rows = benchmark_models(features, splits=3, purge=3)
    names = {row["model"] for row in rows}
    assert names == {"zero_return", "historical_mean", "momentum", "ridge", "ridge_momentum"}
    assert all(row["folds"] == 3 for row in rows)


def test_model_gate_requires_outperformance_and_direction_accuracy():
    from stockmarket.benchmarks import assess_model_gate

    rows = [
        {"model": "zero_return", "rmse": 0.020, "directional_accuracy": 0.0},
        {"model": "historical_mean", "rmse": 0.018, "directional_accuracy": 0.45},
        {"model": "momentum", "rmse": 0.017, "directional_accuracy": 0.49},
        {"model": "ridge_momentum", "rmse": 0.015, "directional_accuracy": 0.56},
    ]
    gate = assess_model_gate(rows)
    assert gate.approved
    weak = [dict(row) for row in rows]
    weak[-1]["rmse"] = 0.019
    assert not assess_model_gate(weak).approved


def test_train_model_holdout_is_purged():
    features = build_features(bars(220), horizon=5)
    model = train_model(features, purge=5)
    assert model.metrics["purge_rows"] == 5
    assert model.metrics["holdout_rows"] > 0


def test_backtest_reports_risk_and_benchmark_metrics():
    market = bars(100)
    features = build_features(market, horizon=1)
    predictions = pd.Series(0.02, index=features.index)
    report = run_backtest("MSFT", market.loc[features.index], predictions, starting_cash=10_000, commission_rate=0, slippage_rate=0)
    summary = report["summary"]
    expected = {"hit_rate_pct", "turnover_pct", "exposure_pct", "risk_adjusted_score", "buy_hold_return_pct", "excess_vs_buy_hold_pct", "round_trips"}
    assert expected.issubset(summary)
    assert 0 <= summary["exposure_pct"] <= 100
    assert summary["turnover_pct"] >= 0


def test_analysis_service_uses_latest_live_feature_row_and_purge():
    from stockmarket.services import AnalysisRequest, AnalysisService

    class FakeProvider:
        def fetch(self, symbol, period, interval, minimum_rows=80):
            return bars(240)

    request = AnalysisRequest("60d", "5m", 4, 0.005, -0.005, 0.001, 0.0005)
    result = AnalysisService(FakeProvider()).analyze_symbol("MSFT", request)
    assert result.live_features.index[-1] == result.bars.index[-1]
    assert result.training_features.index[-1] < result.bars.index[-1]
    assert result.model.metrics["purge_rows"] == 4


def test_analysis_service_backtest_is_purged_and_reports_benchmark():
    from stockmarket.services import AnalysisRequest, AnalysisService

    class FakeProvider:
        def fetch(self, symbol, period, interval, minimum_rows=80):
            return bars(260)

    request = AnalysisRequest("60d", "5m", 3, 0.005, -0.005, 0.0, 0.0)
    service = AnalysisService(FakeProvider())
    analysis = service.analyze_symbol("MSFT", request)
    benchmark_rows, gate = service.benchmark_report(analysis)
    report = service.backtest(analysis, request, 10_000)
    assert len(benchmark_rows) == 5
    assert isinstance(gate.approved, bool)
    assert "buy_hold_return_pct" in report["summary"]


def _analysis_for_signal(action: str, confidence: float = 0.8, price: float = 100.0):
    from types import SimpleNamespace
    predicted = 0.02 if action == "Buy" else -0.02 if action == "Sell" else 0.0
    return SimpleNamespace(
        symbol="MSFT",
        price=price,
        predicted_return=predicted,
        signal=SimpleNamespace(action=action, confidence=confidence, net_edge=predicted),
    )


def test_ai_trader_observe_mode_never_executes():
    from stockmarket.services.ai_trader import AITraderConfig, AITraderService, TraderMode
    from stockmarket.services.portfolio import PortfolioService
    from stockmarket.storage import Store
    import tempfile

    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    with tempfile.TemporaryDirectory() as tmp:
        service = PortfolioService(portfolio, Store(f"{tmp}/paper.db"))
        decisions = AITraderService().run_cycle(
            {"MSFT": _analysis_for_signal("Buy")}, {"MSFT": True}, portfolio, service,
            AITraderConfig(TraderMode.OBSERVE, min_confidence=0.6, allocation_pct=10),
        )
    assert decisions[0].decision == "BUY"
    assert not decisions[0].executed
    assert portfolio.positions.get("MSFT") is None


def test_ai_trader_paper_auto_executes_and_prevents_duplicate_entry():
    from stockmarket.services.ai_trader import AITraderConfig, AITraderService, TraderMode
    from stockmarket.services.portfolio import PortfolioService
    from stockmarket.storage import Store
    import tempfile

    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    config = AITraderConfig(TraderMode.PAPER_AUTO, min_confidence=0.6, allocation_pct=10)
    with tempfile.TemporaryDirectory() as tmp:
        service = PortfolioService(portfolio, Store(f"{tmp}/paper.db"))
        trader = AITraderService()
        first = trader.run_cycle({"MSFT": _analysis_for_signal("Buy")}, {"MSFT": True}, portfolio, service, config)[0]
        second = trader.run_cycle({"MSFT": _analysis_for_signal("Buy")}, {"MSFT": True}, portfolio, service, config)[0]
    assert first.executed and 0 < first.quantity <= 10
    assert portfolio.positions["MSFT"].quantity == first.quantity
    assert second.decision == "REJECT" and not second.executed


def test_ai_trader_rejects_low_confidence_or_failed_model_gate():
    from stockmarket.services.ai_trader import AITraderConfig, AITraderService, TraderMode

    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    trader = AITraderService()
    config = AITraderConfig(TraderMode.OBSERVE, min_confidence=0.7, allocation_pct=10)
    low = trader.evaluate_symbol(_analysis_for_signal("Buy", confidence=0.5), True, portfolio, config)
    failed_gate = trader.evaluate_symbol(_analysis_for_signal("Buy", confidence=0.9), False, portfolio, config)
    assert low.decision == "REJECT"
    assert failed_gate.decision == "REJECT"


def test_risk_engine_caps_position_and_portfolio_exposure():
    from stockmarket.services.risk import RiskEngine, RiskLimits

    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    assessment = RiskEngine().assess_entry(
        "MSFT", 100, 1.0, 0.01, portfolio, {"MSFT": 100}, [], 50,
        RiskLimits(max_position_pct=10, max_portfolio_exposure_pct=20, max_open_positions=3, max_daily_trades=10, max_daily_loss_pct=3, volatility_target_pct=2),
    )
    assert assessment.approved
    assert assessment.quantity == 10
    assert assessment.projected_exposure_pct <= 20


def test_risk_engine_blocks_daily_loss_and_trade_limits():
    from datetime import datetime, timezone
    from stockmarket.services.risk import RiskEngine, RiskLimits

    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    orders = [{"created_at": now, "realized_pnl": -400}, {"created_at": now, "realized_pnl": 0}]
    limits = RiskLimits(max_position_pct=10, max_portfolio_exposure_pct=60, max_open_positions=6, max_daily_trades=2, max_daily_loss_pct=3, volatility_target_pct=1.5)
    assessment = RiskEngine().assess_entry("MSFT", 100, .9, .01, portfolio, {"MSFT":100}, orders, 5, limits)
    assert not assessment.approved


def test_journal_service_persists_decisions_and_snapshot():
    import tempfile
    from stockmarket.services.ai_trader import TradeDecision, TraderMode
    from stockmarket.services.journal import JournalService
    from stockmarket.storage import Store

    decision = TradeDecision("MSFT", "Buy", "BUY", 2, 100.0, 0.8, 0.02, 0.018, True, "test", True)
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("MSFT", "buy", 2, 100)
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(f"{tmp}/paper.db")
        summary = JournalService(store).record_cycle([decision], TraderMode.PAPER_AUTO, portfolio, {"MSFT": 101})
        assert summary.executed == 1
        assert store.ai_decisions()[0]["symbol"] == "MSFT"
        assert store.trader_runs()[0]["cycle_id"] == summary.cycle_id
        assert store.portfolio_snapshots()[0]["equity"] == pytest.approx(portfolio.equity({"MSFT":101}))


def test_trader_analytics_computes_win_rate_and_expectancy():
    import tempfile
    from stockmarket.services.analytics import build_trader_analytics
    from stockmarket.storage import Store

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(f"{tmp}/paper.db")
        store.add_order("MSFT", "sell", 1, 110, 0, realized_pnl=10, reason="ai_trader")
        store.add_order("AAPL", "sell", 1, 95, 0, realized_pnl=-5, reason="ai_trader")
        analytics = build_trader_analytics(store)
        assert analytics.closed_trades == 2
        assert analytics.win_rate == pytest.approx(0.5)
        assert analytics.realized_pnl == pytest.approx(5)
        assert analytics.expectancy == pytest.approx(2.5)
        assert analytics.profit_factor == pytest.approx(2.0)


def test_cycle_fingerprint_is_stable_and_changes_with_market_bar():
    from types import SimpleNamespace
    from stockmarket.services import AITraderConfig, TraderMode, cycle_fingerprint

    def item(timestamp):
        return SimpleNamespace(
            timestamp=timestamp,
            predicted_return=0.02,
            signal=SimpleNamespace(action="Buy"),
        )

    config = AITraderConfig(TraderMode.PAPER_AUTO, min_confidence=0.65, allocation_pct=5)
    first = cycle_fingerprint({"MSFT": item("2026-08-31 10:00:00")}, config)
    same = cycle_fingerprint({"MSFT": item("2026-08-31 10:00:00")}, config)
    later = cycle_fingerprint({"MSFT": item("2026-08-31 10:05:00")}, config)
    assert first == same
    assert first != later


def test_protective_exit_records_risk_event():
    import tempfile
    from stockmarket.services.portfolio import PortfolioService, RiskPolicy
    from stockmarket.storage import Store

    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("MSFT", "buy", 10, 100)
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(f"{tmp}/paper.db")
        service = PortfolioService(portfolio, store)
        events = service.apply_risk_policy({"MSFT": 95}, RiskPolicy(True, stop_loss_pct=2, take_profit_pct=4))
        assert events
        assert portfolio.positions["MSFT"].quantity == 0
        risk = store.risk_events()
        assert risk[0]["symbol"] == "MSFT"
        assert risk[0]["event_type"] == "stop_loss"
