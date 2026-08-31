from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import Settings
from .data import MarketDataError, YahooFinanceProvider
from .services import AnalysisRequest, AnalysisService, PortfolioService
from .storage import Store
from .trading import PaperPortfolio, TradingError


def _analysis_request(settings:Settings)->AnalysisRequest:
    return AnalysisRequest(settings.period,settings.interval,settings.horizon,settings.buy_threshold,settings.sell_threshold,settings.commission_rate,settings.slippage_rate)


def create_app(provider=None,database_path=".data/paper_trading.db")->FastAPI:
    settings=Settings.from_environment(); settings.validate(); market=provider or YahooFinanceProvider(); analysis_service=AnalysisService(market); request_config=_analysis_request(settings)
    portfolio=PaperPortfolio(settings.starting_cash,settings.commission_rate,settings.slippage_rate); store=Store(database_path); portfolio_service=PortfolioService(portfolio,store)
    templates=Jinja2Templates(directory=str(Path(__file__).resolve().parents[2]/"templates")); app=FastAPI(title="Stock Market Analyzer API",version="0.3.0"); app.state.portfolio=portfolio; app.state.store=store

    @app.get("/",response_class=HTMLResponse)
    def dashboard(request:Request):
        try: data=market.fetch(settings.symbol,settings.period,settings.interval); price=float(data["Close"].iloc[-1]); error=None
        except MarketDataError as exc: price,error=None,str(exc)
        return templates.TemplateResponse("dashboard.html",{"request":request,"symbol":settings.symbol,"price":price,"portfolio":portfolio.summary({settings.symbol:price} if price else {}),"orders":store.orders(),"error":error})

    @app.get("/api/portfolio")
    def portfolio_state():
        try: data=market.fetch(settings.symbol,settings.period,settings.interval); prices={settings.symbol:float(data["Close"].iloc[-1])}
        except MarketDataError: prices={}
        return portfolio.summary(prices)

    @app.get("/api/quote/{symbol}")
    def quote(symbol:str):
        normalized=symbol.strip().upper(); data=market.fetch(normalized,settings.period,settings.interval,minimum_rows=1)
        return {"symbol":normalized,"price":float(data["Close"].iloc[-1]),"timestamp":data.index[-1].isoformat()}

    @app.post("/orders")
    def order(request:Request,symbol:str=Form(...),side:str=Form(...),quantity:int=Form(...),price:float=Form(...)):
        try: portfolio_service.execute(symbol,side,quantity,price); return RedirectResponse("/",status_code=303)
        except TradingError as exc:
            try: data=market.fetch(settings.symbol,settings.period,settings.interval,minimum_rows=1); current_price=float(data["Close"].iloc[-1])
            except MarketDataError: current_price=None
            return templates.TemplateResponse("dashboard.html",{"request":request,"symbol":settings.symbol,"price":current_price,"portfolio":portfolio.summary({settings.symbol:current_price} if current_price else {}),"orders":store.orders(),"error":str(exc)},status_code=400)

    @app.post("/api/train")
    def train():
        analysis=analysis_service.analyze_symbol(settings.symbol,request_config); store.add_model_run(settings.symbol,analysis.model.metrics); benchmark_rows,gate=analysis_service.benchmark_report(analysis)
        return {"symbol":settings.symbol,"metrics":analysis.model.metrics,"model_gate":{"approved":gate.approved,"reason":gate.reason,"rmse_improvement_vs_best_baseline":gate.rmse_improvement_vs_best_baseline},"benchmarks":benchmark_rows}

    @app.post("/api/backtest")
    def backtest():
        analysis=analysis_service.analyze_symbol(settings.symbol,request_config); report=analysis_service.backtest(analysis,request_config,settings.starting_cash)
        return {"symbol":settings.symbol,"summary":report["summary"]}

    return app


app=create_app()
