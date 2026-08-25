from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import Settings
from .backtest import run_backtest
from .data import MarketDataError, YahooFinanceProvider
from .features import build_features
from .modeling import train_model
from .storage import Store
from .trading import PaperPortfolio, TradingError


def create_app(provider=None, database_path="paper_trading.db") -> FastAPI:
    settings = Settings.from_environment()
    settings.validate()
    market = provider or YahooFinanceProvider()
    portfolio = PaperPortfolio(settings.starting_cash, settings.commission_rate, settings.slippage_rate)
    store = Store(database_path)
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))
    app = FastAPI(title="Paper Market Lab")
    app.state.portfolio = portfolio
    app.state.store = store

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        try:
            data = market.fetch(settings.symbol, settings.period, settings.interval)
            price = float(data["Close"].iloc[-1])
            error = None
        except MarketDataError as exc:
            price, error = None, str(exc)
        return templates.TemplateResponse("dashboard.html", {"request": request, "symbol": settings.symbol, "price": price, "portfolio": portfolio.summary({settings.symbol: price} if price else {}), "orders": store.orders(), "error": error})

    @app.get("/api/portfolio")
    def portfolio_state():
        try:
            data = market.fetch(settings.symbol, settings.period, settings.interval)
            prices = {settings.symbol: float(data["Close"].iloc[-1])}
        except MarketDataError:
            prices = {}
        return portfolio.summary(prices)

    @app.get("/api/quote/{symbol}")
    def quote(symbol: str):
        data = market.fetch(symbol.upper(), settings.period, settings.interval, minimum_rows=1)
        return {"symbol": symbol.upper(), "price": float(data["Close"].iloc[-1]), "timestamp": data.index[-1].isoformat()}

    @app.post("/orders")
    def order(request: Request, symbol: str = Form(...), side: str = Form(...), quantity: int = Form(...), price: float = Form(...)):
        try:
            fill = portfolio.execute(symbol, side, quantity, price)
            store.add_order(symbol.upper(), fill.side, fill.quantity, fill.price, fill.fee)
            return RedirectResponse("/", status_code=303)
        except TradingError as exc:
            return templates.TemplateResponse("dashboard.html", {"request": request, "symbol": settings.symbol, "price": price, "portfolio": portfolio.summary({}), "orders": store.orders(), "error": str(exc)}, status_code=400)

    @app.post("/api/train")
    def train():
        data = market.fetch(settings.symbol, settings.period, settings.interval)
        features = build_features(data, settings.horizon)
        result = train_model(features)
        store.add_model_run(settings.symbol, result.metrics)
        return {"symbol": settings.symbol, "metrics": result.metrics}

    @app.post("/api/backtest")
    def backtest():
        data = market.fetch(settings.symbol, settings.period, settings.interval)
        features = build_features(data, settings.horizon)
        result = train_model(features)
        split = int(len(features) * 0.8)
        test_features = features.iloc[split:]
        report = run_backtest(settings.symbol, data.loc[test_features.index], pd.Series(result.predict(test_features), index=test_features.index), settings.starting_cash, settings.commission_rate, settings.slippage_rate)
        return {"symbol": settings.symbol, "summary": report["summary"]}

    return app


app = create_app()
