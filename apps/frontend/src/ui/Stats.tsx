// Bottom-left: KPI tiles (each switches its layer on) over a markets ticker (economy feeds).
import type { Rec } from "../types";

type Tile = { label: string; feeds: string[]; value: (r: Rec[]) => number };
const TILES: Tile[] = [
  { label: "Aircraft airborne", feeds: ["aircraft", "opensky"], value: (r) => r.filter((x) => !x.attrs.on_ground).length },
  { label: "Military aircraft", feeds: ["aircraft"], value: (r) => r.filter((x) => x.kind === "military").length },
  { label: "Ships", feeds: ["ais"], value: (r) => r.length },
  { label: "Satellites overhead", feeds: ["satellites"], value: (r) => r.length },
  { label: "Quakes · 24h", feeds: ["ncs_quakes"], value: (r) => r.filter((x) => x.observed_at && Date.now() - Date.parse(x.observed_at) < 864e5).length },
  { label: "Weather warnings", feeds: ["imd_warnings"], value: (r) => r.length },
];

export function Stats({ live, inScope, show, ticker }: { live: Record<string, Rec[]>; inScope: (r: Rec) => boolean;
  show: (feeds: string[]) => void; ticker: Rec[] }) {
  const tiles = TILES.filter((t) => t.feeds.some((f) => live[f]));
  if (!tiles.length && !ticker.length) return null;
  return (
    <div className="overlay glass stats">
      <div className="stat-row">
        {tiles.map((t) => (
          <button key={t.label} className="stat" onClick={() => show(t.feeds)} title={`Show ${t.label.toLowerCase()}`}>
            <b className="num">{t.value(t.feeds.flatMap((f) => live[f] ?? []).filter(inScope)).toLocaleString()}</b><small>{t.label}</small>
          </button>
        ))}
      </div>
      {ticker.length > 0 && <Ticker items={ticker} />}
    </div>
  );
}

function Ticker({ items }: { items: Rec[] }) {
  const row = items.map((r) => {
    const pct = r.attrs.change_pct as number | undefined;
    const c = pct === undefined ? "var(--text-2)" : pct > 0 ? "#22d3a6" : pct < 0 ? "#ff6b6b" : "var(--text-2)";
    return (
      <span key={r.feed + r.id} className="tick">
        <b>{r.id}</b> <span className="num">{typeof r.attrs.value === "number" ? r.attrs.value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : ""}</span>
        {pct !== undefined && <span className="num" style={{ color: c }}> {pct > 0 ? "▲" : pct < 0 ? "▼" : "•"}{Math.abs(pct).toFixed(2)}%</span>}
      </span>
    );
  });
  // two copies so the loop is seamless
  return <div className="ticker" aria-label="Markets"><div className="ticker-track" style={{ animationDuration: `${Math.max(20, items.length * 4)}s` }}>{row}{row}</div></div>;
}
