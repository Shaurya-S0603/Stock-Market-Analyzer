"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PriceChart } from "./price-chart";
import type { OhlcvResponse } from "@/lib/contracts";

type Period = "3mo" | "6mo" | "1y";

export function HistoricalExplorer() {
  const [draft, setDraft] = useState("MSFT");
  const [period, setPeriod] = useState<Period>("6mo");
  const [submitted, setSubmitted] = useState<{ symbol: string; period: Period } | null>(null);
  const history = useQuery({
    queryKey: ["research-history", submitted?.symbol, submitted?.period],
    enabled: submitted !== null,
    retry: false,
    queryFn: async (): Promise<OhlcvResponse> => {
      if (!submitted) throw new Error("Choose a ticker");
      const params = new URLSearchParams({ period: submitted.period });
      const response = await fetch(
        "/api/v1/market/" + encodeURIComponent(submitted.symbol) + "/ohlcv?" + params,
        { cache: "no-store" },
      );
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error("Real historical data is disabled. Enable the opt-in local adapter first.");
        }
        throw new Error("Historical provider unavailable (" + response.status + "). No prices were fabricated.");
      }
      return response.json() as Promise<OhlcvResponse>;
    },
  });
  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const symbol = draft.trim().toUpperCase();
    if (!/^[A-Z0-9][A-Z0-9.^=-]{0,14}$/.test(symbol) || symbol === "QEDMO") {
      setSubmitted(null);
      return;
    }
    setSubmitted({ symbol, period });
  }
  const result = history.data;
  return <div className="space-y-6">
    <header>
      <p className="label">Phase 1A · historical market data (local opt-in)</p>
      <h1 className="mt-2 text-3xl font-bold">Historical market explorer</h1>
      <p className="mt-3 max-w-3xl text-slate-400">
        Read-only daily prices from an unofficial free historical provider.
        Data may be delayed, stale or incomplete. No live quote, broker connectivity or trading.
      </p>
    </header>
    <form onSubmit={submit} className="panel flex flex-wrap items-end gap-4 p-5">
      <label className="flex flex-col gap-2 text-sm">Ticker
        <input aria-label="Ticker" value={draft} onChange={event => setDraft(event.target.value)}
          maxLength={15} className="rounded-lg border border-slate-600 bg-slate-950 px-4 py-3"
          placeholder="e.g. MSFT" required />
      </label>
      <label className="flex flex-col gap-2 text-sm">History window
        <select aria-label="History window" value={period} onChange={event => setPeriod(event.target.value as Period)}
          className="rounded-lg border border-slate-600 bg-slate-950 px-4 py-3">
          <option value="3mo">3 months</option><option value="6mo">6 months</option>
          <option value="1y">1 year</option>
        </select>
      </label>
      <button type="submit" className="rounded-lg bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-500">
        Load historical candles
      </button>
    </form>
    {history.isPending && submitted && <p role="status">Loading historical research data…</p>}
    {history.isError && <p className="panel p-5 text-amber-300" role="alert">{history.error.message}</p>}
    {result && !result.provenance.fictional && <section className="panel p-5">
      <h2 className="text-xl font-semibold">{result.symbol} · historical daily candles</h2>
      <p className="mt-2 text-sm text-slate-300">
        Source: {result.provenance.provider} · Latest session label: {result.bars.at(-1)?.time} ·
        Retrieved: {result.provenance.retrieved_at ?? "unknown"}
      </p>
      <PriceChart bars={result.bars} sma={[]} showSma={false}
        ariaLabel="Historical daily candlestick chart, delayed or cached data" />
      <p className="mt-3 text-sm text-amber-300">{result.warning}</p>
      <p className="mt-2 text-xs text-slate-400">
        Adjustment: {result.provenance.adjustment}. {result.provenance.delay}
      </p>
    </section>}
    <p className="text-xs text-slate-500">
      The historical adapter is disabled by default. Set QUANTEDGE_ENABLE_HISTORICAL_RESEARCH=1
      for controlled local development; public deployment requires durable caching,
      throttling, authorization for saved data, and provider terms review.
    </p>
  </div>;
}
