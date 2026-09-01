from stockmarket.config import Settings
from stockmarket.ui.sidebar import UISettings, effective_period


def test_primary_research_defaults_use_hourly_recent_history() -> None:
    config = Settings()
    ui = UISettings(watchlist=["MSFT"])
    assert config.period == "60d"
    assert config.interval == "1h"
    assert config.horizon == 6
    assert ui.period == "60d"
    assert ui.interval == "1h"
    assert ui.horizon == 6


def test_intraday_period_normalization_rejects_long_history() -> None:
    assert effective_period("6mo", "1h") == "60d"
    assert effective_period("3mo", "30m") == "60d"
    assert effective_period("60d", "1h") == "60d"
