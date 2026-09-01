from __future__ import annotations

from dataclasses import dataclass
import os

import pandas as pd
import streamlit as st

from ..data import YahooFinanceProvider
from ..services import AnalysisRequest, AnalysisService, PersistentPaperState, PortfolioService
from ..storage import Store
from ..trading import PaperPortfolio
from .sidebar import UISettings


@st.cache_data(ttl=300, show_spinner=False)
def _load_market_data(symbol: str, period: str, interval: str) -> pd.DataFrame:
    return YahooFinanceProvider().fetch(symbol, period, interval)


class CachedYahooProvider:
    def fetch(self, symbol: str, period: str, interval: str, minimum_rows: int = 80) -> pd.DataFrame:
        frame = _load_market_data(symbol, period, interval)
        if len(frame) < minimum_rows:
            raise ValueError(f"Only {len(frame)} valid rows returned; at least {minimum_rows} are required")
        return frame


@dataclass
class AppContext:
    settings: UISettings
    portfolio: PaperPortfolio
    store: Store
    portfolio_service: PortfolioService
    analysis_service: AnalysisService
    request: AnalysisRequest
    paper_state: PersistentPaperState | None = None
    portfolio_reset: bool = False

    def analyze_watchlist(self):
        return self.analysis_service.analyze_watchlist(self.settings.watchlist, self.request)


def _portfolio(settings: UISettings, store: Store) -> tuple[PaperPortfolio, bool, PersistentPaperState]:
    config = (settings.starting_cash, settings.commission_rate, settings.slippage_rate)
    previous = st.session_state.get("portfolio_config")
    reset = False
    paper_state = PersistentPaperState(store.path)

    if "portfolio" not in st.session_state:
        restored = paper_state.load(*config)
        st.session_state.portfolio = restored or PaperPortfolio(*config)
        if restored is None:
            paper_state.save(st.session_state.portfolio)
        st.session_state.portfolio_config = config
    elif previous != config:
        st.session_state.portfolio = PaperPortfolio(*config)
        st.session_state.portfolio_config = config
        paper_state.save(st.session_state.portfolio)
        reset = previous is not None

    return st.session_state.portfolio, reset, paper_state


def _store() -> Store:
    if "store" not in st.session_state:
        st.session_state.store = Store(os.getenv("PAPER_DB_PATH", ".data/paper_trading.db"))
    return st.session_state.store


def build_context(settings: UISettings) -> AppContext:
    store = _store()
    portfolio, reset, paper_state = _portfolio(settings, store)
    request = AnalysisRequest(
        period=settings.period,
        interval=settings.interval,
        horizon=settings.horizon,
        buy_threshold=settings.buy_threshold,
        sell_threshold=settings.sell_threshold,
        commission_rate=settings.commission_rate,
        slippage_rate=settings.slippage_rate,
    )
    return AppContext(
        settings=settings,
        portfolio=portfolio,
        store=store,
        portfolio_service=PortfolioService(portfolio, store, paper_state),
        analysis_service=AnalysisService(CachedYahooProvider()),
        request=request,
        paper_state=paper_state,
        portfolio_reset=reset,
    )
