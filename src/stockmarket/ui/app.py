from __future__ import annotations

import os
import pandas as pd
import streamlit as st

from ..data import YahooFinanceProvider
from ..services import AnalysisRequest, AnalysisService, PortfolioService, RiskPolicy
from ..storage import Store
from ..trading import PaperPortfolio
from .pages import render_backtest, render_dashboard, render_model_health, render_trading
from .sidebar import UISettings, render_sidebar
from .theme import apply_theme


@st.cache_data(ttl=300, show_spinner=False)
def _load_market_data(symbol: str, period: str, interval: str) -> pd.DataFrame:
    return YahooFinanceProvider().fetch(symbol,period,interval)


class CachedYahooProvider:
    def fetch(self,symbol:str,period:str,interval:str,minimum_rows:int=80)->pd.DataFrame:
        frame = _load_market_data(symbol,period,interval)
        if len(frame)<minimum_rows: raise ValueError(f"Only {len(frame)} valid rows returned; at least {minimum_rows} are required")
        return frame


def _portfolio(settings:UISettings)->tuple[PaperPortfolio,bool]:
    config=(settings.starting_cash,settings.commission_rate,settings.slippage_rate); previous=st.session_state.get("portfolio_config"); reset=False
    if "portfolio" not in st.session_state or previous!=config:
        st.session_state.portfolio=PaperPortfolio(*config); st.session_state.portfolio_config=config; reset=previous is not None
    return st.session_state.portfolio,reset


def _store()->Store:
    if "store" not in st.session_state: st.session_state.store=Store(os.getenv("PAPER_DB_PATH",".data/paper_trading.db"))
    return st.session_state.store


def render_app()->None:
    apply_theme()
    st.markdown('<section class="hero" aria-label="Stock Market Analyzer introduction"><h1 class="hero-title">Stock Market Analyzer</h1><p class="hero-copy">Research market trends, validate forecasting signals, backtest strategies, and practice execution with a paper-only portfolio.</p><span class="notice">Simulation only · no broker routing</span></section>',unsafe_allow_html=True)
    settings=render_sidebar(); portfolio,reset=_portfolio(settings); store=_store(); portfolio_service=PortfolioService(portfolio,store)
    request=AnalysisRequest(settings.period,settings.interval,settings.horizon,settings.buy_threshold,settings.sell_threshold,settings.commission_rate,settings.slippage_rate)
    analysis_service=AnalysisService(CachedYahooProvider())
    if reset: st.info("Paper portfolio reset because starting cash or trading-cost assumptions changed.")
    with st.spinner("Loading market data and evaluating models…"): result=analysis_service.analyze_watchlist(settings.watchlist,request)
    if not result.available:
        st.error("No watchlist symbol returned usable data. Check symbols and the history/interval combination.")
        for symbol,error in result.unavailable.items(): st.caption(f"{symbol}: {error}")
        st.stop()
    for symbol,error in result.unavailable.items(): st.warning(f"{symbol} was skipped: {error}")
    prices={symbol:state.price for symbol,state in result.available.items()}
    policy=RiskPolicy(settings.automation_enabled,settings.stop_loss_pct,settings.take_profit_pct)
    for event in portfolio_service.apply_risk_policy(prices,policy): st.success(event)
    primary_symbol=next(iter(result.available)); primary=result.available[primary_symbol]; summary=portfolio.summary(prices)
    cols=st.columns(4); cols[0].metric("Tracked symbols",str(len(result.available))); cols[1].metric("Reference symbol",primary_symbol); cols[2].metric("Reference price",f"${primary.price:,.2f}"); cols[3].metric("Paper P&L",f"${summary['pnl']:,.2f}",f"{summary['return_pct']:.2f}%")
    st.caption(f"Watchlist: {', '.join(result.available)} · Window: {settings.period} · Interval: {settings.interval} · Horizon: {settings.horizon} bars · Reference data as of {primary.timestamp}")
    st.warning("Historical metrics and model signals are research outputs, not guarantees of future performance or personalized investment advice.")
    dashboard_tab,model_tab,trade_tab,backtest_tab=st.tabs(["Dashboard","Model health","Paper trading","Backtest"])
    with dashboard_tab: render_dashboard(result.available,portfolio,prices)
    with model_tab: render_model_health(result.available,analysis_service)
    with trade_tab: render_trading(result.available,portfolio,portfolio_service,store,prices)
    with backtest_tab: render_backtest(result.available,analysis_service,request,settings.starting_cash)
