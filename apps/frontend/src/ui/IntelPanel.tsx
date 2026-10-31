// Right-hand panel: Alerts (and a selected record's detail), Feed health, Export.
import { ArrowLeft, Bell, Download, ExternalLink, FileDown, History, Lock, PanelRightClose, PanelRightOpen, Radio, Satellite, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { rawUrl, runExport } from "../api";
import type { Pass } from "../features";
import { catOf } from "../sections";
import { SEVERITY_COLOR, SEVERITY_RANK, type FeedMeta, type Rec, type Severity } from "../types";
import { ago, SevTag, STATE } from "./common";

export type Tab = "alerts" | "sats" | "feeds" | "export";
type Props = {
  tab: Tab; setTab: (t: Tab) => void; collapsed: boolean; setCollapsed: (v: boolean) => void;
  feeds: FeedMeta[]; records: Rec[]; now: number; bounds: [number, number, number, number] | null;
  selected: Rec | undefined; selectedMeta?: FeedMeta; pick: (r: Rec) => void; clearSel: () => void;
  loadHistory: () => void; historyCount: number;
  satellites: Rec[]; passFor: (r: Rec) => Pass | null; exportEnabled: boolean;
};

export function IntelPanel(p: Props) {
  if (p.collapsed) return (
    <div className="overlay glass intel collapsed">
      <button className="icon-btn" style={{ margin: 6 }} onClick={() => p.setCollapsed(false)} aria-label="Open panel"><PanelRightOpen size={16} /></button>
    </div>
  );
  // map alerts only; government & cyber items (no place) are listed under their own heading
  const govtFeeds = new Set(p.feeds.filter((f) => f.section === "govt" || f.section === "economy").map((f) => f.id));
  const alerts = p.records.filter((r) => r.severity && SEVERITY_RANK[r.severity] >= 1 && !govtFeeds.has(r.feed));
  const urgent = alerts.filter((r) => SEVERITY_RANK[r.severity!] >= 2).length;
  return (
    <aside className="overlay glass intel" aria-label="Intel">
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={p.tab === "alerts"} className={`tab ${p.tab === "alerts" ? "on" : ""}`} onClick={() => { p.setTab("alerts"); p.clearSel(); }}>
          <Bell size={14} /> Alerts {urgent > 0 && <span className="badge num">{urgent}</span>}
        </button>
        <button role="tab" aria-selected={p.tab === "sats"} className={`tab ${p.tab === "sats" ? "on" : ""}`} onClick={() => { p.setTab("sats"); p.clearSel(); }}>
          <Satellite size={14} /> Satellites
        </button>
        <button role="tab" aria-selected={p.tab === "feeds"} className={`tab ${p.tab === "feeds" ? "on" : ""}`} onClick={() => p.setTab("feeds")}>
          <Radio size={14} /> Feeds
        </button>
        <button role="tab" aria-selected={p.tab === "export"} className={`tab ${p.tab === "export" ? "on" : ""}`} onClick={() => p.setTab("export")}>
          <Download size={14} /> Export
        </button>
        <span className="grow" />
        <button className="icon-btn" onClick={() => p.setCollapsed(true)} aria-label="Collapse panel"><PanelRightClose size={16} /></button>
      </div>
      {(p.tab === "alerts" || p.tab === "sats") && p.selected
        ? <Detail r={p.selected} meta={p.selectedMeta} now={p.now} back={p.clearSel} history={p.loadHistory} historyCount={p.historyCount}
            pass={p.passFor(p.selected)} />
        : p.tab === "sats" ? <Satellites sats={p.satellites} passFor={p.passFor} pick={p.pick} />
        : p.tab === "alerts" && <Alerts alerts={alerts} records={p.records} feeds={p.feeds} now={p.now} pick={p.pick} />}
      {p.tab === "feeds" && <Feeds feeds={p.feeds} now={p.now} />}
      {p.tab === "export" && (p.exportEnabled ? <Export feeds={p.feeds} bounds={p.bounds} /> : <ExportSoon />)}
    </aside>
  );
}

const SEVS: Severity[] = ["critical", "warning", "advisory"];

function Alerts({ alerts, records, feeds, now, pick }: { alerts: Rec[]; records: Rec[]; feeds: FeedMeta[]; now: number; pick: (r: Rec) => void }) {
  const [sev, setSev] = useState<Severity[]>(SEVS);
  const label = (id: string) => feeds.find((f) => f.id === id)?.label ?? id;
  const shown = useMemo(() => alerts.filter((r) => sev.includes(r.severity!))
    .sort((a, b) => SEVERITY_RANK[b.severity!] - SEVERITY_RANK[a.severity!] || (b.observed_at ?? "").localeCompare(a.observed_at ?? ""))
    .slice(0, 400), [alerts, sev]);
  const govt = useMemo(() => {
    const ids = new Set(feeds.filter((f) => f.section === "govt").map((f) => f.id));
    return records.filter((r) => ids.has(r.feed)).sort((a, b) => (b.observed_at ?? "").localeCompare(a.observed_at ?? "")).slice(0, 40);
  }, [records, feeds]);
  const counts = Object.fromEntries(SEVS.map((s) => [s, alerts.filter((r) => r.severity === s).length]));
  return (
    <>
      <div className="filters">
        {SEVS.map((s) => (
          <button key={s} className={`fchip ${sev.includes(s) ? "on" : ""}`} style={{ "--c": SEVERITY_COLOR[s] } as any}
            onClick={() => setSev(sev.includes(s) ? sev.filter((x) => x !== s) : [...sev, s])}>
            <i className="dot" style={{ background: SEVERITY_COLOR[s] }} />{s} <span className="num muted">{counts[s]}</span>
          </button>
        ))}
      </div>
      <div className="scroll">
        {!shown.length && <div className="empty"><ShieldCheck size={22} />No active alerts on the layers you have on.</div>}
        {shown.length > 0 && <div className="group-title">Active · {shown.length}</div>}
        {shown.map((r) => <Item key={r.feed + r.id} r={r} label={label(r.feed)} now={now} onClick={() => pick(r)} />)}
        {govt.length > 0 && <div className="group-title">Government & cyber · latest</div>}
        {govt.map((r) => <Item key={r.feed + r.id} r={r} label={label(r.feed)} now={now} onClick={() => pick(r)} />)}
      </div>
    </>
  );
}

function Item({ r, label, now, onClick }: { r: Rec; label: string; now: number; onClick: () => void }) {
  return (
    <button className="item" onClick={onClick}>
      <i className="sev-bar" style={{ background: r.severity ? SEVERITY_COLOR[r.severity] : "rgba(148,163,184,.3)" }} />
      <span className="grow">
        <span className="item-title">{r.title}</span>
        <span className="item-meta"><span>{label}</span><span>·</span><span>{r.kind}</span><span>·</span><span className="num">{ago(r.observed_at ?? r.fetched_at, now)} ago</span></span>
      </span>
    </button>
  );
}

const fmt = (v: unknown) => (v === null || v === undefined ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));

