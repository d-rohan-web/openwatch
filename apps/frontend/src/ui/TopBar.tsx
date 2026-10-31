import { Box, Github, Globe2, MapPinned, Search } from "lucide-react";
import type { Scope } from "../MapView";
import type { FeedMeta } from "../types";
import { Mark, STATE } from "./common";

type Props = { scope: Scope; setScope: (s: Scope) => void; globalReady: boolean; feeds: FeedMeta[]; now: number;
  threeD: boolean; setThreeD: (v: boolean) => void;
  lastUpdate: number; openSearch: () => void; openFeeds: () => void };

export function TopBar({ scope, setScope, globalReady, feeds, now, threeD, setThreeD, lastUpdate, openSearch, openFeeds }: Props) {
  const running = feeds.filter((f) => f.health?.state !== "NEEDS_KEY");
  const ok = running.filter((f) => f.health?.state === "OK").length;
  const bad = running.filter((f) => f.health?.state === "DOWN" || f.health?.state === "DEGRADED").length;
  const fresh = now - lastUpdate < 30000;
  return (
    <header className="overlay glass topbar">
      <div className="brand">
        <Mark />
        <div>
          <div className="brand-name">OpenWatch<sub>India</sub></div>
          <div className="brand-sub">Open-source situational awareness</div>
        </div>
      </div>
      <span className="divider" />
      <div className="seg" role="radiogroup" aria-label="Coverage">
        <button role="radio" aria-checked={scope === "india"} className={scope === "india" ? "on" : ""} onClick={() => setScope("india")}>
          <MapPinned size={14} /> India
        </button>
        <button role="radio" aria-checked={scope === "global"} className={scope === "global" ? "on" : ""} disabled={!globalReady}
          title={globalReady ? "Worldwide coverage" : "Global coverage is coming soon"} onClick={() => setScope("global")}>
          <Globe2 size={14} /> Global{!globalReady && <span className="soon">Soon</span>}
        </button>
      </div>
      <button className={`view-btn ${threeD ? "on" : ""}`} onClick={() => setThreeD(!threeD)} aria-pressed={threeD}
        title={threeD ? "Back to flat 2D map" : "3D: terrain, tilt (right-drag to rotate), buildings when zoomed in"}>
        <Box size={13} /> {threeD ? "3D" : "2D"}
      </button>
      <button className="search-trigger" onClick={openSearch} aria-label="Search">
        <Search size={15} /><span className="grow">Search layers, callsigns, places, alerts…</span><kbd>⌘K</kbd>
      </button>
      <span className="live" style={{ color: fresh ? "var(--live)" : "var(--muted)" }} title={fresh ? "Receiving updates" : "No update in 30 s"}>
        <i className="pulse" /> {fresh ? "LIVE" : "IDLE"}
      </span>
      <button className="health-pill" onClick={openFeeds} title="Feed health">
        <i className="dot" style={{ background: bad ? STATE.DEGRADED.color : STATE.OK.color }} />
        <span className="num">{ok}/{running.length}</span><span>feeds</span>
      </button>
      <a className="icon-btn gh" href="https://github.com/d-rohan-web/openwatch" target="_blank" rel="noreferrer"
        title="OpenWatch on GitHub: source, issues, contribute" aria-label="OpenWatch on GitHub">
        <Github size={17} />
      </a>
      <div className="clock" aria-label="Time">
        <b className="num">{new Date(now).toLocaleTimeString("en-GB", { timeZone: "Asia/Kolkata" })}</b>
        <small>IST · {new Date(now).toISOString().slice(11, 16)}Z</small>
      </div>
    </header>
  );
}
