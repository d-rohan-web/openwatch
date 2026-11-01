import { useEffect, useMemo, useState } from "react";
import { getBootstrap, getFeeds, getHistory, getWindow, subscribe } from "./api";
import { inArea, inScope as within, MOVING_FEEDS, passOver, type Area } from "./features";
import { MapView, type Overlays, type Scope } from "./MapView";
import type { FeedMeta, Rec } from "./types";
import { CommandPalette } from "./ui/CommandPalette";
import { IntelPanel, type Tab } from "./ui/IntelPanel";
import { LayerDock, type Extra } from "./ui/LayerDock";
import { Notice } from "./ui/Notice";
import { StateCard } from "./ui/StateCard";
import { Stats } from "./ui/Stats";
import { TopBar } from "./ui/TopBar";

// First visit shows the essentials only; everything else is one click away in its category card or a View.
export const OVERVIEW = ["aircraft", "opensky", "satellites", "sachet", "imd_warnings", "imd_nowcast", "imd_cyclone", "ncs_quakes",
  "cwc_rivers", "incois", "ioda", "launches", "markets_india", "fx_inr", "commodities_india", "volcanoes"];
const DEFAULT_OVERLAYS: Overlays = { highways: false, railways: false, rivers: true, defacto: false, states: true, maritime: true, orbits: false };
type GeoArea = { name: string; area: Area };

// Remembered per browser; storage can be unavailable (private mode), so every access is guarded.
function useStored<T>(key: string, init: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(() => { try { const s = localStorage.getItem(key); return s ? JSON.parse(s) : init; } catch { return init; } });
  return [v, (n: T) => { setV(n); try { localStorage.setItem(key, JSON.stringify(n)); } catch { /* not persisted */ } }];
}
const toArea = (g: any): Area => (g.type === "Polygon" ? [g.coordinates] : g.coordinates);

