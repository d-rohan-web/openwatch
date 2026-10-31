// ⌘K: find a layer (toggle it), a live record (fly to it) or a district (fly there).
import { CornerDownLeft, Layers, MapPin, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { catOf } from "../sections";
import type { FeedMeta, Rec } from "../types";

type Hit = { key: string; icon: "layer" | "rec" | "place"; label: string; sub: string; run: () => void };
type District = { name: string; state: string; lon: number; lat: number };

export function CommandPalette({ open, close, feeds, records, on, toggle, pick, fly, states, pickState }: {
  open: boolean; close: () => void; feeds: FeedMeta[]; records: Rec[]; on: Set<string>; toggle: (id: string) => void;
  pick: (r: Rec) => void; fly: (lon: number, lat: number) => void; states: string[]; pickState: (name: string) => void;
}) {
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const [districts, setDistricts] = useState<District[]>([]);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!open) return;
    setQ(""); setI(0); setTimeout(() => input.current?.focus(), 0);
    if (!districts.length) fetch("/geo/districts.geojson").then((r) => r.json()).then((g) => setDistricts(g.features.map((f: any) => {
      const c = f.geometry.coordinates.flat(3);  // rough centre: mean of the outline's vertices
      const xs = c.filter((_: number, k: number) => k % 2 === 0), ys = c.filter((_: number, k: number) => k % 2 === 1);
      return { ...f.properties, lon: xs.reduce((a: number, b: number) => a + b, 0) / xs.length, lat: ys.reduce((a: number, b: number) => a + b, 0) / ys.length };
    }))).catch(() => {});
  }, [open]);

  const hits = useMemo<Hit[]>(() => {
    const s = q.trim().toLowerCase();
    const label = (id: string) => feeds.find((f) => f.id === id)?.label ?? id;
    const layers = feeds.filter((f) => !s || f.label.toLowerCase().includes(s) || f.id.includes(s)).slice(0, s ? 6 : 8).map<Hit>((f) => ({
      key: "l" + f.id, icon: "layer", label: f.label, sub: `${catOf(f.section).label} layer · ${on.has(f.id) ? "on — hide" : "off — show"}`,
      run: () => toggle(f.id) }));
    if (!s) return layers;
    const recs = records.filter((r) => r.title.toLowerCase().includes(s) || r.id.toLowerCase() === s ||
      String(r.attrs.callsign ?? r.attrs.reg ?? r.attrs.name ?? "").toLowerCase().includes(s)).slice(0, 12).map<Hit>((r) => ({
      key: "r" + r.feed + r.id, icon: "rec", label: r.title, sub: `${label(r.feed)} · ${r.kind}`, run: () => pick(r) }));
    const places = districts.filter((d) => d.name.toLowerCase().startsWith(s)).slice(0, 5).map<Hit>((d) => ({
      key: "p" + d.name + d.state, icon: "place", label: d.name, sub: `District · ${d.state}`, run: () => fly(d.lon, d.lat) }));
    const st = states.filter((n) => n.toLowerCase().includes(s)).slice(0, 4).map<Hit>((n) => ({
      key: "s" + n, icon: "place", label: n, sub: "State / UT · focus", run: () => pickState(n) }));
    return [...st, ...places, ...recs, ...layers];
  }, [q, feeds, records, on, districts, states]);

  if (!open) return null;
  const go = (h?: Hit) => { if (h) { h.run(); close(); } };
  return (
    <div className="backdrop" onMouseDown={close}>
      <div className="glass palette" role="dialog" aria-label="Search" onMouseDown={(e) => e.stopPropagation()}>
        <div style={{ position: "relative" }}>
          <Search size={16} style={{ position: "absolute", left: 16, top: 17, color: "var(--muted)" }} />
          <input ref={input} value={q} placeholder="Search layers, callsigns, registrations, alerts, districts…" style={{ paddingLeft: 42 }}
            onChange={(e) => { setQ(e.target.value); setI(0); }}
            onKeyDown={(e) => {
              if (e.key === "Escape") close();
              else if (e.key === "ArrowDown") { e.preventDefault(); setI(Math.min(i + 1, hits.length - 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setI(Math.max(i - 1, 0)); }
              else if (e.key === "Enter") go(hits[i]);
            }} />
        </div>
        <div className="scroll">
          {!hits.length && <div className="empty">Nothing matches “{q}”.</div>}
          {hits.map((h, k) => (
            <button key={h.key} className={`pal-item ${k === i ? "on" : ""}`} onMouseEnter={() => setI(k)} onClick={() => go(h)}>
              {h.icon === "layer" ? <Layers size={15} className="muted" /> : h.icon === "place" ? <MapPin size={15} color="#ff9933" /> : <Search size={15} className="muted" />}
              <span className="grow"><div>{h.label}</div><small>{h.sub}</small></span>
              {k === i && <CornerDownLeft size={14} className="muted" />}
            </button>
          ))}
        </div>
        <div className="pal-foot"><span><kbd>↑</kbd> <kbd>↓</kbd> move</span><span><kbd>↵</kbd> open</span><span><kbd>esc</kbd> close</span></div>
      </div>
    </div>
  );
}
