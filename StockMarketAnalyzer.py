import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from stockmarket.config import Settings
from stockmarket.data import MarketDataError, YahooFinanceProvider
from stockmarket.features import build_features


def main() -> None:
    settings = Settings.from_environment()
    settings.validate()
    try:
        data = YahooFinanceProvider().fetch(settings.symbol, settings.period, settings.interval)
        features = build_features(data, settings.horizon)
    except (MarketDataError, ValueError) as exc:
        print(f"Analysis unavailable: {exc}")
        return
    latest = features.iloc[-1]
    print(f"{settings.symbol}: {len(features)} usable rows through {features.index[-1]}")
    print(f"Latest close: {latest['Close']:.2f}")
    print("Feature pipeline ready. Start the paper-trading app for model training and backtesting.")


if __name__ == "__main__":
    main()

