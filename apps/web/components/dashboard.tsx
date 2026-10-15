"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { PriceChart } from "./price-chart";
import type {
  DemoBacktestResponse, HealthResponse, IndicatorResponse, OhlcvResponse,
} from "@/lib/contracts";

async function readJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to reach research API (" + response.status + ")");
  return response.json() as Promise<T>;
}

export function Dashboard() {
  const [showSma, setShowSma] = useState(true);
  const [startingCash, setStartingCash] = useState("10000");
  const health = useQuery({ queryKey: ["health"], queryFn: () => readJson<HealthResponse>("/api/v1/health") });
  const history = useQuery({ queryKey: ["ohlcv", "QEDMO"], queryFn: () => readJson<OhlcvResponse>("/api/v1/market/QEDMO/ohlcv") });
  const indicators = useQuery({ queryKey: ["indicators", "QEDMO", 20], queryFn: () => readJson<IndicatorResponse>("/api/v1/market/QEDMO/indicators?period=20") });
  const demo = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/v1/backtests/demo", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ starting_cash: Number(startingCash) }),
      });
      if (!response.ok) throw new Error("Demo backtest failed (" + response.status + ")");
      return response.json() as Promise<DemoBacktestResponse>;
    },
  });

  const last = history.data?.bars.at(-1);
  return <div className="space-y-7">
    <header className="flex flex-wrap justify-between gap-4">
      <div>
        <p className="label">Next.js + FastAPI · Phase 0</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Personal market terminal</h1>
        <p className="mt-3 max-w-2xl text-slate-400">
          A first working slice of the rebuilt trading-research app.
          The displayed QEDMO symbol is fictional, not an investable security.
        </p>
      </div>
      <div className="self-start rounded-full border border-blue-700/60 bg-blue-950/50 px-4 py-2 text-sm text-blue-300">
        {health.isLoading ? "Checking backend…" :
          health.data?.status === "ok" ? "● Research API connected" : "○ Research API unavailable"}
      </div>
    </header>

    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Fictional example summary">
      <div className="panel p-5"><p className="label">Practice symbol</p><p className="mt-2 text-2xl font-bold">QEDMO</p><p className="mt-2 text-sm text-slate-400">Synthetic dataset</p></div>
      <div className="panel p-5"><p className="label">Historical close</p><p className="mt-2 text-2xl font-bold">{last ? last.close.toFixed(2) : "—"}</p><p className="mt-2 text-sm text-slate-400">Fictional price units</p></div>
      <div className="panel p-5"><p className="label">Cached bars</p><p className="mt-2 text-2xl font-bold">{history.data?.bars.length ?? "—"}</p><p className="mt-2 text-sm text-slate-400">Completed historical days</p></div>
      <div className="panel p-5"><p className="label">Execution mode</p><p className="mt-2 text-2xl font-bold">Paper only</p><p className="mt-2 text-sm text-slate-400">No connected brokerage</p></div>
    </section>

    <section className="panel overflow-hidden" aria-label="Price chart">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 p-5">
        <div><h2 className="text-lg font-semibold">Fictional QEDMO · Daily candlesticks</h2>
          <p className="mt-1 text-xs text-slate-400">Crosshair, pan, zoom and 20-day SMA</p></div>
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showSma} onChange={e => setShowSma(e.target.checked)}
            className="h-4 w-4 accent-blue-500"/> Show SMA (20)
        </label>
      </div>
      <div className="p-4">
        {history.isLoading || indicators.isLoading ? <p className="p-10 text-slate-400">Loading historical chart…</p> :
          history.error || indicators.error ? <p className="p-10 text-rose-300">Chart unavailable. Start the FastAPI service and retry.</p> :
          history.data && indicators.data ?
          <PriceChart bars={history.data.bars} sma={indicators.data.indicators.sma} showSma={showSma}/> : null}
      </div>
      <p className="px-5 pb-5 text-xs text-amber-300">
        Data source: synthetic-tutorial. Not live data; no current quotes or exchange trading.
      </p>
    </section>

    <section className="panel p-6" aria-label="Demo backtesting">
      <p className="label">Python backtest engine · verification example</p>
      <h2 className="mt-2 text-xl font-semibold">Run a simulated strategy</h2>
      <p className="mt-2 text-sm text-slate-400">Uses the existing deterministic SMA/RSI example with next-bar fills, slippage and historical risk controls.</p>
      <div className="mt-5 flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-2 text-sm text-slate-300">
          Fictional starting cash
          <input aria-label="Starting cash" type="number" min="100" max="1000000" value={startingCash}
            onChange={e => setStartingCash(e.target.value)}
            className="w-48 rounded-lg border border-slate-600 bg-slate-950 px-4 py-3"/>
        </label>
        <button type="button" onClick={() => demo.mutate()} disabled={demo.isPending}
          className="rounded-lg bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-500">
          {demo.isPending ? "Simulating…" : "Run fictional backtest"}
        </button>
      </div>
      {demo.isError && <p className="mt-4 text-rose-300" role="alert">{demo.error.message}</p>}
      {demo.data && <div className="mt-6 space-y-4">
        <p className="text-sm text-slate-400">{demo.data.strategy}</p>
        <div className="grid gap-4 sm:grid-cols-4">
          <div><p className="label">Simulated return</p><strong className="text-xl">{demo.data.metrics.total_return_pct.toFixed(2)}%</strong></div>
          <div><p className="label">Buy & hold</p><strong className="text-xl">{demo.data.metrics.buy_hold_return_pct.toFixed(2)}%</strong></div>
          <div><p className="label">Max drawdown</p><strong className="text-xl">{demo.data.metrics.max_drawdown_pct.toFixed(2)}%</strong></div>
          <div><p className="label">Completed trades</p><strong className="text-xl">{demo.data.metrics.trade_count}</strong></div>
        </div>
        <p className="text-xs text-amber-300">{demo.data.warning}</p>
      </div>}
    </section>
    <p className="text-sm text-slate-500">This foundation deliberately has no live-money execution, user login or persistent shared account. Those features require authentication and database isolation in later stages.</p>
  </div>;
}
