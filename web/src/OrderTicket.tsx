import { useState } from "react";
import { api, type OrderType, type Preview, type Quote, type Side } from "./api";
import { money, price } from "./format";

type Props = { quote: Quote; tradingEnabled: boolean; maxOrder: number; onPlaced: () => void };

export function OrderTicket({ quote, tradingEnabled, maxOrder, onPlaced }: Props) {
  const [side, setSide] = useState<Side>("buy");
  const [qty, setQty] = useState("10");
  const [type, setType] = useState<OrderType>("market");
  const [px, setPx] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const needsPrice = type !== "market";
  const estimate = (Number(px) || quote.last) * (Number(qty) || 0);

  const reset = () => { setPreview(null); setError(null); setResult(null); };

  async function onPreview(e: React.FormEvent) {
    e.preventDefault();
    reset();
    const q = Number(qty);
    if (!Number.isInteger(q) || q <= 0) return setError("Enter a whole number of shares above zero.");
    if (needsPrice && !(Number(px) > 0)) return setError(`Enter a ${type === "limit" ? "limit" : "trigger"} price.`);
    setBusy(true);
    try {
      setPreview(await api.preview({
        symbol: quote.symbol, side, quantity: q, order_type: type,
        limit_price: type === "limit" ? Number(px) : undefined,
        stop_price: type === "stop" ? Number(px) : undefined,
      }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm() {
    if (!preview) return;
    setBusy(true);
    try {
      const o = await api.confirm(preview.confirmation_token);
      setResult(o.status === "filled"
        ? `Order placed and filled at ${price(o.filled_price ?? 0)}.`
        : `Order placed. Status: ${o.status}.`);
      setPreview(null);
      onPlaced();
    } catch (err) {
      setError((err as Error).message);
      setPreview(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel ticket" aria-labelledby="ticket-h">
      <h2 id="ticket-h">Trade {quote.symbol}</h2>
      <form onSubmit={onPreview} noValidate>
        <div className="segmented" role="radiogroup" aria-label="Side">
          {(["buy", "sell"] as Side[]).map((s) => (
            <button key={s} type="button" role="radio" aria-checked={side === s}
              className={side === s ? "on" : ""} onClick={() => { setSide(s); reset(); }}>
              {s === "buy" ? "Buy" : "Sell"}
            </button>
          ))}
        </div>
        <label>
          Shares
          <input inputMode="numeric" value={qty} onChange={(e) => { setQty(e.target.value); reset(); }} />
        </label>
        <label>
          Order type
          <select value={type} onChange={(e) => { setType(e.target.value as OrderType); reset(); }}>
            <option value="market">Market, at the current price</option>
            <option value="limit">Limit, at your price or better</option>
            <option value="stop">Stop, triggers at a price</option>
          </select>
        </label>
        {needsPrice && (
          <label>
            {type === "limit" ? "Limit price" : "Trigger price"} (EGP)
            <input inputMode="decimal" value={px} placeholder={price(quote.last)}
              onChange={(e) => { setPx(e.target.value); reset(); }} />
          </label>
        )}
        <p className="hint">
          About {money(estimate)}. Orders are capped at {money(maxOrder)}.
        </p>
        {error && <p className="error" role="alert">{error}</p>}
        {!preview && <button className="primary" disabled={busy}>Review order</button>}
      </form>

      {preview && (
        <div className="review" role="region" aria-label="Order review">
          <p className="review-summary">{preview.summary}</p>
          <dl>
            <div><dt>Last price</dt><dd>{price(preview.last_price)}</dd></div>
            <div><dt>Estimated value</dt><dd>{money(preview.estimated_value_egp)}</dd></div>
          </dl>
          {!tradingEnabled && (
            <p className="hint">Trading is off on this server, so placing will be refused. Restart with YOUNIT_TRADING_ENABLED=true to place mock orders.</p>
          )}
          <div className="row">
            <button className="primary" onClick={onConfirm} disabled={busy}>Place order</button>
            <button className="ghost" onClick={reset} disabled={busy}>Edit</button>
          </div>
        </div>
      )}
      {result && <p className="success" role="status">{result}</p>}
    </section>
  );
}
