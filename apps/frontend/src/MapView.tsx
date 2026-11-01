// The map: one GeoJSON source per feed over a retinted dark basemap, drawn as a globe you can spin freely. India scope
// dims everything outside the official outline (Survey of India, via datameet); the basemap's own borders are hidden and
// replaced by our border layers. States are clickable; 3D adds terrain, tilt and buildings.
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import * as lucide from "lucide";
import { alongTrack, FEED_ICON, feedColor, GLYPHS, inArea, inScope, MOVING_FEEDS, toFeatures, trackStep, type Area } from "./features";
import { SEVERITY_RANK } from "./types";
import { INDIA_FIT } from "./sections";
import type { FeedMeta, Rec } from "./types";

const STYLE = "https://tiles.openfreemap.org/styles/dark";
const DEM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"; // AWS Open Data terrain tiles
export type Scope = "india" | "global";
export type Overlays = { highways: boolean; railways: boolean; rivers: boolean; defacto: boolean; states: boolean; maritime: boolean; orbits: boolean };
// Keep India clear of the floating UI: top bar + dock (top), KPI bar (bottom), intel panel (right, unless collapsed).
const fitPad = (panel: boolean) => ({ top: 118, bottom: 108, left: 24, right: panel ? 404 : 24 });
let FIT_PAD = fitPad(true);
const FONT = ["Noto Sans Regular"];

type Props = {
  live: Record<string, Rec[]>; feeds: FeedMeta[]; on: Set<string>; traffic: boolean; scope: Scope; area: Area | null;
  overlays: Overlays; threeD: boolean; panelOpen: boolean; state: string | null; onState: (name: string | null) => void;
  select: (feed: string, id: string) => void; selected: { feed: string; id: string } | null; history: Rec[];
  flyTo: { lon: number; lat: number; zoom?: number; n: number } | null;
  onBounds: (b: [number, number, number, number]) => void;
};

// Our palette on top of the OpenFreeMap dark style (layer ids from that style).
const TINT: [RegExp, string, string][] = [
  [/^background$/, "background-color", "#0b111f"],
  [/^water$/, "fill-color", "#04070e"],
  [/^waterway$/, "line-color", "#0a1222"],
  [/^landcover|^landuse/, "fill-color", "#0d1424"],
  [/^building$/, "fill-color", "#101828"],
  [/^highway_(minor|path)/, "line-color", "#141c2e"],
  [/^highway_major|^highway_motorway/, "line-color", "#1b253b"],
  [/^railway/, "line-color", "#1a2336"],
  [/^aeroway/, "line-color", "#1d2740"],
  [/^place_(city|state|country)/, "text-color", "#8994ac"],
  [/^place_/, "text-color", "#5f6b84"],
  [/^place_|^water_name|^highway_name/, "text-halo-color", "#05070d"],
  [/^highway_name/, "text-color", "#4b566d"],
];

function icon(draw: (g: CanvasRenderingContext2D, s: number) => void): ImageData {
  const s = 48, c = document.createElement("canvas");
  c.width = c.height = s;
  const g = c.getContext("2d")!;
  g.fillStyle = "#fff";
  draw(g, s);
  return g.getImageData(0, 0, s, s);
}
// Top-down airliner: fuselage, swept wings, tailplane (nose up = heading 0).
const plane = icon((g) => {
  g.beginPath();
  g.moveTo(24, 3); g.bezierCurveTo(26.5, 3, 27, 7, 27, 10); g.lineTo(27, 19);
  g.lineTo(44, 27); g.lineTo(44, 31); g.lineTo(27, 26.5); g.lineTo(26.5, 37);
  g.lineTo(32, 41); g.lineTo(32, 44); g.lineTo(24, 41.5); g.lineTo(16, 44); g.lineTo(16, 41);
  g.lineTo(21.5, 37); g.lineTo(21, 26.5); g.lineTo(4, 31); g.lineTo(4, 27); g.lineTo(21, 19);
  g.lineTo(21, 10); g.bezierCurveTo(21, 7, 21.5, 3, 24, 3); g.closePath(); g.fill();
});
// Ship: pointed hull seen from above.
const ship = icon((g) => {
  g.beginPath(); g.moveTo(24, 4); g.bezierCurveTo(31, 14, 31, 22, 30, 42); g.lineTo(18, 42);
  g.bezierCurveTo(17, 22, 17, 14, 24, 4); g.closePath(); g.fill();
});

// Render a lucide icon (white strokes) into an SDF sprite image so each point can be tinted by its colour.
async function glyphImage(name: string): Promise<ImageData | null> {
  const key = name.replace(/(^|-)(\w)/g, (_, __, c: string) => c.toUpperCase());
  const icon = (lucide as any)[key] as [string, object, [string, Record<string, string>][]] | undefined;  // ["svg", attrs, children]
  if (!icon) return null;
  const body = icon[2].map(([tag, attrs]) => `<${tag} ${Object.entries(attrs).map(([k, v]) => `${k}="${v}"`).join(" ")}/>`).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="-2 -2 28 28" fill="none" stroke="white" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
  const img = new Image();
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  await img.decode();
  const c = document.createElement("canvas");
  c.width = c.height = 48;
  const g = c.getContext("2d")!;
  g.drawImage(img, 0, 0, 48, 48);
  return g.getImageData(0, 0, 48, 48);
}

