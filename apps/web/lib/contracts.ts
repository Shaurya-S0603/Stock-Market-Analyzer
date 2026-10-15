export type OhlcvBar = { time: string; timestamp: string; open: number; high: number; low: number; close: number; volume: number };
export type OhlcvResponse = { symbol: string; interval: string; bars: OhlcvBar[]; provenance: { provider: string; fictional: boolean; adjustment: string; as_of: string; latest_bar_complete: boolean }; warning: string };
export type IndicatorPoint = { time: string; value: number };
export type IndicatorResponse = { symbol: string; period: number; fictional: boolean; indicators: Record<"sma" | "ema" | "rsi", IndicatorPoint[]> };
export type HealthResponse = { status: string; service: string; api_version: string; market_mode: string; database: string; brokerage: string };
export type DemoBacktestResponse = { symbol: string; fictional: boolean; strategy: string; metrics: { total_return_pct: number; max_drawdown_pct: number; trade_count: number; buy_hold_return_pct: number; final_equity: number; sharpe: number | null }; equity: Array<{ time: string; equity: number; drawdown_pct: number }>; trades: Array<{ entry_at: string; exit_at: string; net_pnl: number }>; warning: string };
