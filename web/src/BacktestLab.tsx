import { useEffect, useMemo, useState } from "react";
import { api, type BacktestResult, type Catalog, type ReportCard, type StrategySpec } from "./api";
import { LineChart } from "./LineChart";
import { ReportCardView } from "./ReportCardView";
import { pct, shortDate, tone } from "./format";

export function BacktestLab({ symbol }: { symbol: string }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [strategyId, setStrategyId] = useState("sma_cross");
  const [days, setDays] = useState(365);
  const [params, setParams] = useState<Record<string, string>>({});
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [card, setCard] = useState<ReportCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"run" | "check" | null>(null);

  useEffect(() => {
    api.strategies().then(setCatalog).catch((e) => setError((e as Error).message));
  }, []);

  const spec: StrategySpec | undefined = catalog?.strategies.find((s) => s.id === strategyId);
  const builtIn = useMemo(() => catalog?.strategies.filter((s) => s.source === "built-in") ?? [], [catalog]);
  const yours = useMemo(() => catalog?.strategies.filter((s) => s.source !== "built-in") ?? [], [catalog]);

  function readParams(): Record<string, number> | null {
    if (!spec) return null;
    const out: Record<string, number> = {};
    for (const p of spec.params) {
      const raw = params[p.key] ?? String(p.default);
      const n = Number(raw);
      if (raw.trim() === "" || Number.isNaN(n)) { setError(`${p.label} must be a number.`); return null; }
      if (n < p.min || n > p.max) { setError(`${p.label} must be between ${p.min} and ${p.max}.`); return null; }
      if (p.integer && !Number.isInteger(n)) { setError(`${p.label} must be a whole number.`); return null; }
      out[p.key] = n;
    }
    return out;
  }

  async function run(e?: React.FormEvent) {
    e?.preventDefault();
    setError(null);
    const p = readParams();
    if (!p) return;
    setBusy("run");
    try {
      setResult(await api.backtest({ symbol, strategy: strategyId, days, params: p }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function check() {
    setError(null);
    const p = readParams();
    if (!p) return;
    setBusy("check");
    setCard(null);
    try {
      setCard(await api.check({ strategy: strategyId, params: p }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  // Re-run when the stock or the library changes, so the lab always matches the chart above.
  useEffect(() => { if (catalog) run(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [symbol, catalog]);

  const curve = result?.equity_curve ?? [];
  const beat = result ? result.total_return_pct - result.buy_and_hold_return_pct : 0;

  return (
    <section className="panel lab" aria-labelledby="lab-h">
      <div className="lab-head">
        <h2 id="lab-h">Strategy lab</h2>
        <p className="hint">
          {catalog ? `${builtIn.length} built-in strategies` : "Loading strategies"}
          {yours.length > 0 && `, ${yours.length} of your own`}. Signals use each day's close and trade at the next day's open,
          with a 0.15% fee each way.
        </p>
      </div>

      {catalog?.load_errors.map((le) => (
        <p key={le.file} className="error" role="alert">Could not load {le.file}: {le.error}</p>
      ))}

      <form className="lab-form" onSubmit={run} noValidate>
        <label className="wide">
          Strategy
          <select value={strategyId} onChange={(e) => { setStrategyId(e.target.value); setParams({}); setCard(null); }}>
            <optgroup label="Built-in">
              {builtIn.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </optgroup>
            {yours.length > 0 && (
              <optgroup label="Your strategies">
                {yours.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </optgroup>
            )}
          </select>
        </label>
        {spec?.params.map((p) => (
          <label key={p.key}>
            {p.label}
            <input inputMode={p.integer ? "numeric" : "decimal"} value={params[p.key] ?? String(p.default)}
              aria-describedby={`range-${p.key}`}
              onChange={(e) => { setParams({ ...params, [p.key]: e.target.value }); setCard(null); }} />
            <span id={`range-${p.key}`} className="range">{p.min} to {p.max}</span>
          </label>
        ))}
        <label>
          Period
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={182}>6 months</option>
            <option value={365}>1 year</option>
            <option value={730}>2 years</option>
          </select>
        </label>
        <button className="primary" disabled={busy !== null || !spec}>{busy === "run" ? "Running…" : `Backtest on ${symbol}`}</button>
      </form>

      {spec && (
        <div className="about">
          <p><b>{spec.name}.</b> {spec.summary} {spec.how}</p>
          <p className="hint">
            {spec.source === "built-in" ? "Built-in" : `From ${spec.source.replace("your file: ", "")}`}, by {spec.author}.
            {spec.reference && <> <a href={spec.reference} target="_blank" rel="noreferrer">Background reading</a>.</>}
          </p>
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}

      {result && curve.length > 1 && (
        <>
          <p className="verdict">
            On {result.symbol}, this strategy turned 100 EGP into {curve[curve.length - 1].strategy.toFixed(2)} EGP.
            {" "}That is {Math.abs(beat).toFixed(2)} points {beat >= 0 ? "ahead of" : "behind"} simply holding.
          </p>
          <dl className="stats">
            <div><dt>Strategy return</dt><dd className={tone(result.total_return_pct)}>{pct(result.total_return_pct)}</dd></div>
            <div><dt>Buy and hold</dt><dd className={tone(result.buy_and_hold_return_pct)}>{pct(result.buy_and_hold_return_pct)}</dd></div>
            <div><dt>Worst drop</dt><dd>{result.max_drawdown_pct.toFixed(2)}%</dd></div>
            <div><dt>Sharpe</dt><dd>{result.sharpe.toFixed(2)}</dd></div>
            <div><dt>Trades</dt><dd>{result.trades}</dd></div>
            <div><dt>Time in the market</dt><dd>{result.exposure_pct.toFixed(0)}%</dd></div>
          </dl>
          <LineChart
            label={`Growth of 100 EGP: ${result.strategy_name} versus buy and hold on ${result.symbol}`}
            days={curve.map((c) => c.day)}
            series={[
              { name: "Strategy", color: "var(--lapis)", values: curve.map((c) => c.strategy) },
              { name: "Buy and hold", short: "Hold", color: "var(--saffron)", values: curve.map((c) => c.buy_hold), dashed: true },
            ]}
            format={(v) => v.toFixed(0)}
          />
          {result.trade_log.length > 0 && (
            <details className="trades">
              <summary>Trade log ({result.trade_log.length} most recent)</summary>
              <table>
                <thead><tr><th>Entry</th><th>Exit</th><th className="num">Return</th></tr></thead>
                <tbody>
                  {result.trade_log.slice().reverse().map((t, i) => (
                    <tr key={i}>
                      <td>{shortDate(t.entry)}</td>
                      <td>{t.exit === "open" ? "Still open" : shortDate(t.exit)}</td>
                      <td className={`num ${tone(t.return_pct)}`}>{pct(t.return_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
        </>
      )}

      <div className="check-row">
        <div>
          <h3>Does it hold up?</h3>
          <p className="hint">
            One stock over one period can flatter any rule. The check runs it on every stock, tests it on later data it was not
            tuned on, and confirms it never uses future prices.
          </p>
        </div>
        <button className="ghost strong" onClick={check} disabled={busy !== null || !spec}>
          {busy === "check" ? "Checking…" : "Check this strategy"}
        </button>
      </div>
      {card && <ReportCardView card={card} />}
    </section>
  );
}