function PassBox({ p }: { p: Pass }) {
  const fixed = p.orbit === "GEO" || p.orbit === "IGSO";
  const text = fixed ? (p.over ? "Geosynchronous · always in view of India" : "Geosynchronous · not in view of India")
    : p.over ? `Over India now${p.outMin !== null ? ` · leaves in ${p.outMin} min` : ""}`
    : p.inMin !== null ? `Next over India in ${p.inMin} min` : "Not over India in the next 90 min";
  return (
    <div className="pass">
      <i className="dot" style={{ background: p.over ? "var(--live)" : "#b69cff" }} />
      <span className="grow">{text}</span>
      {p.orbit && <span className="tag" style={{ color: "#b69cff" }}>{p.orbit}</span>}
    </div>
  );
}

const MISSION_ORDER = ["Navigation (NavIC)", "Earth observation", "Weather & ocean", "Communication", "Strategic communication",
  "Electronic intelligence", "Space science", "Technology demo", "Other"];

function Satellites({ sats, passFor, pick }: { sats: Rec[]; passFor: (r: Rec) => Pass | null; pick: (r: Rec) => void }) {
  const [q, setQ] = useState("");
  const indian = sats.filter((r) => r.attrs.owner === "IND" && (!q || r.title.toLowerCase().includes(q.toLowerCase())));
  const others = sats.filter((r) => r.attrs.owner !== "IND");
  const groups = MISSION_ORDER.map((m) => [m, indian.filter((r) => (r.attrs.mission ?? "Other") === m)] as const).filter(([, l]) => l.length);
  const overNow = indian.filter((r) => passFor(r)?.over).length;
  return (
    <>
      <div className="filters">
        <input placeholder="Filter Indian satellites…" value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: 1 }} aria-label="Filter satellites" />
      </div>
      <div className="sat-sum muted">{indian.length} Indian satellites · {overNow} over / in view of India now · {others.length} others over the region</div>
      <div className="scroll">
        {!sats.length && <div className="empty"><Satellite size={22} />Waiting for orbital data from CelesTrak.</div>}
        {groups.map(([m, list]) => (
          <div key={m}>
            <div className="group-title">{m} · {list.length}</div>
            {list.map((r) => {
              const ps = passFor(r);
              return (
                <button key={r.id} className="item" onClick={() => pick(r)}>
                  <i className="sev-bar" style={{ background: ps?.over ? "var(--live)" : "rgba(182,156,255,.5)" }} />
                  <span className="grow">
                    <span className="item-title">{r.title}</span>
                    <span className="item-meta"><span>{r.attrs.orbit}</span><span>·</span><span className="num">{Math.round(r.attrs.alt_km).toLocaleString()} km</span>
                      {r.attrs.inclination !== undefined && <><span>·</span><span className="num">{r.attrs.inclination}°</span></>}
                      <span>·</span><span>{ps?.over ? (r.attrs.orbit === "GEO" || r.attrs.orbit === "IGSO" ? "in view of India" : "over India")
                        : ps?.inMin != null ? `over India in ${ps.inMin} min` : "—"}</span></span>
                  </span>
                </button>
              );
            })}
          </div>
        ))}
        {others.length > 0 && <div className="group-title">Other satellites over the region · {others.length}</div>}
        {others.slice(0, 60).map((r) => (
          <button key={r.id} className="item" onClick={() => pick(r)}>
            <i className="sev-bar" style={{ background: "rgba(148,163,184,.35)" }} />
            <span className="grow"><span className="item-title">{r.title}</span>
              <span className="item-meta">{r.kind} · {r.attrs.owner ?? "—"} · {Math.round(r.attrs.alt_km)} km</span></span>
          </button>
        ))}
      </div>
    </>
  );
}

