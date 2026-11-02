export type Status = {
  source: string; synthetic: boolean; real_money: boolean; trading_enabled: boolean; max_order_egp: number;
};
export type Account = { account_id: string; currency: string; cash: number; equity: number; buying_power: number };
export type Position = {
  symbol: string; quantity: number; avg_cost: number; last_price: number;
  market_value: number; unrealized_pnl: number; unrealized_pnl_pct: number;
};
export type Quote = { symbol: string; name: string; last: number; change_pct: number; volume: number; as_of: string };
export type Bar = { day: string; open: number; high: number; low: number; close: number; volume: number };
export type CurvePoint = { day: string; strategy: number; buy_hold: number };
export type Trade = { entry: string; exit: string; return_pct: number };
export type BacktestResult = {
  strategy: string; strategy_name: string; symbol: string; start: string; end: string; trading_days: number;
  total_return_pct: number; buy_and_hold_return_pct: number; max_drawdown_pct: number;
  sharpe: number; trades: number; win_rate_pct: number; exposure_pct: number;
  trade_log: Trade[]; equity_curve: CurvePoint[];
};
export type ParamSpec = {
  key: string; label: string; default: number; min: number; max: number; step: number; integer: boolean; help: string;
};
export type StrategySpec = {
  id: string; name: string; summary: string; how: string; author: string; source: string; reference: string;
  params: ParamSpec[];
};
export type Catalog = { strategies: StrategySpec[]; load_errors: { file: string; error: string }[] };
export type SymbolScore = {
  symbol: string; in_sample_pct: number; in_sample_hold_pct: number; out_sample_pct: number;
  out_sample_hold_pct: number; out_sample_trades: number; out_sample_drawdown_pct: number;
  out_sample_start: string; beat_in_sample: boolean; beat_out_sample: boolean;
};
export type ReportCard = {
  strategy: string; strategy_name: string; split_pct: number;
  lookahead: { passed: boolean; cuts_tested: number; detail: string; first_bad_day: string | null };
  verdict: "holds_up" | "mixed" | "does_not_hold_up" | "too_few_trades" | "baseline" | "invalid" | "demo_data";
  headline: string; notes: string[]; symbols: SymbolScore[];
  beat_count: number; median_excess_pct: number; total_trades: number; luck_chance_pct: number;
};
export type Side = "buy" | "sell";
export type OrderType = "market" | "limit" | "stop";
export type OrderBody = {
  symbol: string; side: Side; quantity: number; order_type: OrderType;
  limit_price?: number; stop_price?: number;
};
export type Preview = {
  confirmation_token: string; summary: string; last_price: number;
  estimated_value_egp: number; expires_in_seconds: number; trading_enabled: boolean;
};
export type Order = {
  order_id: string; status: string; created_at: string; filled_price: number | null;
  request: OrderBody;
};

async function call<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status}).`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  status: () => call<Status>("/status"),
  account: () => call<Account>("/account"),
  positions: () => call<Position[]>("/positions"),
  symbols: () => call<Quote[]>("/symbols"),
  history: (symbol: string, days: number) => call<{ symbol: string; bars: Bar[] }>(`/history/${symbol}?days=${days}`),
  strategies: () => call<Catalog>("/strategies"),
  check: (b: { strategy: string; params: Record<string, number> }) => call<ReportCard>("/check", b),
  backtest: (b: { symbol: string; strategy: string; days: number; params: Record<string, number> }) =>
    call<BacktestResult>("/backtest", b),
  preview: (b: OrderBody) => call<Preview>("/orders/preview", b),
  confirm: (token: string) => call<Order>("/orders/confirm", { confirmation_token: token }),
  orders: () => call<Order[]>("/orders"),
};