const LAYERS = ["fill", "line", "glow", "circle", "glyph", "icon", "cluster", "count"] as const;
// District-level alert feeds are drawn as shaded districts (max severity), not as hundreds of centroid dots.
export const DISTRICT_FEEDS = new Set(["imd_warnings", "imd_nowcast", "sachet"]);
// Dense, static point layers merge into count bubbles when zoomed out.
const CLUSTER = new Set(["navarea8", "airports", "airport_infra", "defence_sites", "nuclear", "border_posts", "ncs_quakes", "usgs_quakes", "gdelt",
  "incois", "city_weather", "cwc_rivers", "launches", "ioda", "cpcb_aqi", "firms", "road_incidents", "volcanoes"]);
const NOT_CLUSTER = ["!", ["has", "point_count"]] as any;
const MINOR = ["boolean", ["get", "minor"], false] as any;
const HAS_GLYPH = ["!=", ["get", "glyph"], ""] as any;
// Zoom from which points become icon badges; fixed places worth seeing nationwide get them early.
const BADGE_ZOOM: Record<string, number> = { satellites: 0, airports: 3, defence_sites: 3, nuclear: 3, border_posts: 4, launches: 3, cwc_rivers: 4 };

function addFeedLayers(map: maplibregl.Map, id: string, color: string) {
  const src = `src-${id}`;
  const bz = BADGE_ZOOM[id] ?? 3;
  map.addSource(src, { type: "geojson", data: { type: "FeatureCollection", features: [] },
    ...(CLUSTER.has(id) ? { cluster: true, clusterRadius: 60, clusterMaxZoom: 7, clusterProperties: { sev: ["max", ["get", "sev"]] } } : {}) });
  const isPoly = ["==", ["geometry-type"], "Polygon"] as any;
  const isLine = ["==", ["geometry-type"], "LineString"] as any;
  const isPoint = ["==", ["geometry-type"], "Point"] as any;
  const before = "borders";
  map.addLayer({ id: `${id}-fill`, type: "fill", source: src, filter: isPoly,
    paint: { "fill-color": ["get", "color"], "fill-opacity": 0.1 } }, before);
  map.addLayer({ id: `${id}-line`, type: "line", source: src, filter: ["any", isPoly, isLine],
    paint: { "line-color": ["get", "color"], "line-width": ["case", isLine, 1, 1.3], "line-opacity": ["case", isLine, id === "satellites" ? 0.35 : 0.45, 0.85],
      ...(id === "satellites" ? { "line-dasharray": [3, 2] } : {}) } }, before);
  // soft halo under alert points so severity reads at a glance
  map.addLayer({ id: `${id}-glow`, type: "circle", source: src, filter: ["all", isPoint, NOT_CLUSTER, ["!", ["get", "arrow"]], ["==", ["get", "sev"], 3]],
    paint: { "circle-color": ["get", "color"], "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 11, 8, 20], "circle-opacity": 0.2, "circle-blur": 0.6 } });
  // a coloured dot when zoomed out; from zoom 5 a dark badge with a coloured ring and the kind's glyph inside
  map.addLayer({ id: `${id}-circle`, type: "circle", source: src, filter: ["all", isPoint, NOT_CLUSTER, ["!", ["get", "arrow"]]],
    paint: { "circle-color": ["step", ["zoom"], ["get", "color"], bz, ["case", HAS_GLYPH, "#0a0f1c", ["get", "color"]]],
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 3, bz, ["case", HAS_GLYPH, 8.5, 3.5], 9, ["case", HAS_GLYPH, 13, 6]],
      "circle-stroke-color": ["step", ["zoom"], "#05070d", bz, ["case", HAS_GLYPH, ["get", "color"], "#05070d"]],
      "circle-stroke-width": ["step", ["zoom"], 0.8, bz, ["case", HAS_GLYPH, 1.4, 0.8]],
      // minor items (small airstrips, heliports) only once zoomed in
      "circle-opacity": ["step", ["zoom"], ["case", MINOR, 0, 0.95], 7, 0.95], "circle-stroke-opacity": ["step", ["zoom"], ["case", MINOR, 0, 1], 7, 1] } });
  map.addLayer({ id: `${id}-glyph`, type: "symbol", source: src, minzoom: bz, filter: ["all", isPoint, NOT_CLUSTER, ["!", ["get", "arrow"]], HAS_GLYPH],
    layout: { "icon-image": ["get", "glyph"], "icon-allow-overlap": true, "icon-ignore-placement": true,
      "icon-size": ["interpolate", ["linear"], ["zoom"], bz, 0.32, 9, 0.48] },
    paint: { "icon-color": ["get", "color"] } });
  const isCluster = ["has", "point_count"] as any;
  const sevColor = ["match", ["get", "sev"], 3, "#ff4d4f", 2, "#ff8c1a", 1, "#ffd23f", color] as any;
  map.addLayer({ id: `${id}-cluster`, type: "circle", source: src, filter: isCluster,
    paint: { "circle-color": "#0a0f1c", "circle-stroke-color": sevColor, "circle-stroke-width": 1.2, "circle-opacity": 0.9,
      "circle-radius": ["step", ["get", "point_count"], 8.5, 10, 10.5, 50, 12.5, 200, 14.5] } });
  // a group shows its layer's icon in the ring, with the count as a small superscript
  map.addLayer({ id: `${id}-count`, type: "symbol", source: src, filter: isCluster,
    layout: { ...(FEED_ICON[id] ? { "icon-image": FEED_ICON[id], "icon-size": 0.3, "icon-allow-overlap": true } : {}),
      "text-field": ["get", "point_count_abbreviated"], "text-font": FONT, "text-size": 9, "text-allow-overlap": true,
      ...(FEED_ICON[id] ? { "text-offset": [1.15, -1.05], "text-anchor": "center" } : {}) },
    paint: { "icon-color": sevColor, "text-color": "#e7ecf4", "text-halo-color": "#0a0f1c", "text-halo-width": 2.2 } });
  map.addLayer({ id: `${id}-icon`, type: "symbol", source: src, filter: ["all", isPoint, ["get", "arrow"]],
    layout: { "icon-image": ["get", "icon"], "icon-rotate": ["get", "rot"], "icon-rotation-alignment": "map",
      "icon-pitch-alignment": "map", "icon-allow-overlap": true, "icon-ignore-placement": true,
      "icon-size": ["interpolate", ["linear"], ["zoom"], 3, 0.55, 6, 0.72, 10, 1.05] },
    paint: { "icon-color": ["get", "color"], "icon-halo-color": "#02040a", "icon-halo-width": 1.2 } });
}

// Footprint radius: how far from the sub-satellite point the satellite is above the horizon (km).
const footprintKm = (altKm: number) => 6371 * Math.acos(6371 / (6371 + altKm));
function circle([lon, lat]: [number, number], km: number, n = 72) {
  const ring: [number, number][] = [];
  const d = km / 6371, φ1 = (lat * Math.PI) / 180, λ1 = (lon * Math.PI) / 180;
  for (let i = 0; i <= n; i++) {
    const θ = (2 * Math.PI * i) / n;
    const φ2 = Math.asin(Math.sin(φ1) * Math.cos(d) + Math.cos(φ1) * Math.sin(d) * Math.cos(θ));
    const λ2 = λ1 + Math.atan2(Math.sin(θ) * Math.sin(d) * Math.cos(φ1), Math.cos(d) - Math.sin(φ1) * Math.sin(φ2));
    ring.push([(λ2 * 180) / Math.PI, Math.max(-85, Math.min(85, (φ2 * 180) / Math.PI))]);
  }
  return ring;
}

function drawPass(m: maplibregl.Map, r: Rec | undefined, now: number) {
  const src = m.getSource("pass") as maplibregl.GeoJSONSource | undefined;
  if (!src) return;
  if (!r || r.lon === null) { src.setData({ type: "FeatureCollection", features: [] }); return; }
  const pos = alongTrack(r, now) ?? [r.lon, r.lat!] as [number, number];
  const feats: any[] = [{ type: "Feature", properties: { part: "foot" }, geometry: { type: "Polygon", coordinates: [circle(pos, footprintKm(Number(r.attrs.alt_km) || 500))] } }];
  const c = r.geometry?.type === "LineString" ? (r.geometry.coordinates as [number, number][]) : [];
  if (c.length > 1 && r.observed_at) {
    const sMin = trackStep(r) / 60, step = (now - Date.parse(r.observed_at)) / 1000 / trackStep(r), k = Math.min(Math.floor(step) + 1, c.length);
    const every = sMin >= 20 ? 6 : 5; // a tick every 2 h on a 24 h figure-of-eight, every 10 min on a LEO pass
    feats.push({ type: "Feature", properties: { part: "done" }, geometry: { type: "LineString", coordinates: [...c.slice(0, k), pos] } });
    if (k < c.length) feats.push({ type: "Feature", properties: { part: "next" }, geometry: { type: "LineString", coordinates: [pos, ...c.slice(k)] } });
    c.forEach((pt, i) => {
      const min = Math.round((i - step) * sMin);
      const label = min >= 120 ? `+${Math.round(min / 60)}h` : `+${min}m`;
      if (min > 0 && i % every === 0) feats.push({ type: "Feature", properties: { part: "tick", label }, geometry: { type: "Point", coordinates: pt } });
    });
  }
  src.setData({ type: "FeatureCollection", features: feats });
}

export function MapView(p: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const ready = useRef(false);
  const added = useRef(new Set<string>());
  const props = useRef(p);
  props.current = p;
  const stateBox = useRef<Record<string, number[]>>({});
  const districtsRef = useRef<{ name: string; area: Area; bbox: number[] }[]>([]);
  const districtAlert = useRef<Map<number, Rec>>(new Map()); // district index → its most severe alert

  useEffect(() => {
    // a (re)created map starts empty: forget layers added to a previous instance (dev hot reload re-runs this effect)
    added.current = new Set(); ready.current = false;
    const m = new maplibregl.Map({ container: el.current!, style: STYLE, bounds: INDIA_FIT, fitBoundsOptions: { padding: FIT_PAD },
      attributionControl: { compact: true }, maxPitch: 75 });
    map.current = m;
    m.dragRotate.disable(); m.touchZoomRotate.disableRotation();
    m.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
    m.addControl(new maplibregl.ScaleControl({}), "bottom-right");
    fetch("/geo/states.geojson").then((r) => r.json()).then((g) => {
      stateBox.current = Object.fromEntries(g.features.map((f: any) => [f.properties.name, f.properties.bbox]));
    }).catch(() => {});
    const hover = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, maxWidth: "320px" });
    let hoverState: string | number | undefined;
    m.on("load", () => {
      m.setProjection({ type: "globe" });
      m.setSky({ "sky-color": "#05070d", "horizon-color": "#0b111f", "fog-color": "#05070d", "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 1, 7, 0] });
      for (const l of m.getStyle().layers) {
        if ((l as any)["source-layer"] === "boundary") { m.setLayoutProperty(l.id, "visibility", "none"); continue; }
        for (const [re, prop, val] of TINT) if (re.test(l.id)) try { m.setPaintProperty(l.id, prop, val); } catch { /* prop not on this layer type */ }
      }
      m.addImage("openwatch-plane", plane, { sdf: true, pixelRatio: 2 });
      m.addImage("openwatch-ship", ship, { sdf: true, pixelRatio: 2 });
      for (const g of GLYPHS) glyphImage(g).then((d) => { if (d && !m.hasImage(g)) m.addImage(g, d, { sdf: true, pixelRatio: 2 }); }).catch(() => {});
      // key-free road/rail overlays straight from the basemap's OpenStreetMap vector tiles
      // National highways = roads whose OSM ref starts with NH (and expressways), not every "trunk" road
      const nh = ["any", ["==", ["slice", ["coalesce", ["get", "ref"], ""], 0, 2], "NH"], ["==", ["get", "class"], "motorway"]] as any;
      m.addLayer({ id: "osm-highways", type: "line", source: "openmaptiles", "source-layer": "transportation_name",
        filter: nh, layout: { visibility: "none", "line-join": "round", "line-cap": "round" },
        paint: { "line-color": ["match", ["get", "class"], "motorway", "#fbbf24", "#f59e0b"], "line-opacity": 0.85,
          "line-width": ["interpolate", ["linear"], ["zoom"], 4, 0.8, 8, 1.8, 12, 3.2] } });
      m.addLayer({ id: "osm-highway-refs", type: "symbol", source: "openmaptiles", "source-layer": "transportation_name", minzoom: 6.5,
        filter: nh, layout: { visibility: "none", "symbol-placement": "line", "text-field": ["coalesce", ["get", "ref"], ["get", "name"]],
          "text-font": FONT, "text-size": 9.5, "symbol-spacing": 300 },
        paint: { "text-color": "#fde68a", "text-halo-color": "#1a1203", "text-halo-width": 1.6 } });
      m.addLayer({ id: "osm-railways", type: "line", source: "openmaptiles", "source-layer": "transportation",
        filter: ["==", ["get", "class"], "rail"], layout: { visibility: "none" },
        paint: { "line-color": "#a78bfa", "line-opacity": 0.75, "line-width": ["interpolate", ["linear"], ["zoom"], 4, 0.5, 10, 1.6],
          "line-dasharray": [3, 1.5] } });
      m.addLayer({ id: "osm-rivers", type: "line", source: "openmaptiles", "source-layer": "waterway",
        filter: ["in", ["get", "class"], ["literal", ["river", "canal"]]], layout: { visibility: "none", "line-join": "round" },
        paint: { "line-color": "#38bdf8", "line-opacity": ["interpolate", ["linear"], ["zoom"], 4, 0.45, 9, 0.8],
          "line-width": ["interpolate", ["linear"], ["zoom"], 4, 0.5, 8, 1.3, 12, 2.6] } });
      m.addLayer({ id: "osm-river-names", type: "symbol", source: "openmaptiles", "source-layer": "waterway", minzoom: 6,
        filter: ["==", ["get", "class"], "river"], layout: { visibility: "none", "symbol-placement": "line",
          "text-field": ["coalesce", ["get", "name:en"], ["get", "name"]], "text-font": FONT, "text-size": 10, "symbol-spacing": 350 },
        paint: { "text-color": "#7dd3fc", "text-halo-color": "#02030a", "text-halo-width": 1.3 } });
      m.addSource("traffic", { type: "raster", tiles: ["/api/tiles/traffic/{z}/{x}/{y}.png"], tileSize: 256, attribution: "Traffic © TomTom" });
      m.addLayer({ id: "traffic", type: "raster", source: "traffic", layout: { visibility: "none" }, paint: { "raster-opacity": 0.75 } });
      m.addSource("mask", { type: "geojson", data: "/geo/mask.geojson" });
      m.addLayer({ id: "mask", type: "fill", source: "mask", paint: { "fill-color": "#020308", "fill-opacity": 0.72 } });
      m.addSource("neighbours", { type: "geojson", data: "/geo/neighbours.geojson", attribution: "Borders: Natural Earth" });
      m.addLayer({ id: "neighbour-lines", type: "line", source: "neighbours", filter: ["==", ["get", "kind"], "border"],
        paint: { "line-color": "#3b4760", "line-width": 0.8, "line-dasharray": [2, 1.5] } });
      m.addLayer({ id: "neighbour-labels", type: "symbol", source: "neighbours", filter: ["==", ["get", "kind"], "label"],
        layout: { "text-field": ["upcase", ["get", "name"]], "text-font": FONT, "text-size": 11, "text-letter-spacing": 0.25 },
        paint: { "text-color": "#56627a", "text-halo-color": "#02030a", "text-halo-width": 1.2 } });
      m.addSource("maritime", { type: "geojson", data: "/geo/maritime.geojson", attribution: "Maritime zones: Marine Regions (VLIZ), CC BY 4.0" });
      const zc = ["match", ["get", "zone"], "TS", "#2dd4bf", "CZ", "#22d3ee", "#38bdf8"] as any;
      m.addLayer({ id: "maritime-fill", type: "fill", source: "maritime", layout: { visibility: "none" },
        paint: { "fill-color": zc, "fill-opacity": ["match", ["get", "zone"], "EEZ", 0.035, 0.05] } });
      m.addLayer({ id: "maritime-line", type: "line", source: "maritime", layout: { visibility: "none" },
        paint: { "line-color": zc, "line-width": ["match", ["get", "zone"], "EEZ", 1.2, 0.8], "line-opacity": 0.7,
          "line-dasharray": ["match", ["get", "zone"], "EEZ", ["literal", [4, 2]], ["literal", [1, 1.5]]] } });
      m.addLayer({ id: "maritime-label", type: "symbol", source: "maritime", filter: ["==", ["get", "zone"], "EEZ"],
        layout: { visibility: "none", "symbol-placement": "line", "text-field": "EEZ · 200 nm", "text-font": FONT, "text-size": 10,
          "symbol-spacing": 600 }, paint: { "text-color": "#7dd3fc", "text-halo-color": "#02030a", "text-halo-width": 1.4 } });
      m.addSource("districts", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      fetch("/geo/districts.geojson").then((r) => r.json()).then((g) => {
        g.features.forEach((f: any, i: number) => { f.id = i; });
        districtsRef.current = g.features.map((f: any) => {
          const area: Area = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
          const xs = area.flat(2).map((p) => p[0]), ys = area.flat(2).map((p) => p[1]);
          return { name: f.properties.name, area, bbox: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)] };
        });
        (m.getSource("districts") as maplibregl.GeoJSONSource).setData(g);
        m.fire("openwatch:districts");
      }).catch(() => {});
      m.addLayer({ id: "districts-alert", type: "fill", source: "districts",
        paint: { "fill-color": ["match", ["coalesce", ["feature-state", "sev"], 0], 3, "#ff4d4f", 2, "#ff8c1a", 1, "#ffd23f", "#000000"],
          "fill-opacity": ["match", ["coalesce", ["feature-state", "sev"], 0], 3, 0.42, 2, 0.34, 1, 0.24, 0] } });
      m.addLayer({ id: "districts-alert-line", type: "line", source: "districts",
        paint: { "line-color": ["match", ["coalesce", ["feature-state", "sev"], 0], 3, "#ff4d4f", 2, "#ff8c1a", 1, "#ffd23f", "#000000"],
          "line-width": 0.8, "line-opacity": ["match", ["coalesce", ["feature-state", "sev"], 0], 0, 0, 0.7] } });
      m.addLayer({ id: "districts", type: "line", source: "districts", minzoom: 6,
        paint: { "line-color": "#1e2840", "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.3, 9, 0.9] } });
      m.addSource("states", { type: "geojson", data: "/geo/states.geojson", promoteId: "name" });
      m.addLayer({ id: "states-fill", type: "fill", source: "states",
        paint: { "fill-color": "#ff9933", "fill-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.07,
          ["boolean", ["feature-state", "hover"], false], 0.05, 0] } });
      m.addLayer({ id: "states-line", type: "line", source: "states",
        paint: { "line-color": ["case", ["boolean", ["feature-state", "selected"], false], "#ff9933", "#33405c"],
          "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 1.6, ["boolean", ["feature-state", "hover"], false], 1.2, 0.6],
          "line-opacity": 0.9 } });
      m.addSource("india", { type: "geojson", data: "/geo/india.geojson", attribution: "Boundary: Survey of India via datameet (CC0 / CC BY 4.0)" });
      m.addLayer({ id: "india-glow", type: "line", source: "india", paint: { "line-color": "#ff9933", "line-width": 7, "line-opacity": 0.07, "line-blur": 4 } });
      m.addLayer({ id: "india-line", type: "line", source: "india", paint: { "line-color": "#ff9933", "line-width": 0.9, "line-opacity": 0.55 } });
      m.addSource("defacto", { type: "geojson", data: "/geo/defacto.geojson" });
      m.addLayer({ id: "defacto", type: "line", source: "defacto", layout: { visibility: "none" },
        paint: { "line-color": "#f87171", "line-width": 1.4, "line-dasharray": [1.5, 1.5], "line-opacity": 0.9 } });
      m.addLayer({ id: "defacto-label", type: "symbol", source: "defacto", layout: { visibility: "none", "symbol-placement": "line",
        "text-field": ["get", "label"], "text-font": FONT, "text-size": 10, "symbol-spacing": 400 },
        paint: { "text-color": "#fca5a5", "text-halo-color": "#02030a", "text-halo-width": 1.4 } });
      m.addSource("borders", { type: "geojson", data: "/geo/borders.geojson" });
      m.addLayer({ id: "borders", type: "line", source: "borders", layout: { "line-join": "round" },
        paint: { "line-color": "#ff9933", "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1.4, 8, 2.4] } });
      m.addLayer({ id: "border-labels", type: "symbol", source: "borders", minzoom: 4.2,
        layout: { "symbol-placement": "line", "text-field": ["get", "label"], "text-font": FONT, "text-size": 10.5,
          "text-letter-spacing": 0.08, "symbol-spacing": 500, "text-offset": [0, -0.9] },
        paint: { "text-color": "#ffb366", "text-halo-color": "#02030a", "text-halo-width": 1.5 } });
      // selected satellite: coverage footprint, flown part of the pass (dim), upcoming part (bright), minute ticks
      m.addSource("pass", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "pass-foot", type: "fill", source: "pass", filter: ["==", ["get", "part"], "foot"], paint: { "fill-color": "#b69cff", "fill-opacity": 0.07 } });
      m.addLayer({ id: "pass-foot-line", type: "line", source: "pass", filter: ["==", ["get", "part"], "foot"],
        paint: { "line-color": "#b69cff", "line-width": 1, "line-opacity": 0.5, "line-dasharray": [2, 2] } });
      m.addLayer({ id: "pass-done", type: "line", source: "pass", filter: ["==", ["get", "part"], "done"],
        paint: { "line-color": "#b69cff", "line-width": 1.5, "line-opacity": 0.3 } });
      m.addLayer({ id: "pass-next", type: "line", source: "pass", filter: ["==", ["get", "part"], "next"],
        paint: { "line-color": "#d8c8ff", "line-width": 2.2, "line-opacity": 0.9 } });
      m.addLayer({ id: "pass-tick", type: "circle", source: "pass", filter: ["==", ["get", "part"], "tick"],
        paint: { "circle-radius": 2.5, "circle-color": "#d8c8ff" } });
      m.addLayer({ id: "pass-tick-label", type: "symbol", source: "pass", filter: ["==", ["get", "part"], "tick"],
        layout: { "text-field": ["get", "label"], "text-font": FONT, "text-size": 10, "text-offset": [0, -1], "text-allow-overlap": true },
        paint: { "text-color": "#d8c8ff", "text-halo-color": "#02030a", "text-halo-width": 1.4 } });
      m.addSource("history", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "history", type: "line", source: "history", paint: { "line-color": "#ffffff", "line-width": 2, "line-opacity": 0.75, "line-dasharray": [1, 1.5] } });
      m.addSource("sel", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "sel", type: "circle", source: "sel", paint: { "circle-radius": 14, "circle-color": "transparent",
        "circle-stroke-color": "#ff9933", "circle-stroke-width": 2 } });
      m.addSource("dem", { type: "raster-dem", tiles: [DEM], tileSize: 256, encoding: "terrarium", maxzoom: 13,
        attribution: "Terrain: Mapzen / AWS Open Data" });
      ready.current = true;
      m.fire("openwatch:ready");
    });
    const recordLayers = () => [...added.current].flatMap((f) => ["cluster", "circle", "icon", "fill", "line"].map((l) => `${f}-${l}`)).filter((i) => m.getLayer(i));
    m.on("click", (e) => {
      const f = m.queryRenderedFeatures(e.point, { layers: recordLayers() })[0];
      if (f && f.layer.id.endsWith("-cluster")) {
        const src = m.getSource(f.source) as maplibregl.GeoJSONSource;
        src.getClusterExpansionZoom(f.properties.cluster_id).then((z) =>
          m.easeTo({ center: (f.geometry as any).coordinates, zoom: Math.min(z + 0.3, 12), duration: 700 }));
        return;
      }
      if (f) return props.current.select(f.properties.feed, f.properties.id);
      const d = m.queryRenderedFeatures(e.point, { layers: ["districts-alert"] }).find((x) => districtAlert.current.has(x.id as number));
      if (d) { const r = districtAlert.current.get(d.id as number)!; return props.current.select(r.feed, r.id); }
      if (!props.current.overlays.states) return;
      const s = m.queryRenderedFeatures(e.point, { layers: ["states-fill"] })[0];
      props.current.onState(s ? String(s.properties.name) : null);
    });
    m.on("mousemove", (e) => {
      const f = m.queryRenderedFeatures(e.point, { layers: [...recordLayers().filter((i) => !i.endsWith("-line")), "borders", "defacto"].filter((i) => m.getLayer(i)) })[0];
      // (recordLayers includes "-cluster" so bubbles get a tooltip too)
      const dz = m.queryRenderedFeatures(e.point, { layers: ["districts-alert"] }).find((x) => districtAlert.current.has(x.id as number));
      const s = props.current.overlays.states ? m.queryRenderedFeatures(e.point, { layers: ["states-fill"] })[0] : undefined;
      const id = s?.properties.name as string | undefined;
      if (hoverState !== id) {
        if (hoverState !== undefined) m.setFeatureState({ source: "states", id: hoverState }, { hover: false });
        if (id !== undefined) m.setFeatureState({ source: "states", id }, { hover: true });
        hoverState = id;
      }
      m.getCanvas().style.cursor = f || s || dz ? "pointer" : "";
      if (f && f.layer.id.endsWith("-cluster")) {
        const feed = f.layer.id.slice(0, -"-cluster".length);
        const label = props.current.feeds.find((x) => x.id === feed)?.label ?? feed;
        hover.setLngLat(e.lngLat).setText(`${f.properties.point_count} × ${label} · click to expand`).addTo(m);
      } else if (f) {
        const pr = f.properties;
        const text = f.layer.id === "borders" ? `${pr.label} · ${Number(pr.length_km).toLocaleString()} km (MHA)` :
          f.layer.id === "defacto" ? `${pr.label}. ${pr.note}` : pr.title;
        hover.setLngLat(e.lngLat).setText(text).addTo(m);
      } else if (dz) {
        const r = districtAlert.current.get(dz.id as number)!;
        hover.setLngLat(e.lngLat).setText(`${dz.properties.name}: ${r.title}`).addTo(m);
      } else if (s) hover.setLngLat(e.lngLat).setText(String(s.properties.name)).addTo(m);
      else hover.remove();
    });
    m.on("mouseout", () => hover.remove());
    const report = () => { const b = m.getBounds(); props.current.onBounds([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]); };
    m.on("moveend", report);
    return () => m.remove();
  }, []);

  const whenReady = (fn: (m: maplibregl.Map) => void) => {
    const m = map.current;
    if (!m) return;
    if (ready.current) fn(m); else m.once("openwatch:ready", () => fn(m));
  };
  const sections = () => Object.fromEntries(props.current.feeds.map((f) => [f.id, f.section]));

  // shade each district by the most severe active district-level alert inside it
  const shadeDistricts = (m: maplibregl.Map) => {
    const ds = districtsRef.current;
    if (!ds.length) return;
    const { live, on, area } = props.current;
    const best = new Map<number, Rec>();
    for (const feed of DISTRICT_FEEDS) {
      if (!on.has(feed)) continue;
      for (const r of live[feed] ?? []) {
        if (r.lon === null || !r.severity || SEVERITY_RANK[r.severity] < 1 || !inScope(r, area)) continue;
        const pts: [number, number][] = r.geometry?.type === "MultiPoint" ? r.geometry.coordinates : [[r.lon, r.lat!]];
        for (const [x, y] of pts) {
          const i = ds.findIndex((d) => x >= d.bbox[0] && x <= d.bbox[2] && y >= d.bbox[1] && y <= d.bbox[3] && inArea(x, y, d.area));
          if (i < 0) continue;
          const cur = best.get(i);
          if (!cur || SEVERITY_RANK[r.severity] > SEVERITY_RANK[cur.severity!]) best.set(i, r);
        }
      }
    }
    for (const i of districtAlert.current.keys()) if (!best.has(i)) m.setFeatureState({ source: "districts", id: i }, { sev: 0 });
    for (const [i, r] of best) m.setFeatureState({ source: "districts", id: i }, { sev: SEVERITY_RANK[r.severity!] });
    districtAlert.current = best;
  };
  useEffect(() => whenReady((m) => m.on("openwatch:districts", () => shadeDistricts(m))), []);

  useEffect(() => whenReady((m) => {
    const sec = sections(), now = Date.now();
    for (const [feed, recs] of Object.entries(p.live)) {
      if (!added.current.has(feed)) { addFeedLayers(m, feed, feedColor(feed, sec[feed])); added.current.add(feed); }
      if (DISTRICT_FEEDS.has(feed)) { (m.getSource(`src-${feed}`) as maplibregl.GeoJSONSource).setData({ type: "FeatureCollection", features: [] }); continue; }
      const selId = p.selected?.feed === feed ? p.selected.id : undefined;
      (m.getSource(`src-${feed}`) as maplibregl.GeoJSONSource).setData(toFeatures(recs, sec[feed], p.area, MOVING_FEEDS.has(feed) ? now : undefined, selId, p.overlays.orbits) as any);
      const vis = p.on.has(feed) ? "visible" : "none";
      for (const l of LAYERS) m.setLayoutProperty(`${feed}-${l}`, "visibility", vis);
    }
    m.setLayoutProperty("traffic", "visibility", p.traffic ? "visible" : "none");
    shadeDistricts(m);
    for (const id of ["history", "sel"]) m.moveLayer(id);
  }), [p.live, p.on, p.feeds, p.traffic, p.area, p.selected, p.overlays.orbits]);

  // glide moving things between reports (aircraft, ships): re-project once a second
  useEffect(() => {
    const t = setInterval(() => whenReady((m) => {
      const { live, on, area } = props.current, sec = sections(), now = Date.now();
      const sel = props.current.selected;
      for (const feed of MOVING_FEEDS) {
        if (!on.has(feed) || !live[feed] || !added.current.has(feed)) continue;
        const selId = sel?.feed === feed ? sel.id : undefined;
        (m.getSource(`src-${feed}`) as maplibregl.GeoJSONSource).setData(toFeatures(live[feed], sec[feed], area, now, selId, props.current.overlays.orbits) as any);
      }
      drawPass(m, sel?.feed === "satellites" ? live.satellites?.find((r) => r.id === sel.id) : undefined, now);
    }), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => whenReady((m) => {
    const vis = (b: boolean) => (b ? "visible" : "none");
    m.setLayoutProperty("osm-highways", "visibility", vis(p.overlays.highways));
    m.setLayoutProperty("osm-highway-refs", "visibility", vis(p.overlays.highways));
    for (const id of ["maritime-fill", "maritime-line", "maritime-label"]) m.setLayoutProperty(id, "visibility", vis(p.overlays.maritime));
    m.setLayoutProperty("osm-railways", "visibility", vis(p.overlays.railways));
    m.setLayoutProperty("osm-rivers", "visibility", vis(p.overlays.rivers));
    m.setLayoutProperty("osm-river-names", "visibility", vis(p.overlays.rivers));
    m.setLayoutProperty("defacto", "visibility", vis(p.overlays.defacto));
    m.setLayoutProperty("defacto-label", "visibility", vis(p.overlays.defacto));
    m.setLayoutProperty("states-line", "visibility", vis(p.overlays.states));
    m.setLayoutProperty("states-fill", "visibility", vis(p.overlays.states));
  }), [p.overlays]);

  useEffect(() => whenReady((m) => {
    const india = p.scope === "india";
    m.setLayoutProperty("mask", "visibility", india ? "visible" : "none");
    if (india) m.fitBounds(INDIA_FIT, { padding: FIT_PAD, duration: 600 });
  }), [p.scope]);

  // refit India when the panel opens/closes so it always sits in the visible part of the map
  useEffect(() => whenReady((m) => {
    FIT_PAD = fitPad(p.panelOpen);
    if (p.scope === "india" && !p.state) m.fitBounds(INDIA_FIT, { padding: FIT_PAD, duration: 700, pitch: m.getPitch() });
  }), [p.panelOpen]);

  // selected state: highlight and fly to it; cleared → back to all of India
  const prevState = useRef<string | null>(null);
  useEffect(() => whenReady((m) => {
    if (prevState.current) m.setFeatureState({ source: "states", id: prevState.current }, { selected: false });
    prevState.current = p.state;
    if (!p.state) {
      if (p.scope === "india") m.fitBounds(INDIA_FIT, { padding: FIT_PAD, duration: 1200, pitch: m.getPitch() });
      return;
    }
    m.setFeatureState({ source: "states", id: p.state }, { selected: true });
    const b = stateBox.current[p.state];
    if (b) m.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: { ...FIT_PAD, top: 170 }, duration: 1400, essential: true, maxZoom: 9, pitch: m.getPitch() });
  }), [p.state]);

  // 3D: terrain + tilt + extruded buildings; 2D: flat and north-up
  useEffect(() => whenReady((m) => {
    if (p.threeD) {
      m.setTerrain({ source: "dem", exaggeration: 1.5 });
      if (!m.getLayer("hills")) m.addLayer({ id: "hills", type: "hillshade", source: "dem",
        paint: { "hillshade-shadow-color": "#000000", "hillshade-highlight-color": "#33405c", "hillshade-exaggeration": 0.45 } }, "mask");
      if (!m.getLayer("buildings-3d")) m.addLayer({ id: "buildings-3d", type: "fill-extrusion", source: "openmaptiles", "source-layer": "building",
        minzoom: 13, paint: { "fill-extrusion-color": "#1c2740", "fill-extrusion-opacity": 0.85,
          "fill-extrusion-height": ["coalesce", ["get", "render_height"], 8], "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0] } });
      (m as any).setSky?.({ "sky-color": "#05070d", "horizon-color": "#0b111f", "fog-color": "#05070d", "sky-horizon-blend": 0.6 });
      m.dragRotate.enable(); m.touchZoomRotate.enableRotation();
      m.easeTo({ pitch: 60, bearing: -12, duration: 1200 });
    } else {
      m.setTerrain(null);
      for (const id of ["hills", "buildings-3d"]) if (m.getLayer(id)) m.removeLayer(id);
      m.dragRotate.disable(); m.touchZoomRotate.disableRotation();
      m.easeTo({ pitch: 0, bearing: 0, duration: 900 });
    }
  }), [p.threeD]);

  useEffect(() => whenReady((m) => {
    const pts = p.history.filter((r) => r.lon !== null).map((r) => [r.lon, r.lat]);
    (m.getSource("history") as maplibregl.GeoJSONSource).setData({ type: "FeatureCollection",
      features: pts.length > 1 ? [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: pts as any } }] : [] });
  }), [p.history]);

  useEffect(() => whenReady((m) => {
    const r = p.selected && p.live[p.selected.feed]?.find((x) => x.id === p.selected!.id);
    (m.getSource("sel") as maplibregl.GeoJSONSource).setData({ type: "FeatureCollection",
      features: r && r.lon !== null ? [{ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [r.lon, r.lat!] } }] : [] });
  }), [p.selected, p.live]);

  useEffect(() => {
    if (p.flyTo && map.current) map.current.flyTo({ center: [p.flyTo.lon, p.flyTo.lat], zoom: p.flyTo.zoom ?? Math.max(map.current.getZoom(), 7), duration: 1100, essential: true });
  }, [p.flyTo]);

  return <div ref={el} className="map" />;
}
