"""Phase 2 graphical and research integration tests, no live provider dependency."""
import pandas as pd
import numpy as np
import pytest

from stockmarket.workspace.charting import build_chart
from stockmarket.workspace.fundamentals import fetch_company_research, _extract_news


def candles():
    x = np.arange(90, dtype=float)
    close = 100 + .2 * x + np.sin(x)
    return pd.DataFrame({"open": close - .5, "high": close+1, "low": close-1,
                         "close": close, "volume": 500 + x},
                        index=pd.date_range("2026-01-01", periods=90, freq="h", tz="UTC"))


def test_chart_generates_volume_and_indicator_panels():
    chart = build_chart(candles(), {
        "symbol":"AAPL", "interval":"1h", "chart_type":"Candles", "indicators":
        ["SMA", "Bollinger", "RSI", "MACD", "Stochastic", "VWAP"],
        "volume":True, "length":20,
    })
    names = {trace.name for trace in chart.data}
    assert "Price" in names
    assert "SMA 20" in names
    assert "MACD Histogram" in names
    assert "UTC-date VWAP" in names
    assert "RSI 14" in names
    assert "Volume" in names


def test_daily_vwap_is_rejected_not_mislabeled():
    with pytest.raises(ValueError, match="intraday"):
        build_chart(candles(), {"symbol":"AAPL", "interval":"1d", "indicators":["VWAP"]})


def test_research_normalizes_old_and_new_article_shapes():
    class Dummy:
        info = {"longName":"Example Inc", "marketCap":1000, "profitMargins":0.1,
                "forwardPE":float("nan"), "website":"javascript:bad", "sector":"Technology"}
        news = [
            {"title":"Old format", "link":"https://example.com/article", "providerPublishTime":1},
            {"content":{"title":"New format", "provider":{"displayName":"Publisher"},
                        "canonicalUrl":{"url":"https://example.com/news"},
                        "pubDate":"2026-10-01T12:00:00Z"}},
            {"title":"Unsafe", "link":"javascript:alert(1)"},
        ]
    result = fetch_company_research("MSFT", ticker_factory=lambda s:Dummy())
    assert result["profile"]["Company"] == "Example Inc"
    assert "Website" not in result["profile"]
    assert result["fundamentals"]["Market capitalization"] == 1000
    assert "Forward P/E" not in result["fundamentals"]
    assert len(result["news"]) == 2
    assert all(item["URL"].startswith("https://") for item in result["news"])


def test_provider_errors_are_reported_as_unavailable():
    class Broken:
        @property
        def info(self):
            raise RuntimeError("offline")
        @property
        def news(self):
            raise RuntimeError("offline")
    report = fetch_company_research("MSFT", ticker_factory=lambda s: Broken())
    assert not report["profile"] and not report["news"]
    assert report["warnings"]
