import type { ReportCard } from "./api";
import { pct, tone } from "./format";

const VERDICT: Record<ReportCard["verdict"], { label: string; mark: string; cls: string }> = {
  holds_up: { label: "Holds up on unseen data", mark: "✓", cls: "v-good" },
  mixed: { label: "Mixed results", mark: "≈", cls: "v-neutral" },
  does_not_hold_up: { label: "Does not hold up", mark: "✕", cls: "v-bad" },
  too_few_trades: { label: "Too few trades to judge", mark: "?", cls: "v-neutral" },
  baseline: { label: "Baseline", mark: "=", cls: "v-neutral" },
  invalid: { label: "Uses future prices", mark: "⚠", cls: "v-bad" },
  demo_data: { label: "No verdict on demo data", mark: "i", cls: "v-neutral" },
};

export function ReportCardView({ card }: { card: ReportCard }) {
  const v = VERDICT[card.verdict];
  const oosStart = card.symbols[0]?.out_sample_start;
  return (
    <div className="card" role="region" aria-label={`Report card for ${card.strategy_name}`}>
      <div className={`verdict-band ${v.cls}`}>
        <span className="verdict-mark" aria-hidden="true">{v.mark}</span>
        <div>
          <p className="verdict-label">{v.label}</p>
          <p className="verdict-headline">{card.headline}</p>
        </div>
      </div>

      <ul className="checks">
        <li>
          <span className={card.lookahead.passed ? "ok" : "fail"} aria-hidden="true">{card.lookahead.passed ? "✓" : "✕"}</span>
          <span><b>Look-ahead check {card.lookahead.passed ? "passed" : "failed"}.</b> {card.lookahead.detail}</span>
        </li>
        <li>
          <span className="ok" aria-hidden="true">✓</span>
          <span>
            <b>Tested on data it was not tuned on.</b> Each stock's history is split {card.split_pct}/{100 - card.split_pct}; the
            table compares the later part{oosStart ? `, from ${oosStart}` : ""}, against simply holding the stock.
          </span>
        </li>
      </ul>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Stock</th>
              <th className="num">Earlier: strategy</th>
              <th className="num">Earlier: hold</th>
              <th className="num">Later: strategy</th>
              <th className="num">Later: hold</th>
              <th className="num">Later trades</th>
              <th>Beat holding later?</th>
            </tr>
          </thead>
          <tbody>
            {card.symbols.map((s) => (
              <tr key={s.symbol}>
                <td><b>{s.symbol}</b></td>
                <td className={`num ${tone(s.in_sample_pct)}`}>{pct(s.in_sample_pct)}</td>
                <td className="num">{pct(s.in_sample_hold_pct)}</td>
                <td className={`num ${tone(s.out_sample_pct)}`}><b>{pct(s.out_sample_pct)}</b></td>
                <td className="num">{pct(s.out_sample_hold_pct)}</td>
                <td className="num">{s.out_sample_trades}</td>
                <td>{s.beat_out_sample ? "✓ Yes" : "✕ No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint card-sum">
        Beat holding on {card.beat_count} of {card.symbols.length} stocks on the later data, with a median gap
        of {pct(card.median_excess_pct)} over {card.total_trades} trades.
      </p>

      <ul className="notes">
        {card.notes.map((n, i) => <li key={i}>{n}</li>)}
      </ul>
    </div>
  );
}
