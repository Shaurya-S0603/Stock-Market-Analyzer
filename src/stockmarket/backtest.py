from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .signals import make_signal
from .trading import PaperPortfolio


def _buy_hold_return_pct(bars: pd.DataFrame, commission_rate: float, slippage_rate: float) -> float:
    if len(bars)<2: return 0.0
    entry=float(bars["Open"].iloc[1])*(1.0+slippage_rate); exit_price=float(bars["Close"].iloc[-1])*(1.0-slippage_rate)
    return (exit_price*(1.0-commission_rate)/(entry*(1.0+commission_rate))-1.0)*100.0


def run_backtest(symbol:str,bars:pd.DataFrame,predicted_returns:pd.Series,starting_cash:float=100_000.0,commission_rate:float=0.001,slippage_rate:float=0.0005,buy_threshold:float=0.005,sell_threshold:float=-0.005)->dict:
    symbol=symbol.strip().upper()
    if not symbol: raise ValueError("symbol must not be empty")
    if len(bars)!=len(predicted_returns): raise ValueError("bars and predictions must have equal length")
    if len(bars)<2: raise ValueError("At least two bars are required for backtesting")
    if not bars.index.equals(predicted_returns.index): predicted_returns=predicted_returns.reindex(bars.index)
    if predicted_returns.isna().any(): raise ValueError("predicted_returns must align to all backtest bars")
    portfolio=PaperPortfolio(starting_cash,commission_rate,slippage_rate); equity_points=[]; equity_index=[]; trades=0; gross_turnover=0.0; exposed_points=0
    for index in range(len(bars)-1):
        next_bar=bars.iloc[index+1]
        signal=make_signal(float(predicted_returns.iloc[index]),buy_threshold=buy_threshold,sell_threshold=sell_threshold,round_trip_cost=commission_rate*2+slippage_rate*2)
        position=portfolio.positions.get(symbol)
        if signal.action=="Buy" and (position is None or position.quantity==0):
            quantity=max(int(portfolio.cash*0.10/float(next_bar["Open"])),0)
            if quantity:
                fill=portfolio.execute(symbol,"buy",quantity,float(next_bar["Open"]),bars.index[index+1],reason="backtest_buy"); gross_turnover+=fill.price*fill.quantity; trades+=1
        elif signal.action=="Sell" and position and position.quantity:
            fill=portfolio.execute(symbol,"sell",position.quantity,float(next_bar["Open"]),bars.index[index+1],reason="backtest_sell"); gross_turnover+=fill.price*fill.quantity; trades+=1
        position_after=portfolio.positions.get(symbol)
        if position_after and position_after.quantity>0: exposed_points+=1
        equity_points.append(portfolio.equity({symbol:float(next_bar["Close"])})); equity_index.append(bars.index[index+1])
    equity_series=pd.Series(equity_points,index=equity_index,dtype=float); peak=equity_series.cummax(); drawdown=(equity_series/peak-1.0).fillna(0.0)
    period_returns=equity_series.pct_change().replace([np.inf,-np.inf],np.nan).dropna(); volatility=float(period_returns.std(ddof=0)) if len(period_returns) else 0.0
    risk_adjusted_score=float(period_returns.mean()/volatility*math.sqrt(len(period_returns))) if volatility>0.0 and len(period_returns) else 0.0
    exit_fills=[fill for fill in portfolio.fills if fill.side=="sell"]; profitable_exits=sum(fill.realized_pnl>0 for fill in exit_fills)
    hit_rate_pct=(profitable_exits/len(exit_fills)*100.0) if exit_fills else 0.0; average_equity=float(equity_series.mean()) if len(equity_series) else starting_cash
    turnover_pct=gross_turnover/max(average_equity,1e-12)*100.0; exposure_pct=exposed_points/max(len(equity_series),1)*100.0
    total_return_pct=float((equity_series.iloc[-1]/starting_cash-1.0)*100.0) if len(equity_series) else 0.0; buy_hold_return_pct=_buy_hold_return_pct(bars,commission_rate,slippage_rate); final_price=float(bars["Close"].iloc[-1])
    return {"equity_curve":equity_series,"summary":{"total_return_pct":total_return_pct,"max_drawdown_pct":float(drawdown.min()*100.0) if len(drawdown) else 0.0,"trades":trades,"round_trips":len(exit_fills),"hit_rate_pct":hit_rate_pct,"turnover_pct":turnover_pct,"exposure_pct":exposure_pct,"risk_adjusted_score":risk_adjusted_score,"return_volatility":volatility,"buy_hold_return_pct":buy_hold_return_pct,"excess_vs_buy_hold_pct":total_return_pct-buy_hold_return_pct,"final":portfolio.summary({symbol:final_price})}}
