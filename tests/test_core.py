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
    index=pd.date_range("2025-01-01",periods=rows,freq="5min"); close=pd.Series(100+np.linspace(0,8,rows)+np.sin(np.arange(rows)),index=index)
    return pd.DataFrame({"Open":close-0.2,"High":close+0.5,"Low":close-0.5,"Close":close,"Volume":1000},index=index)


def test_normalize_flattens_yahoo_multiindex():
    frame=bars(); frame.columns=pd.MultiIndex.from_tuples([(column,"MSFT") for column in frame.columns]); result=normalize_ohlcv(frame)
    assert list(result.columns)==["Open","High","Low","Close","Volume"]; assert result.index.is_monotonic_increasing


def test_empty_data_is_rejected():
    with pytest.raises(MarketDataError): normalize_ohlcv(pd.DataFrame())


def test_features_support_training_and_live_rows():
    market=bars(); training=build_features(market,horizon=3,include_target=True); live=build_features(market,horizon=3,include_target=False)
    assert set(FEATURE_COLUMNS).issubset(training.columns); assert "target_return" in training.columns; assert "target_return" not in live.columns; assert training.index[-1]<market.index[-1]; assert live.index[-1]==market.index[-1]; assert np.isfinite(training["target_return"]).all()


def test_training_and_walk_forward_validation_work():
    features=build_features(bars(),horizon=3); result=train_model(features)
    assert set(result.metrics)>={"rmse","mae","directional_accuracy","baseline_rmse","strategy_return"}; assert result.predict(build_features(bars(),horizon=3,include_target=False).iloc[[-1]]).shape==(1,)
    scores=walk_forward_scores(features,splits=3); assert len(scores)==3; assert all("fold" in score for score in scores)


def test_signal_uses_configured_thresholds():
    assert make_signal(0.012,buy_threshold=0.005,sell_threshold=-0.005,round_trip_cost=0.002).action=="Buy"; assert make_signal(0.004,buy_threshold=0.005,sell_threshold=-0.005,round_trip_cost=0.002).action=="Hold"; assert make_signal(-0.010,buy_threshold=0.005,sell_threshold=-0.005,round_trip_cost=0.002).action=="Sell"


def test_portfolio_rejects_invalid_orders_and_tracks_pnl():
    portfolio=PaperPortfolio(1_000,commission_rate=0,slippage_rate=0)
    with pytest.raises(TradingError): portfolio.execute("MSFT","buy",20,100)
    portfolio.execute("MSFT","buy",2,100)
    with pytest.raises(TradingError): portfolio.execute("MSFT","sell",3,120)
    portfolio.execute("MSFT","sell",1,120); assert portfolio.summary({"MSFT":120})["pnl"]==pytest.approx(40)


def test_backtest_equity_starts_after_first_execution_bar():
    market=bars(80); features=build_features(market,horizon=1); predictions=pd.Series(0.02,index=features.index); report=run_backtest("MSFT",market.loc[features.index],predictions,starting_cash=10_000,commission_rate=0,slippage_rate=0)
    assert report["equity_curve"].index[0]==features.index[1]; assert report["summary"]["trades"]>=1


def test_purged_walk_forward_splits_respect_forecast_gap():
    from stockmarket.validation import purged_walk_forward_splits
    folds=purged_walk_forward_splits(160,splits=3,purge=6); assert len(folds)==3; assert all(fold.test_start-fold.train_end==6 for fold in folds); assert all(fold.train_start==0 for fold in folds)


def test_walk_forward_reports_purge_and_fold_sizes():
    from stockmarket.validation import walk_forward_scores as leakage_safe_scores
    features=build_features(bars(220),horizon=4); scores=leakage_safe_scores(features,splits=3,purge=4); assert len(scores)==3; assert all(score["purge_rows"]==4 for score in scores); assert all(score["train_rows"]>=30 for score in scores)


def test_live_model_is_refit_on_all_labeled_rows():
    from stockmarket.modeling import fit_model
    features=build_features(bars(200),horizon=3); model=train_model(features); full=fit_model(features); assert np.allclose(model.coefficients,full.coefficients); assert model.metrics["holdout_rows"]>0


def test_benchmark_ladder_includes_simple_and_current_models():
    from stockmarket.benchmarks import benchmark_models
    rows=benchmark_models(build_features(bars(240),horizon=3),splits=3,purge=3); assert {row["model"] for row in rows}=={"zero_return","historical_mean","momentum","ridge","ridge_momentum"}; assert all(row["folds"]==3 for row in rows)


def test_model_gate_requires_outperformance_and_direction_accuracy():
    from stockmarket.benchmarks import assess_model_gate
    rows=[{"model":"zero_return","rmse":0.020,"directional_accuracy":0.0},{"model":"historical_mean","rmse":0.018,"directional_accuracy":0.45},{"model":"momentum","rmse":0.017,"directional_accuracy":0.49},{"model":"ridge_momentum","rmse":0.015,"directional_accuracy":0.56}]
    assert assess_model_gate(rows).approved; weak=[dict(row) for row in rows]; weak[-1]["rmse"]=0.019; assert not assess_model_gate(weak).approved


def test_train_model_holdout_is_purged():
    model=train_model(build_features(bars(220),horizon=5),purge=5); assert model.metrics["purge_rows"]==5; assert model.metrics["holdout_rows"]>0


def test_backtest_reports_risk_and_benchmark_metrics():
    market=bars(100); features=build_features(market,horizon=1); predictions=pd.Series(0.02,index=features.index); summary=run_backtest("MSFT",market.loc[features.index],predictions,starting_cash=10_000,commission_rate=0,slippage_rate=0)["summary"]
    assert {"hit_rate_pct","turnover_pct","exposure_pct","risk_adjusted_score","buy_hold_return_pct","excess_vs_buy_hold_pct","round_trips"}.issubset(summary); assert 0<=summary["exposure_pct"]<=100; assert summary["turnover_pct"]>=0


def test_analysis_service_uses_latest_live_feature_row_and_purge():
    from stockmarket.services import AnalysisRequest, AnalysisService
    class FakeProvider:
        def fetch(self,symbol,period,interval,minimum_rows=80): return bars(240)
    request=AnalysisRequest("60d","5m",4,0.005,-0.005,0.001,0.0005); result=AnalysisService(FakeProvider()).analyze_symbol("MSFT",request)
    assert result.live_features.index[-1]==result.bars.index[-1]; assert result.training_features.index[-1]<result.bars.index[-1]; assert result.model.metrics["purge_rows"]==4


def test_analysis_service_backtest_is_purged_and_reports_benchmark():
    from stockmarket.services import AnalysisRequest, AnalysisService
    class FakeProvider:
        def fetch(self,symbol,period,interval,minimum_rows=80): return bars(260)
    request=AnalysisRequest("60d","5m",3,0.005,-0.005,0.0,0.0); service=AnalysisService(FakeProvider()); analysis=service.analyze_symbol("MSFT",request); benchmark_rows,gate=service.benchmark_report(analysis); report=service.backtest(analysis,request,10_000)
    assert len(benchmark_rows)==5; assert isinstance(gate.approved,bool); assert "buy_hold_return_pct" in report["summary"]