function Detail({ r, meta, now, back, history, historyCount, pass }: { r: Rec; meta?: FeedMeta; now: number; back: () => void; history: () => void; historyCount: number; pass: Pass | null }) {
  const link = r.attrs.link ?? r.attrs.url;
  const cat = meta ? catOf(meta.section) : null;
  return (
    <>
      <div className="detail-head">
        <button className="link" style={{ display: "inline-flex", alignItems: "center", gap: 4, justifySelf: "start" }} onClick={back}>
          <ArrowLeft size={13} /> Back
        </button>
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          {cat && <span className="tag" style={{ color: cat.color }}>{cat.label}</span>}
          {r.severity && <SevTag s={r.severity} />}
          <span className="muted" style={{ fontSize: 11 }}>{meta?.label ?? r.feed} · {r.kind}</span>
        </div>
        <div className="detail-title">{r.title}</div>
        <div className="muted num" style={{ fontSize: 11 }}>
          observed {ago(r.observed_at, now)} ago · fetched {ago(r.fetched_at, now)} ago
          {r.lat !== null && <> · {r.lat.toFixed(4)}, {r.lon!.toFixed(4)}</>}
        </div>
      </div>
      {pass && <PassBox p={pass} />}
      <dl className="kv scroll">
        {Object.entries(r.attrs).filter(([, v]) => v !== "" && v !== null).map(([k, v]) => (
          <div key={k} style={{ display: "contents" }}><dt title={k}>{k}</dt><dd>{fmt(v)}</dd></div>
        ))}
        <dt>id</dt><dd className="mono">{r.id}</dd>
      </dl>
      <div className="actions">
        {r.lon !== null && <button className="btn" onClick={history}><History size={14} />{historyCount ? `History · ${historyCount}` : "History 6h"}</button>}
        {link && <a className="btn" href={link} target="_blank" rel="noreferrer"><ExternalLink size={14} />Source</a>}
        {r.raw_sha256 && <a className="btn" href={rawUrl(r.feed, r.raw_sha256)}><FileDown size={14} />Raw</a>}
      </div>
    </>
  );
}

