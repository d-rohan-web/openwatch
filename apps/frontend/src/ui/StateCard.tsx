// Floating summary of the clicked state: what's happening inside it right now.
import { ArrowLeft, MapPin } from "lucide-react";
import { useMemo } from "react";
import { SEVERITY_COLOR, SEVERITY_RANK, type FeedMeta, type Rec, type Severity } from "../types";
import { ago } from "./common";

const SEVS: Severity[] = ["critical", "warning", "advisory"];
const COUNTS: { label: string; test: (r: Rec) => boolean }[] = [
  { label: "Aircraft overhead", test: (r) => (r.feed === "aircraft" || r.feed === "opensky") && !r.attrs.on_ground },
  { label: "Weather warnings", test: (r) => r.feed === "imd_warnings" || r.feed === "imd_nowcast" },
  { label: "Rivers above warning", test: (r) => r.feed === "cwc_rivers" },
  { label: "Quakes", test: (r) => r.kind === "earthquake" },
  { label: "Defence sites", test: (r) => r.feed === "defence_sites" },
  { label: "Airports", test: (r) => r.feed === "airports" },
];

export function StateCard({ name, records, feeds, now, back, pick }: {
  name: string; records: Rec[]; feeds: FeedMeta[]; now: number; back: () => void; pick: (r: Rec) => void;
}) {
  const label = (id: string) => feeds.find((f) => f.id === id)?.label ?? id;
  const alerts = useMemo(() => records.filter((r) => r.severity && SEVERITY_RANK[r.severity] >= 1)
    .sort((a, b) => SEVERITY_RANK[b.severity!] - SEVERITY_RANK[a.severity!] || (b.observed_at ?? "").localeCompare(a.observed_at ?? "")), [records]);
  const counts = COUNTS.map((c) => ({ ...c, n: records.filter(c.test).length })).filter((c) => c.n > 0);
  return (
    <div className="overlay glass state-card" role="region" aria-label={`${name} summary`}>
      <div className="sc-head">
        <MapPin size={15} color="#ff9933" />
        <b className="grow">{name}</b>
        <button className="btn" style={{ height: 26 }} onClick={back}><ArrowLeft size={13} />India</button>
      </div>
      <div className="sc-sev">
        {SEVS.map((s) => (
          <div key={s} style={{ color: SEVERITY_COLOR[s] }}>
            <b className="num">{alerts.filter((r) => r.severity === s).length}</b><small>{s}</small>
          </div>
        ))}
      </div>
      {counts.length > 0 && (
        <div className="sc-counts">
          {counts.map((c) => <span key={c.label}><b className="num">{c.n.toLocaleString()}</b> {c.label.toLowerCase()}</span>)}
        </div>
      )}
      <div className="sc-list scroll">
        {!alerts.length && <div className="empty" style={{ padding: 14 }}>No active alerts in {name}.</div>}
        {alerts.slice(0, 30).map((r) => (
          <button key={r.feed + r.id} className="item" onClick={() => pick(r)}>
            <i className="sev-bar" style={{ background: SEVERITY_COLOR[r.severity!] }} />
            <span className="grow"><span className="item-title">{r.title}</span>
              <span className="item-meta">{label(r.feed)} · {ago(r.observed_at ?? r.fetched_at, now)} ago</span></span>
          </button>
        ))}
      </div>
    </div>
  );
}