export function App() {
  const [feeds, setFeeds] = useState<FeedMeta[]>([]);
  const [live, setLive] = useState<Record<string, Rec[]>>({});
  const [lastUpdate, setLastUpdate] = useState(0);
  const [offStored, setOff] = useStored<string[] | null>("openwatch.off3", null);
  const [traffic, setTraffic] = useStored("openwatch.traffic", false);
  const [overlaysRaw, setOverlays] = useStored<Partial<Overlays>>("openwatch.overlays", DEFAULT_OVERLAYS);
  const overlays: Overlays = { ...DEFAULT_OVERLAYS, ...overlaysRaw };
  const [scope, setScope] = useStored<Scope>("openwatch.scope", "india");
  const [threeD, setThreeD] = useStored("openwatch.3d", false);
  const [day, setDay] = useStored("openwatch.day", false);
  const [windowH, setWindowH] = useStored("openwatch.window", 0); // 0 = live only; 6/12/24 = also what the archive saw
  const [past, setPast] = useState<Record<string, Rec[]>>({});
  const [tab, setTab] = useStored<Tab>("openwatch.tab", "alerts");
  const [collapsed, setCollapsed] = useStored("openwatch.collapsed", false);
  const [cfg, setCfg] = useState({ traffic_tiles: false, global: false, export: false });
  const [sel, setSel] = useState<{ feed: string; id: string } | null>(null);
  const [history, setHistory] = useState<Rec[]>([]);
  const [flyTo, setFlyTo] = useState<{ lon: number; lat: number; zoom?: number; n: number } | null>(null);
  const [bounds, setBounds] = useState<[number, number, number, number] | null>(null);
  const [palette, setPalette] = useState(false);
  const [seenNotice, setSeenNotice] = useStored("openwatch.notice", false);
  const [notice, setNotice] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [indiaArea, setIndiaArea] = useState<Area | null>(null);
  const [states, setStates] = useState<GeoArea[]>([]);
  const [stateName, setStateName] = useState<string | null>(null);

  useEffect(() => {
    const load = () => getFeeds().then(setFeeds).catch(() => {}); // health refresh; the first load is the bootstrap
    fetch("/geo/scope.geojson").then((r) => r.json()).then((g) => setIndiaArea(toArea(g.features[0].geometry))).catch(() => {});
    fetch("/geo/states.geojson").then((r) => r.json())
      .then((g) => setStates(g.features.map((f: any) => ({ name: f.properties.name, area: toArea(f.geometry) })))).catch(() => {});
    const boot = () => getBootstrap().then((b) => { setCfg(b.config); setFeeds(b.feeds); setLive(b.live); setLastUpdate(Date.now()); }).catch(() => {});
    boot();
    const t = setInterval(load, 30000), c = setInterval(() => setNow(Date.now()), 1000);
    const unsub = subscribe((feed, records, health) => {
      if (records) setLive((l) => ({ ...l, [feed]: records }));
      setLastUpdate(Date.now());
      if (health) setFeeds((fs) => fs.map((f) => (f.id === feed ? { ...f, health } : f)));
    }, boot);
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((v) => !v); }
    };
    window.addEventListener("keydown", key);
    return () => { clearInterval(t); clearInterval(c); unsub(); window.removeEventListener("keydown", key); };
  }, []);

  useEffect(() => { if (scope === "global" && !cfg.global && feeds.length) setScope("india"); }, [cfg.global, feeds.length]);

  // OpenSky and adsb.fi see many of the same aircraft: show adsb.fi's (fresher, richer) where both have it.
  // Time window: add what each feed showed in the last N hours and isn't live any more, marked _past (drawn faded).
  const mapLive = useMemo(() => {
    const out = { ...live };
    if (live.opensky && live.aircraft) {
      const seen = new Set(live.aircraft.map((r) => r.id));
      out.opensky = live.opensky.filter((r) => !seen.has(r.id));
    }
    for (const [feed, recs] of Object.entries(past)) {
      const seen = new Set((live[feed] ?? []).map((r) => r.id));
      out[feed] = [...(live[feed] ?? []), ...recs.filter((r) => !seen.has(r.id)).map((r) => ({ ...r, attrs: { ...r.attrs, _past: true } }))];
    }
    return out;
  }, [live, past]);

  // moving things (aircraft, ships, satellites) and market prices stay live-only: hours of them is clutter, not situation
  const windowFeeds = feeds.filter((f) => !MOVING_FEEDS.has(f.id) && f.section !== "economy" && f.health?.state !== "NEEDS_KEY").map((f) => f.id).join();
  useEffect(() => {
    setPast({});
    if (!windowH || !windowFeeds) return;
    const load = () => Promise.all(windowFeeds.split(",").map((f) => getWindow(f, windowH).then((r) => [f, r] as const).catch(() => [f, []] as const)))
      .then((pairs) => setPast(Object.fromEntries(pairs)));
    load();
    const t = setInterval(load, 5 * 60e3);
    return () => clearInterval(t);
  }, [windowH, windowFeeds]);

  const off = offStored ?? feeds.map((f) => f.id).filter((id) => !OVERVIEW.includes(id));
  const on = useMemo(() => new Set(feeds.map((f) => f.id).filter((id) => !off.includes(id))), [feeds, offStored]);
  const setOn = (ids: string[]) => setOff(feeds.map((f) => f.id).filter((id) => !ids.includes(id)));
  const toggle = (id: string) => setOn(on.has(id) ? [...on].filter((x) => x !== id) : [...on, id]);
  const area = scope === "india" ? indiaArea : null;
  const inScope = (r: Rec) => within(r, area);
  const visible = useMemo(() => Object.entries(mapLive).filter(([f]) => on.has(f)).flatMap(([, r]) => r).filter(inScope), [mapLive, on, area]);
  const allRecs = useMemo(() => Object.values(mapLive).flat().filter(inScope), [mapLive, area]);
  const selected = sel ? live[sel.feed]?.find((r) => r.id === sel.id) ?? history[history.length - 1] : undefined;
  const stateArea = states.find((s) => s.name === stateName)?.area;
  const inState = useMemo(() => (stateArea ? allRecs.filter((r) => r.lon !== null && inArea(r.lon, r.lat!, stateArea)) : []), [allRecs, stateArea]);
  const economy = new Set(feeds.filter((f) => f.section === "economy").map((f) => f.id));
  const ticker = Object.entries(live).filter(([f]) => economy.has(f) && on.has(f)).flatMap(([, r]) => r);

  const flip = (k: keyof Overlays) => setOverlays({ ...overlays, [k]: !overlays[k] });
  const extras: Extra[] = [
    { id: "orbits", section: "space", label: "Orbits of all Indian satellites", meta: "ground tracks ahead · click one satellite to see just its pass",
      color: "#b69cff", on: overlays.orbits, available: true, toggle: () => flip("orbits") },
    { id: "maritime", section: "sea", label: "Maritime zones: 12 nm, 24 nm, EEZ", meta: "Marine Regions (VLIZ) · territorial sea, contiguous zone, EEZ",
      color: "#38bdf8", on: overlays.maritime, available: true, toggle: () => flip("maritime") },
    { id: "rivers", section: "hazards", label: "Rivers & canals (OSM)", meta: "OpenStreetMap · names when zoomed in", color: "#38bdf8",
      on: overlays.rivers, available: true, toggle: () => flip("rivers") },
    { id: "highways", section: "infrastructure", label: "National highways & expressways (OSM)", meta: "OpenStreetMap · motorway / trunk",
      color: "#f59e0b", on: overlays.highways, available: true, toggle: () => flip("highways") },
    { id: "railways", section: "infrastructure", label: "Railway lines (OSM)", meta: "OpenStreetMap", color: "#a78bfa",
      on: overlays.railways, available: true, toggle: () => flip("railways") },
    { id: "traffic", section: "infrastructure", label: "Live road traffic flow (TomTom)", color: "#4ade80",
      meta: cfg.traffic_tiles ? "TomTom · tiles" : "set TOMTOM_KEY in .env to enable", on: traffic && cfg.traffic_tiles,
      available: cfg.traffic_tiles, toggle: () => setTraffic(!traffic) },
    { id: "defacto", section: "defence", label: "LoC / LAC (de facto, approx.)", meta: "Natural Earth · not recognised by India as boundaries",
      color: "#f87171", on: overlays.defacto, available: true, toggle: () => flip("defacto") },
    { id: "states", section: "govt", label: "State boundaries (click to focus)", meta: "datameet · 36 states & UTs", color: "#ff9933",
      on: overlays.states, available: true, toggle: () => flip("states") },
  ];

  const pick = (r: Rec) => {
    setSel({ feed: r.feed, id: r.id }); setHistory([]); setCollapsed(false);
    if (tab !== "alerts" && tab !== "sats") setTab(r.feed === "satellites" ? "sats" : "alerts");
    // satellites: an orbit-scale view (track + footprint), everything else close in
    if (r.lon !== null && r.lat !== null) setFlyTo({ lon: r.lon, lat: r.lat, zoom: r.feed === "satellites" ? 2.8 : undefined, n: Date.now() });
  };

  return (
    <div className={`shell ${collapsed ? "panel-collapsed" : ""}`}>
      <MapView live={mapLive} feeds={feeds} on={on} traffic={traffic && cfg.traffic_tiles} scope={scope} area={area}
        overlays={overlays} threeD={threeD} day={day} panelOpen={!collapsed} state={stateName} onState={setStateName} selected={sel}
        select={(feed, id) => { setSel({ feed, id }); setHistory([]); setTab(feed === "satellites" ? "sats" : "alerts"); setCollapsed(false); }}
        history={history} flyTo={flyTo} onBounds={setBounds} />
      <TopBar scope={scope} setScope={setScope} globalReady={cfg.global} feeds={feeds} now={now} lastUpdate={lastUpdate}
        threeD={threeD} setThreeD={setThreeD} day={day} setDay={setDay} windowH={windowH} setWindowH={setWindowH}
        openSearch={() => setPalette(true)} openFeeds={() => { setTab("feeds"); setCollapsed(false); }} openNotice={() => setNotice(true)} />
      <LayerDock feeds={feeds} live={mapLive} on={on} setOn={setOn} extras={extras} now={now} />
      {stateName && <StateCard name={stateName} records={inState} feeds={feeds} now={now} back={() => setStateName(null)} pick={pick} />}
      <IntelPanel tab={tab} setTab={setTab} collapsed={collapsed} setCollapsed={setCollapsed} feeds={feeds} records={visible} now={now}
        bounds={bounds} selected={selected} selectedMeta={feeds.find((f) => f.id === sel?.feed)} pick={pick}
        clearSel={() => { setSel(null); setHistory([]); }} historyCount={history.length}
        loadHistory={() => selected && getHistory(selected.feed, selected.id).then(setHistory)}
        satellites={live.satellites ?? []} passFor={(r) => passOver(r, indiaArea, now)} exportEnabled={cfg.export} />
      <Stats live={mapLive} inScope={inScope} ticker={ticker} show={(fs) => setOn([...new Set([...on, ...fs])])} />
      {(notice || !seenNotice) && <Notice close={() => { setSeenNotice(true); setNotice(false); }} />}
      <CommandPalette open={palette} close={() => setPalette(false)} feeds={feeds} records={allRecs} on={on} toggle={toggle} pick={pick}
        states={states.map((s) => s.name)} pickState={setStateName}
        fly={(lon, lat) => setFlyTo({ lon, lat, zoom: 8.5, n: Date.now() })} />
    </div>
  );
}
