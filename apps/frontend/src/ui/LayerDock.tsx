// Layer filter: a row of category chips over the map; each opens a card with its layers. Views set a whole job's layers.
import { ChevronDown, Info, Layers } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { feedColor } from "../features";
import { CATS, VIEWS } from "../sections";
import type { FeedMeta, Rec, Section } from "../types";
import { ago, STATE } from "./common";

// Map overlays that aren't feeds (basemap roads/rivers, border lines, TomTom tiles), shown in their category's card.
export type Extra = { id: string; section: Section; label: string; meta: string; color: string; on: boolean; available: boolean; toggle: () => void };
type Props = { feeds: FeedMeta[]; live: Record<string, Rec[]>; on: Set<string>; setOn: (ids: string[]) => void; extras: Extra[]; now: number };

export function LayerDock(p: Props) {
  const [open, setOpen] = useState<Section | "views" | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(null); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(null); };
    document.addEventListener("mousedown", close); document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, []);
  const toggle = (id: string) => p.setOn(p.on.has(id) ? [...p.on].filter((x) => x !== id) : [...p.on, id]);
  const setMany = (ids: string[], v: boolean) => p.setOn(v ? [...new Set([...p.on, ...ids])] : [...p.on].filter((x) => !ids.includes(x)));
  const all = p.feeds.map((f) => f.id);

  return (
    <div className="overlay dock" ref={ref}>
      <div className="cat">
        <button className={`glass cat-chip ${open === "views" ? "open" : ""}`} style={{ "--cat": "#ff9933" } as CSSProperties}
          onClick={() => setOpen(open === "views" ? null : "views")} aria-expanded={open === "views"} title="Views: one-click layer sets">
          <span className="ico"><Layers size={14} /></span><span className="sr">Views</span><ChevronDown size={13} className="muted" />
        </button>
        {open === "views" && (
          <div className="glass pop" style={{ width: 240 }}>
            <div className="pop-head"><b className="grow">Views</b><button className="link" onClick={() => p.setOn([])}>Clear map</button></div>
            {VIEWS.map((v) => {
              const ids = v.feeds.length ? v.feeds.filter((id) => all.includes(id)) : all;
              return (
                <button key={v.id} className="layer-row" style={{ width: "100%", background: "none", border: 0, textAlign: "left" }}
                  onClick={() => { p.setOn(ids); setOpen(null); }}>
                  <span className="grow layer-name">{v.label}</span><span className="layer-meta">{ids.length} layers</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
      {CATS.map((c) => {
        const fs = p.feeds.filter((f) => f.section === c.id);
        const ex = p.extras.filter((e) => e.section === c.id);
        if (!fs.length && !ex.length) return null;
        const active = fs.filter((f) => p.on.has(f.id));
        const count = active.reduce((n, f) => n + (p.live[f.id]?.length ?? 0), 0);
        const trouble = fs.some((f) => f.health?.state === "DOWN");
        const Icon = c.icon;
        const style = { "--cat": c.color, "--cat-soft": `${c.color}22` } as CSSProperties;
        return (
          <div className="cat" key={c.id} style={style}>
            <button className={`glass cat-chip ${active.length || ex.some((e) => e.on) ? "active" : ""} ${open === c.id ? "open" : ""}`}
              onClick={() => setOpen(open === c.id ? null : c.id)} aria-expanded={open === c.id}>
              <span className="ico"><Icon size={14} /></span>
              {c.label}
              {active.length > 0 && <span className="count num">{count.toLocaleString()}</span>}
              {trouble && <i className="warn" title="A feed in this group is down" />}
              <ChevronDown size={13} className="muted" />
            </button>
            {open === c.id && (
              <div className="glass pop">
                <div className="pop-head">
                  <Icon size={14} color={c.color} /><b className="grow">{c.label}</b>
                  <button className="link" onClick={() => setMany(fs.map((f) => f.id), true)}>All</button>
                  <span className="muted">·</span>
                  <button className="link" onClick={() => setMany(fs.map((f) => f.id), false)}>None</button>
                </div>
                {fs.map((f) => <LayerRow key={f.id} f={f} n={p.live[f.id]?.length ?? 0} on={p.on.has(f.id)} toggle={() => toggle(f.id)} now={p.now} />)}
                {ex.map((e) => (
                  <div key={e.id} className={`layer ${e.on && e.available ? "" : "off"}`}>
                    <div className="layer-row" onClick={() => e.available && e.toggle()}>
                      <i className="swatch" style={{ background: e.color }} />
                      <span className="grow"><div className="layer-name">{e.label}</div><div className="layer-meta">{e.meta}</div></span>
                      <button className={`switch ${e.on && e.available ? "on" : ""}`} disabled={!e.available} aria-label={e.label} role="switch"
                        aria-checked={e.on} onClick={(ev) => { ev.stopPropagation(); e.toggle(); }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function LayerRow({ f, n, on, toggle, now }: { f: FeedMeta; n: number; on: boolean; toggle: () => void; now: number }) {
  const [info, setInfo] = useState(false);
  const st = STATE[f.health?.state ?? "STARTING"];
  const needsKey = f.health?.state === "NEEDS_KEY";
  return (
    <div className={`layer ${on && !needsKey ? "" : "off"}`}>
      <div className="layer-row" onClick={() => !needsKey && toggle()}>
        <i className="swatch" style={{ background: feedColor(f.id, f.section) }} />
        <span className="grow">
          <div className="layer-name">{f.label}</div>
          <div className="layer-meta">
            <i className="dot" style={{ background: st.color, width: 6, height: 6, marginRight: 5 }} />
            {needsKey ? <>needs <code>{f.key}</code></> : <>{n.toLocaleString()} · {st.label.toLowerCase()} · {ago(f.health?.last_ok_at, now)} ago</>}
          </div>
        </span>
        <button className="icon-btn" aria-label={`About ${f.label}`} aria-expanded={info} onClick={(e) => { e.stopPropagation(); setInfo(!info); }}>
          <Info size={14} />
        </button>
        <button className={`switch ${on && !needsKey ? "on" : ""}`} disabled={needsKey} aria-label={f.label} role="switch" aria-checked={on}
          onClick={(e) => { e.stopPropagation(); toggle(); }} />
      </div>
      {info && (
        <div className="layer-info">
          <span><a href={f.homepage} target="_blank" rel="noreferrer">{f.homepage.replace(/^https?:\/\//, "")}</a></span>
          <span>{f.terms}</span>
          <span className="muted">{f.streaming ? "Streaming" : `Every ${f.every >= 60 ? `${Math.round(f.every / 60)} min` : `${f.every} s`}`} · stored {(f.health?.stored_total ?? 0).toLocaleString()}</span>
          {f.health?.last_error && f.health.state !== "OK" && <span className="err">{f.health.last_error}</span>}
        </div>
      )}
    </div>
  );
}
