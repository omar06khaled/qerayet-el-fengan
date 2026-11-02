import { useCallback, useEffect, useState } from "react";
import { api, type Account, type Bar, type Position, type Quote, type Status } from "./api";
import { LineChart } from "./LineChart";
import { OrderTicket } from "./OrderTicket";
import { BacktestLab } from "./BacktestLab";
import { ARABIC, count, money, pct, price, signedMoney, tone } from "./format";

const RANGES = [
  { label: "3M", days: 91 },
  { label: "6M", days: 182 },
  { label: "1Y", days: 365 },
];

export default function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [account, setAccount] = useState<Account | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [symbol, setSymbol] = useState("COMI");
  const [range, setRange] = useState(182);
  const [bars, setBars] = useState<Bar[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadPortfolio = useCallback(async () => {
    try {
      const [a, p] = await Promise.all([api.account(), api.positions()]);
      setAccount(a);
      setPositions(p);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    Promise.all([api.status(), api.symbols()])
      .then(([s, q]) => { setStatus(s); setQuotes(q); })
      .catch(() => setError("Can't reach the Sahm API on port 8000. Start it with: younit-dashboard"));
    loadPortfolio();
  }, [loadPortfolio]);

  useEffect(() => {
    api.history(symbol, range).then((h) => setBars(h.bars)).catch((e) => setError(e.message));
  }, [symbol, range]);

  const quote = quotes.find((q) => q.symbol === symbol);
  const pnl = positions.reduce((s, p) => s + p.unrealized_pnl, 0);
  const rangeReturn = bars.length > 1 ? 100 * (bars[bars.length - 1].close / bars[0].close - 1) : 0;

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="mark" lang="ar">سهم</span>
          <span className="brand-name">Sahm</span>
          <span className="brand-sub">A strategy lab for the EGX</span>
        </div>
        {account && (
          <dl className="figures">
            <div><dt>Account value</dt><dd>{money(account.equity)}</dd></div>
            <div><dt>Cash</dt><dd>{money(account.cash)}</dd></div>
            <div><dt>Open gain or loss</dt><dd className={tone(pnl)}>{signedMoney(pnl)} EGP</dd></div>
          </dl>
        )}
      </header>

      {status?.synthetic && (
        <p className="notice" role="note">
          Demo data. Prices are generated, not real EGX quotes, and nothing here is connected to Younit or EFG Hermes yet.
          {status.trading_enabled ? " Mock trading is on." : " Order placement is off."}
        </p>
      )}
      {status && !status.synthetic && (
        <p className={`notice${status.real_money ? " live" : ""}`} role="note">
          {status.real_money
            ? "Connected to your real Younit account. Orders use real money."
            : "Connected to Younit's simulation environment. Orders are paper trades."}
          {status.trading_enabled ? " Order placement is on." : " Order placement is off."}
        </p>
      )}
      {error && <p className="error banner" role="alert">{error}</p>}

      <main className="grid">
        <aside className="side">
          <section className="panel watch-panel" aria-labelledby="watch-h">
            <h2 id="watch-h">EGX stocks</h2>
            <ul className="watch">
              {quotes.map((q) => (
                <li key={q.symbol}>
                  <button className={q.symbol === symbol ? "sel" : ""} aria-pressed={q.symbol === symbol}
                    onClick={() => setSymbol(q.symbol)}>
                    <span className="w-sym">{q.symbol}</span>
                    <span className="w-name">{q.name}</span>
                    <span className="w-last">{price(q.last)}</span>
                    <span className={`w-chg ${tone(q.change_pct)}`}>{pct(q.change_pct)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
          {quote && status && (
            <OrderTicket key={symbol} quote={quote} tradingEnabled={status.trading_enabled}
              maxOrder={status.max_order_egp} onPlaced={loadPortfolio} />
          )}
        </aside>

        <div className="main">
          {quote && (
            <section className="panel stage" aria-labelledby="stage-h">
              <div className="stage-head">
                <h1 id="stage-h" className="ticker">
                  <span className="t-latin">{quote.symbol}</span>
                  <span className="t-arabic" lang="ar" dir="rtl">{ARABIC[quote.symbol]}</span>
                </h1>
                <div className="stage-price">
                  <span className="big">{price(quote.last)}</span>
                  <span className="unit">EGP</span>
                  <span className={`chg ${tone(quote.change_pct)}`}>{pct(quote.change_pct)} today</span>
                </div>
              </div>
              <div className="stage-bar">
                <p className="hint">{quote.name}. Over this range: <span className={tone(rangeReturn)}>{pct(rangeReturn)}</span></p>
                <div className="segmented small" role="radiogroup" aria-label="Chart range">
                  {RANGES.map((r) => (
                    <button key={r.label} role="radio" aria-checked={range === r.days}
                      className={range === r.days ? "on" : ""} onClick={() => setRange(r.days)}>
                      {r.label}
                    </button>
                  ))}
                </div>
              </div>
              {bars.length > 1 && (
                <LineChart
                  label={`${quote.symbol} daily closing price`}
                  days={bars.map((b) => b.day)}
                  series={[{ name: "Close", color: "var(--lapis)", values: bars.map((b) => b.close) }]}
                  format={(v) => v.toFixed(2)}
                  height={300}
                />
              )}
            </section>
          )}

          <section className="panel holdings" aria-labelledby="pos-h">
            <h2 id="pos-h">Your holdings</h2>
            {positions.length === 0 ? (
              <p className="hint">No holdings yet. Pick a stock and review a buy order to start.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Stock</th><th className="num">Shares</th><th className="num">Avg cost</th>
                      <th className="num">Last</th><th className="num">Value</th><th className="num">Gain or loss</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((p) => (
                      <tr key={p.symbol}>
                        <td><button className="linkish" onClick={() => setSymbol(p.symbol)}>{p.symbol}</button></td>
                        <td className="num">{count(p.quantity)}</td>
                        <td className="num">{price(p.avg_cost)}</td>
                        <td className="num">{price(p.last_price)}</td>
                        <td className="num">{price(p.market_value)}</td>
                        <td className={`num ${tone(p.unrealized_pnl)}`}>
                          {signedMoney(p.unrealized_pnl)} <small>{pct(p.unrealized_pnl_pct)}</small>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <BacktestLab symbol={symbol} />
        </div>
      </main>

      <footer className="foot">
        Independent open-source project. Not affiliated with or endorsed by EFG Hermes. Backtests are simulations, not advice.
      </footer>
    </div>
  );
}