function Feeds({ feeds, now }: { feeds: FeedMeta[]; now: number }) {
  const order = { DOWN: 0, DEGRADED: 1, STARTING: 2, OK: 3, NEEDS_KEY: 4 } as const;
  const sorted = [...feeds].sort((a, b) => order[a.health?.state ?? "STARTING"] - order[b.health?.state ?? "STARTING"] || a.label.localeCompare(b.label));
  return (
    <div className="scroll">
      {sorted.map((f) => {
        const st = STATE[f.health?.state ?? "STARTING"];
        return (
          <div key={f.id} className="feed">
            <div className="feed-top">
              <i className="dot" style={{ background: st.color }} />
              <b className="grow" style={{ fontWeight: 500 }}>{f.label}</b>
              <span className="feed-state" style={{ color: st.color }}>{st.label.toUpperCase()}</span>
            </div>
            <small className="num">
              {f.health?.state === "NEEDS_KEY" ? <>Add <code>{f.key}</code> to .env to enable</> :
                <>last ok {ago(f.health?.last_ok_at, now)} ago · live {(f.health?.live_count ?? 0).toLocaleString()} · stored {(f.health?.stored_total ?? 0).toLocaleString()} · {f.streaming ? "stream" : `every ${f.every}s`}</>}
            </small>
            {f.health?.last_error && f.health.state !== "OK" && f.health.state !== "NEEDS_KEY" && <span className="err">{f.health.last_error}</span>}
            <small><a href={f.homepage} target="_blank" rel="noreferrer">{f.homepage.replace(/^https?:\/\//, "")}</a> · {f.terms}</small>
          </div>
        );
      })}
    </div>
  );
}

function ExportSoon() {
  return (
    <div className="scroll">
      <div className="empty" style={{ padding: "36px 22px", gap: 10 }}>
        <Lock size={24} color="var(--accent)" />
        <b style={{ color: "var(--text)", fontSize: 14 }}>Data export is coming soon</b>
        <span>Everything OpenWatch receives is already being archived. Exporting a time, area and feed slice as
          GeoJSON, CSV or Parquet (with source evidence and a manifest) will open here shortly.</span>
      </div>
    </div>
  );
}

const local = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);

function Export({ feeds, bounds }: { feeds: FeedMeta[]; bounds: [number, number, number, number] | null }) {
  const [picked, setPicked] = useState<string[]>([]);
  const [start, setStart] = useState(local(new Date(Date.now() - 864e5)));
  const [end, setEnd] = useState(local(new Date()));
  const [useView, setUseView] = useState(false);
  const [format, setFormat] = useState<"geojson" | "csv" | "parquet">("geojson");
  const [raw, setRaw] = useState(false);
  const [timeField, setTimeField] = useState<"fetched" | "observed">("fetched");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const go = async () => {
    setBusy(true); setMsg(null);
    try {
      await runExport({ feeds: picked, start: new Date(start).toISOString(), end: new Date(end).toISOString(),
        bbox: useView && bounds ? bounds.map((x) => +x.toFixed(4)) : null, format, include_unlocated: !useView, include_raw: raw, time_field: timeField });
      setMsg({ ok: true, text: "Export downloaded." });
    } catch (e: any) { setMsg({ ok: false, text: e.message }); } finally { setBusy(false); }
  };
  return (
    <div className="scroll">
      <div className="form">
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>
          Everything OpenWatch receives is archived. Export a slice as a zip: one file per feed, plus a manifest with the query,
          counts, source licences and checksums.
        </p>
        <div className="field">
          <span>Feeds <button className="link" style={{ float: "right" }} onClick={() => setPicked(picked.length ? [] : feeds.map((f) => f.id))}>
            {picked.length ? "Clear" : "Select all"}</button></span>
          <div className="picklist">
            {feeds.map((f) => (
              <label key={f.id} className="check"><input type="checkbox" checked={picked.includes(f.id)}
                onChange={() => setPicked(picked.includes(f.id) ? picked.filter((x) => x !== f.id) : [...picked, f.id])} />{f.label}</label>
            ))}
          </div>
        </div>
        <div className="row2">
          <label className="field"><span>From</span><input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} /></label>
          <label className="field"><span>To</span><input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        </div>
        <label className="field"><span>Window applies to</span>
          <select value={timeField} onChange={(e) => setTimeField(e.target.value as any)}>
            <option value="fetched">When OpenWatch received it</option><option value="observed">When the event happened (source time)</option>
          </select></label>
        <label className="field"><span>Format</span>
          <select value={format} onChange={(e) => setFormat(e.target.value as any)}>
            <option value="geojson">GeoJSON</option><option value="csv">CSV</option><option value="parquet">Parquet (best for datasets)</option>
          </select></label>
        <label className="check"><input type="checkbox" checked={useView} onChange={() => setUseView(!useView)} />Only what's inside the current map view</label>
        <label className="check"><input type="checkbox" checked={raw} onChange={() => setRaw(!raw)} />Include original source responses (evidence)</label>
        <button className="btn primary" style={{ justifyContent: "center", height: 36 }} disabled={!picked.length || busy} onClick={go}>
          <Download size={15} />{busy ? "Preparing…" : `Export ${picked.length || ""} feed${picked.length === 1 ? "" : "s"}`}
        </button>
        {msg && <small style={{ color: msg.ok ? "var(--live)" : "#ff9b9c" }}>{msg.text}</small>}
      </div>
    </div>
  );
}
