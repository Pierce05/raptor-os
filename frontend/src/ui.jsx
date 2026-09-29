import { useEffect, useState } from "react";

export const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "");
export const short = (id, n = 8) => (id ? String(id).slice(0, n) : "—");

export const reduceMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export function useCountUp(to, delay = 200) {
  const [v, setV] = useState(reduceMotion() ? to : 0);
  useEffect(() => {
    if (typeof to !== "number") return;
    if (reduceMotion()) { setV(to); return; }
    let raf; const start = performance.now() + delay;
    const tick = (now) => {
      const p = Math.min(1, Math.max(0, (now - start) / 700));
      setV(Math.round((1 - Math.pow(1 - p, 3)) * to));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, delay]);
  return v;
}

export function Metric({ value, label, tone, delay }) {
  const isNum = typeof value === "number";
  const n = useCountUp(isNum ? value : 0, delay);
  return (
    <div>
      <b className={tone || ""}>{isNum ? n : value}</b>
      <span>{label}</span>
    </div>
  );
}
export function MetricStrip({ items }) {
  return <div className="strip">{items.map((m, i) => <Metric key={m.label} {...m} delay={200 + i * 70} />)}</div>;
}

export function StatusBadge({ tone = "", children }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Progress({ pct, label, right, thick, crimson }) {
  return (
    <div>
      {(label || right) && <div className="bar-label"><span>{label}</span><span>{right}</span></div>}
      <div className={`bar ${thick ? "thick" : ""} ${crimson ? "crimson" : ""}`} role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
        <div style={{ width: Math.max(0, Math.min(100, pct)) + "%" }} />
      </div>
    </div>
  );
}

export function Panel({ title, right, accent, children, style }) {
  return (
    <section className={`panel ${accent ? "accent" : ""}`} style={style}>
      {(title || right) && <div className="ptitle"><span>{title}</span><span>{right}</span></div>}
      {children}
    </section>
  );
}

export function LoadingState({ rows = 3 }) {
  return <div className="skeleton" aria-busy="true">{Array.from({ length: rows }).map((_, i) => <div className="skel-row" key={i} />)}</div>;
}
export function EmptyState({ children }) { return <div className="state">{children}</div>; }
export function ErrorState({ children, onRetry }) {
  return (
    <div className="state state-error" role="alert">
      {children}
      {onRetry && <div><button onClick={onRetry}>Retry</button></div>}
    </div>
  );
}

export function PageHead({ eyebrow, title, sub, right }) {
  return (
    <div className="head">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h2 style={{ margin: 0 }}>{title}</h2>
        {sub && <p className="meta" style={{ marginTop: 6 }}>{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function AuditIndicator({ state }) {
  if (state === "valid") return <StatusBadge tone="ok"><i className="dot ok" />chain valid</StatusBadge>;
  if (state === "broken") return <StatusBadge tone="err"><i className="dot err" />chain broken</StatusBadge>;
  return <StatusBadge><i className="dot" />chain not loaded</StatusBadge>;
}

export function Logo() {
  return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M2 20 L12 3 L22 20 L12 14 Z" fill="#c2202f" /></svg>;
}

export function Radar({ dots = 0 }) {
  // Positions are decorative slots; how many appear equals the real project count (capped).
  const slots = [[120,230],[60,90],[250,70],[140,60],[280,170],[100,150],[230,210],[170,20],[80,200],[260,120],[150,250],[40,140]];
  return (
    <div className="hero-art" aria-hidden="true">
      <svg viewBox="0 0 300 280">
        <circle className="ring1" cx="190" cy="130" r="120" stroke="#c2202f" strokeOpacity=".3" fill="none" />
        <circle className="ring2" cx="190" cy="130" r="78" stroke="#c2202f" strokeOpacity=".5" fill="none" />
        <g stroke="#f3eee4" strokeOpacity=".16">
          {[[298,130,310,130],[190,238,190,250],[82,130,70,130],[190,22,190,10],[283.5,184,293.9,190],[96.5,76,86.1,70],[244,36.5,250,26.1],[136,223.5,130,233.9]].map((l, i) => <line key={i} x1={l[0]} y1={l[1]} x2={l[2]} y2={l[3]} />)}
        </g>
        <circle cx="190" cy="130" r="6" fill="#c2202f" />
        {slots.slice(0, Math.min(dots, slots.length)).map(([x, y], i) => (
          <circle key={i} className="blip" cx={x} cy={y} r="3" fill="#3fa88f" style={{ animationDelay: `${i * 0.3}s` }} />
        ))}
        <g className="sweep">
          <path d="M190 130 L280 40" stroke="#c2202f" strokeWidth="2" />
          <circle cx="280" cy="40" r="3.5" fill="#c2202f" />
          <path d="M190 130 L280 40" stroke="#c2202f" strokeOpacity=".08" strokeWidth="60" strokeLinecap="round" />
        </g>
      </svg>
      <span className="cap">AUDIT · LIVE</span>
    </div>
  );
}
