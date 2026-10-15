"""Unified research navigation, dashboard and trade marker visuals."""
import pandas as pd
import numpy as np
from streamlit.testing.v1 import AppTest

from stockmarket.workspace.charting import build_chart
from stockmarket.workspace.strategy_pages import monthly_return_table


def sample():
    prices=np.linspace(90,100,40)
    return pd.DataFrame({"open":prices,"high":prices+1,"low":prices-1,
                         "close":prices,"volume":np.full(40,900.)},
                        index=pd.date_range("2026-01-01",periods=40,freq="D",tz="UTC"))


def test_trade_markers_render_on_price_panel():
    history=sample()
    fig=build_chart(history,{"symbol":"MSFT","interval":"1d","indicators":["SMA"]},
        markers=[
            {"side":"buy","timestamp":history.index[15].isoformat(),"price":95.},
            {"side":"sell","timestamp":history.index[25].isoformat(),"price":97.},
            {"side":"sell","timestamp":"2024-01-01T00:00:00Z","price":99.},
            {"side":"buy","timestamp":"invalid","price":0.},
        ])
    names=[item.name for item in fig.data]
    assert "Simulated BUY" in names and "Simulated SELL" in names
    assert len(next(item for item in fig.data if item.name=="Simulated SELL").x)==1


def test_monthly_return_uses_first_month_starting_cash():
    series=[
        {"timestamp":"2026-01-05T00:00:00Z","equity":100.},
        {"timestamp":"2026-01-31T00:00:00Z","equity":110.},
        {"timestamp":"2026-02-28T00:00:00Z","equity":99.},
    ]
    data=monthly_return_table(series,100.)
    assert data["Return %"].to_list()==[10.,-10.]


def test_dashboard_works_on_new_install_without_onboarding(tmp_path,monkeypatch):
    monkeypatch.setenv("QUANTEDGE_WORKSPACE_DB",str(tmp_path/"fresh.db"))
    app=AppTest.from_string(
        "from stockmarket.workspace.home import personal_dashboard_page\n"
        "personal_dashboard_page()\n",default_timeout=25).run()
    assert not app.exception
