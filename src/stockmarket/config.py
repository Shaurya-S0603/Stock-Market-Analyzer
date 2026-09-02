from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    symbol: str = "MSFT"
    period: str = "60d"
    interval: str = "1h"
    horizon: int = 6
    starting_cash: float = 100_000.0
    commission_rate: float = 0.001
    slippage_rate: float = 0.0005
    buy_threshold: float = 0.003
    sell_threshold: float = -0.004

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            symbol=os.getenv("STOCK_SYMBOL", cls.symbol).upper(),
            period=os.getenv("STOCK_PERIOD", cls.period),
            interval=os.getenv("STOCK_INTERVAL", cls.interval),
            horizon=int(os.getenv("FORECAST_HORIZON", cls.horizon)),
            starting_cash=float(os.getenv("STARTING_CASH", cls.starting_cash)),
            commission_rate=float(os.getenv("COMMISSION_RATE", cls.commission_rate)),
            slippage_rate=float(os.getenv("SLIPPAGE_RATE", cls.slippage_rate)),
            buy_threshold=float(os.getenv("BUY_THRESHOLD", cls.buy_threshold)),
            sell_threshold=float(os.getenv("SELL_THRESHOLD", cls.sell_threshold)),
        )

    def validate(self) -> None:
        if not self.symbol or self.horizon < 1:
            raise ValueError("symbol and horizon must be valid")
        if self.starting_cash <= 0:
            raise ValueError("starting_cash must be positive")
        if not 0 <= self.commission_rate < 1 or not 0 <= self.slippage_rate < 1:
            raise ValueError("commission and slippage rates must be between 0 and 1")
        if self.sell_threshold >= self.buy_threshold:
            raise ValueError("sell_threshold must be below buy_threshold")
