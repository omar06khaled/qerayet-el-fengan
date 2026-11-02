import { useEffect, useMemo, useRef, useState } from "react";
import { longDate, shortDate } from "./format";

export type Series = { name: string; short?: string; color: string; values: number[]; dashed?: boolean };

type Props = {
  days: string[];
  series: Series[];
  height?: number;
  format: (n: number) => string;
  label: string; // accessible description
};

const PAD = { top: 16, right: 92, bottom: 28, left: 56 };

function niceTicks(min: number, max: number, count = 4) {
  const span = max - min || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const lo = Math.floor(min / step) * step;
  const hi = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(+v.toFixed(6));
  return { lo, hi, ticks };
}

export function LineChart({ days, series, height = 280, format, label }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(720);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(300, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const n = days.length;
  const multi = series.length > 1;
  const padRight = multi ? PAD.right : 20;
  const innerW = width - PAD.left - padRight;
  const innerH = height - PAD.top - PAD.bottom;

  const { lo, hi, ticks } = useMemo(() => {
    const all = series.flatMap((s) => s.values);
    return niceTicks(Math.min(...all), Math.max(...all));
  }, [series]);

  const x = (i: number) => PAD.left + (n <= 1 ? 0 : (i / (n - 1)) * innerW);
  const y = (v: number) => PAD.top + innerH - ((v - lo) / (hi - lo || 1)) * innerH;
  const path = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("");

  const xTickIdx = useMemo(() => {
    const k = Math.min(5, n);
    return Array.from({ length: k }, (_, j) => Math.round((j / (k - 1 || 1)) * (n - 1)));
  }, [n]);

  // End labels: nudge apart so they never collide.
  const endLabels = useMemo(() => {
    if (!multi) return [];
    const items = series.map((s) => ({ s, y: y(s.values[n - 1]) })).sort((a, b) => a.y - b.y);
    for (let i = 1; i < items.length; i++) {
      if (items[i].y - items[i - 1].y < 16) items[i].y = items[i - 1].y + 16;
    }
    return items;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, width, lo, hi]);

  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const rel = (e.clientX - box.left) / box.width;
    setHover(Math.max(0, Math.min(n - 1, Math.round(rel * (n - 1)))));
  };

  const tipLeft = hover === null ? 0 : x(hover);
  const tipFlip = hover !== null && tipLeft > width - 200;

  return (
    <div className="chart" ref={wrap}>
      {multi && (
        <ul className="legend" aria-label="Legend">
          {series.map((s) => (
            <li key={s.name}>
              <svg width="22" height="8" aria-hidden="true">
                <line x1="1" y1="4" x2="21" y2="4" stroke={s.color} strokeWidth="2"
                  strokeDasharray={s.dashed ? "5 3" : undefined} strokeLinecap="round" />
              </svg>
              {s.name}
            </li>
          ))}
        </ul>
      )}
      <svg width={width} height={height} role="img" aria-label={label}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={PAD.left + innerW} y1={y(t)} y2={y(t)} className="grid" />
            <text x={PAD.left - 10} y={y(t)} className="axis" textAnchor="end" dominantBaseline="central">
              {format(t)}
            </text>
          </g>
        ))}
        {xTickIdx.map((i) => (
          <text key={i} x={x(i)} y={height - 8} className="axis"
            textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}>
            {shortDate(days[i])}
          </text>
        ))}
        {series.map((s) => (
          <path key={s.name} d={path(s.values)} fill="none" stroke={s.color} strokeWidth="2"
            strokeLinejoin="round" strokeLinecap="round" strokeDasharray={s.dashed ? "6 4" : undefined} />
        ))}
        {endLabels.map(({ s, y: ly }) => (
          <text key={s.name} x={PAD.left + innerW + 10} y={ly} className="endlabel" dominantBaseline="central">
            {s.short ?? s.name} {format(s.values[n - 1])}
          </text>
        ))}
        {hover !== null && (
          <g pointerEvents="none">
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + innerH} className="crosshair" />
            {series.map((s) => (
              <circle key={s.name} cx={x(hover)} cy={y(s.values[hover])} r="4.5"
                fill={s.color} stroke="var(--surface)" strokeWidth="2" />
            ))}
          </g>
        )}
        <rect x={PAD.left} y={PAD.top} width={innerW} height={innerH} fill="transparent"
          onPointerMove={onMove} onPointerLeave={() => setHover(null)} style={{ cursor: "crosshair" }} />
      </svg>
      {hover !== null && (
        <div className="tooltip" style={{ left: tipFlip ? tipLeft - 16 : tipLeft + 16, top: PAD.top, transform: tipFlip ? "translateX(-100%)" : undefined }}>
          <div className="tooltip-date">{longDate(days[hover])}</div>
          {series.map((s) => (
            <div key={s.name} className="tooltip-row">
              <svg width="14" height="8" aria-hidden="true">
                <line x1="1" y1="4" x2="13" y2="4" stroke={s.color} strokeWidth="2"
                  strokeDasharray={s.dashed ? "4 2" : undefined} />
              </svg>
              <span>{s.name}</span>
              <b>{format(s.values[hover])}</b>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
