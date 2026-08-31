from __future__ import annotations

from dataclasses import asdict, dataclass

import streamlit as st


@dataclass(frozen=True)
class UISettings:
    watchlist: list[str]
    period: str = "60d"
    interval: str = "5m"
    horizon: int = 12
    buy_threshold: float = 0.005
    sell_threshold: float = -0.005
    starting_cash: float = 100_000.0
    commission_rate: float = 0.001
    slippage_rate: float = 0.0005
    automation_enabled: bool = False
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 4.0


def sanitize_symbol(symbol: str) -> str:
    cleaned = "".join(ch for ch in symbol.upper().strip() if ch.isalnum() or ch in {".", "-"})
    if cleaned == "APPL":
        return "AAPL"
    return cleaned or "MSFT"


def parse_watchlist(raw_watchlist: str) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for chunk in raw_watchlist.split(","):
        symbol = sanitize_symbol(chunk)
        if symbol not in seen:
            unique.append(symbol)
            seen.add(symbol)
    return unique or ["MSFT"]


def effective_period(period: str, interval: str) -> str:
    if interval in {"5m", "15m", "30m"} and period not in {"5d", "10d", "30d", "60d"}:
        return "60d"
    return period


def default_settings() -> UISettings:
    return UISettings(watchlist=["MSFT", "AAPL", "GOOGL"])


def load_settings() -> UISettings:
    defaults = default_settings()
    stored = st.session_state.get("ui_settings")
    if not isinstance(stored, dict):
        return defaults
    data = asdict(defaults)
    data.update(stored)
    data["watchlist"] = [sanitize_symbol(symbol) for symbol in data.get("watchlist", defaults.watchlist)]
    data["period"] = effective_period(str(data["period"]), str(data["interval"]))
    return UISettings(**data)


def save_settings(settings: UISettings) -> None:
    st.session_state.ui_settings = asdict(settings)


def render_sidebar_shell(settings: UISettings) -> None:
    with st.sidebar:
        st.markdown("""<div class="qe-brand"><div class="qe-brand-mark" aria-hidden="true">Q</div><div><div class="qe-brand-title">QuantEdge Lab</div><div class="qe-brand-subtitle">AI market research · paper execution</div></div></div>""", unsafe_allow_html=True)
        st.caption("PAPER ENVIRONMENT")
        st.markdown(f"**{len(settings.watchlist)} symbols** · {settings.interval} · {settings.period}")
        st.caption(", ".join(settings.watchlist))
        st.divider()
        st.caption("No brokerage connection. All executions remain simulated.")


def render_settings_form(settings: UISettings) -> UISettings:
    st.info(
        f"Portfolio universe: {', '.join(settings.watchlist)} · starting paper capital ${settings.starting_cash:,.0f}. "
        "Use Portfolio Configuration below this form to change symbols, allocations, cash reserve, or starting capital."
    )
    row = st.columns(3)
    periods = ["5d", "10d", "30d", "60d", "3mo", "6mo"]
    intervals = ["5m", "15m", "30m", "1h"]
    period = row[0].selectbox("History window", periods, index=periods.index(settings.period if settings.period in periods else "60d"))
    interval = row[1].selectbox("Bar interval", intervals, index=intervals.index(settings.interval))
    horizon = row[2].slider("Forecast horizon", 1, 48, settings.horizon, help="Bars ahead represented by the prediction target.")
    st.markdown("#### Signal thresholds")
    signal = st.columns(2)
    buy_threshold = signal[0].slider("Buy threshold (%)", 0.1, 10.0, settings.buy_threshold * 100.0, 0.1) / 100.0
    sell_threshold = -(signal[1].slider("Sell threshold (%)", 0.1, 10.0, abs(settings.sell_threshold) * 100.0, 0.1) / 100.0)
    st.markdown("#### Transaction assumptions")
    costs = st.columns(2)
    commission_rate = costs[0].number_input("Commission rate", min_value=0.0, max_value=0.05, value=float(settings.commission_rate), step=0.0005, format="%.4f")
    slippage_rate = costs[1].number_input("Slippage rate", min_value=0.0, max_value=0.05, value=float(settings.slippage_rate), step=0.0005, format="%.4f")
    st.markdown("#### Position exits")
    risk = st.columns(3)
    automation_enabled = risk[0].toggle("Enable stop / target exits", value=settings.automation_enabled)
    stop_loss_pct = risk[1].slider("Stop-loss (%)", 0.5, 20.0, settings.stop_loss_pct, 0.5)
    take_profit_pct = risk[2].slider("Take-profit (%)", 0.5, 30.0, settings.take_profit_pct, 0.5)
    return UISettings(
        watchlist=list(settings.watchlist),
        period=effective_period(period, interval),
        interval=interval,
        horizon=int(horizon),
        buy_threshold=float(buy_threshold),
        sell_threshold=float(sell_threshold),
        starting_cash=float(settings.starting_cash),
        commission_rate=float(commission_rate),
        slippage_rate=float(slippage_rate),
        automation_enabled=bool(automation_enabled),
        stop_loss_pct=float(stop_loss_pct),
        take_profit_pct=float(take_profit_pct),
    )
