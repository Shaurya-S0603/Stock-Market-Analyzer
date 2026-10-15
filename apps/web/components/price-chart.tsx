"use client";
import { useEffect, useRef } from "react";
import {
  CandlestickSeries, ColorType, createChart, HistogramSeries, LineSeries,
  type CandlestickData, type Time,
} from "lightweight-charts";
import type { IndicatorPoint, OhlcvBar } from "@/lib/contracts";

export function PriceChart({ bars, sma, showSma, ariaLabel = "Fictional daily candlestick chart with crosshair and optional moving average" }: {
  bars: OhlcvBar[];
  sma: IndicatorPoint[];
  showSma: boolean;
  ariaLabel?: string;
}) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!host.current || bars.length === 0) return;
    const element = host.current;
    const chart = createChart(element, {
      width: Math.max(320, element.clientWidth),
      height: 410,
      layout: {
        background: { type: ColorType.Solid, color: "#101a2b" },
        textColor: "#a4b4c9",
      },
      grid: { vertLines: { color: "#1b2a3e" }, horzLines: { color: "#1b2a3e" } },
      rightPriceScale: { borderColor: "#34445a" },
      timeScale: { borderColor: "#34445a", rightOffset: 3, timeVisible: false },
      crosshair: { mode: 1 },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#34d399", downColor: "#fb7185",
      borderUpColor: "#34d399", borderDownColor: "#fb7185",
      wickUpColor: "#34d399", wickDownColor: "#fb7185",
    });
    const points: CandlestickData<Time>[] = bars.map(row => ({
      time: row.time, open: row.open, high: row.high, low: row.low, close: row.close,
    }));
    candles.setData(points);
    if (showSma) {
      const average = chart.addSeries(LineSeries, { color: "#fbbf24", lineWidth: 2 });
      average.setData(sma.map(row => ({ time: row.time, value: row.value })));
    }
    chart.timeScale().fitContent();
    const resize = new ResizeObserver(entries => {
      if (entries.length) chart.applyOptions({ width: Math.max(320, entries[0].contentRect.width) });
    });
    resize.observe(element);
    return () => { resize.disconnect(); chart.remove(); };
  }, [bars, sma, showSma]);
  return <div ref={host} className="min-h-[410px] w-full" role="img"
    aria-label={ariaLabel}/>;
}
