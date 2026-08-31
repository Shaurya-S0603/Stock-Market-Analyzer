import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parent/"src"))

from stockmarket.config import Settings
from stockmarket.data import MarketDataError, YahooFinanceProvider
from stockmarket.features import build_features


def main()->None:
    settings=Settings.from_environment(); settings.validate()
    try:
        data=YahooFinanceProvider().fetch(settings.symbol,settings.period,settings.interval)
        training=build_features(data,settings.horizon,include_target=True); live=build_features(data,settings.horizon,include_target=False)
    except (MarketDataError,ValueError) as exc:
        print(f"Analysis unavailable: {exc}"); return
    print(f"{settings.symbol}: {len(training)} labeled rows; {len(live)} live-feature rows")
    print(f"Latest market bar: {data.index[-1]} · close {float(data['Close'].iloc[-1]):.2f}")
    print(f"Latest feature row: {live.index[-1]}")
    print("Pipeline ready. Run `streamlit run streamlit_app.py` for the full research interface.")


if __name__=="__main__": main()
