// Records → GeoJSON for MapLibre. Pure, so it's tested in features.test.ts.
import { catOf } from "./sections";
import { SEVERITY_COLOR, SEVERITY_RANK, type Rec, type Section } from "./types";

const FEED_COLOR: Record<string, string> = { airports: "#64748b", restricted_areas: "#f472b6", aai_notam: "#facc15", faa_notam: "#facc15" };
const KIND_COLOR: Record<string, string> = {
  aircraft: "#eef2f7", military: "#ff5c8a", station: "#ffffff", indian: "#ff9933", navic: "#ff9933", fire: "#ff5a1f", firing: "#ff5c8a", defence: "#ff5c8a",
};
const MOVERS = new Set(["aircraft", "military", "ship"]); // drawn as icons rotated to their heading
export const MOVING_FEEDS = new Set(["aircraft", "opensky", "ais", "satellites"]);

// Map glyph per kind (falls back per feed); names are lucide icons rendered into the map's sprite (MapView).
const KIND_GLYPH: Record<string, string> = {
  earthquake: "activity", met: "cloud-lightning", nowcast: "cloud-rain", warning: "cloud-lightning", weather: "thermometer",
  ocean_alert: "waves", tsunami: "waves", river_level: "droplets", fire: "flame", volcano: "mountain",
  large_airport: "plane-landing", medium_airport: "plane-landing",  // small strips and heliports stay plain dots (hundreds)
  seaplane_base: "anchor", notam: "file-warning", navwarn: "anchor", firing: "crosshair",
  indian: "satellite", navic: "satellite", station: "satellite", military: "satellite", satellite: "satellite", launch: "rocket",
  airbase: "plane", naval_base: "anchor", military_base: "shield", academy: "graduation-cap", cantonment: "castle", crossing: "door-open",
  power_plant: "radiation", reactor: "radiation", research: "atom", mine: "pickaxe", fuel_cycle: "factory", other_nuclear: "radiation",
  outage: "wifi-off", press: "newspaper", defence: "newspaper", cyber: "shield-alert",
};
const FEED_GLYPH: Record<string, string> = {
  sachet: "siren", imd_warnings: "cloud-lightning", imd_nowcast: "cloud-rain", imd_cyclone: "tornado", incois: "waves",
  cwc_rivers: "droplets", ioda: "wifi-off", gdelt: "newspaper", cpcb_aqi: "wind", airport_infra: "radio-tower",
  launches: "rocket", nuclear: "radiation", defence_sites: "shield", border_posts: "door-open", city_weather: "thermometer",
  volcanoes: "mountain", road_incidents: "construction",
};
export const GLYPHS = [...new Set([...Object.values(KIND_GLYPH), ...Object.values(FEED_GLYPH), "plane-landing", "anchor", "activity"])];
// The icon a group (cluster) of a feed's points shows
export const FEED_ICON: Record<string, string> = { ...FEED_GLYPH, airports: "plane-landing", navarea8: "anchor", ncs_quakes: "activity",
  usgs_quakes: "activity", firms: "flame" };
export const glyphOf = (r: Rec) => KIND_GLYPH[r.kind] ?? FEED_GLYPH[r.feed] ?? "";
const MAX_GLIDE_S = 180;
const MINOR_KINDS = new Set(["small_airport", "heliport", "seaplane_base", "closed", "balloonport"]); // never extrapolate further than this past the last report
type Ring = [number, number][];
export type Area = Ring[][];  // MultiPolygon coordinates

export const feedColor = (feed: string, section?: Section) => FEED_COLOR[feed] ?? (section ? catOf(section).color : "#94a3b8");

export function color(r: Rec, section?: Section) {
  return (r.severity && r.severity !== "info" ? SEVERITY_COLOR[r.severity] : null) ?? KIND_COLOR[r.kind] ?? feedColor(r.feed, section);
}

export function heading(r: Rec): number | null {
  const a = r.attrs;
  const h = a.track ?? a.true_heading ?? a.heading ?? a.cog;
  return typeof h === "number" && h >= 0 && h < 360 ? h : null;
}

function inRing(x: number, y: number, ring: Ring) {  // ray casting
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
/** Dead reckoning: where a moving thing is now, from its last report, speed and heading (great-circle-free:
 *  fine for the minute or two between reports). Ground traffic and stale reports don't move. */
export function project(r: Rec, now: number): [number, number] | null {
  if (r.lon === null || r.lat === null) return null;
  if (r.feed === "satellites") return alongTrack(r, now) ?? [r.lon, r.lat];
  const kt = r.attrs.gs_kt ?? r.attrs.sog, h = heading(r);
  if (!r.observed_at || r.attrs.on_ground || typeof kt !== "number" || kt < 30 && r.kind !== "ship" || h === null) return [r.lon, r.lat];
  const dt = Math.min(Math.max((now - Date.parse(r.observed_at)) / 1000, 0), MAX_GLIDE_S);
  const m = kt * 0.514444 * dt, rad = (h * Math.PI) / 180;
  return [r.lon + (m * Math.sin(rad)) / (111320 * Math.cos((r.lat * Math.PI) / 180)), r.lat + (m * Math.cos(rad)) / 110540];
}

// satellites.py samples ground tracks from observed_at every attrs.track_step_s (2 min LEO, 20 min IGSO)
export const trackStep = (r: Rec) => Number(r.attrs.track_step_s) || 120;

/** A satellite's position now, interpolated along its predicted ground track (null without one). */
export function alongTrack(r: Rec, now: number): [number, number] | null {
  const c = r.geometry?.type === "LineString" ? (r.geometry.coordinates as [number, number][]) : null;
  if (!c || c.length < 2 || !r.observed_at) return null;
  const f = Math.min(Math.max((now - Date.parse(r.observed_at)) / 1000 / trackStep(r), 0), c.length - 1.001);
  const i = Math.floor(f), t = f - i;
  return [c[i][0] + (c[i + 1][0] - c[i][0]) * t, c[i][1] + (c[i + 1][1] - c[i][1]) * t];
}

export type Pass = { orbit: string; over: boolean; inMin: number | null; outMin: number | null };
/** When a satellite is over an area, from its ground track: over now (and leaves in), or arrives in N minutes. */
export function passOver(r: Rec, area: Area | null, now: number): Pass | null {
  if (r.feed !== "satellites" || !area) return null;
  const orbit = String(r.attrs.orbit ?? "");
  const pos = alongTrack(r, now) ?? (r.lon !== null ? [r.lon, r.lat!] as [number, number] : null);
  if (!pos) return null;
  // geosynchronous over the Indian Ocean longitudes is always in view of India, wherever its sub-point is
  const geoSync = orbit === "GEO" || orbit === "IGSO";
  const lon = ((pos[0] + 540) % 360) - 180;
  if (geoSync) return { orbit, over: lon > 30 && lon < 140, inMin: null, outMin: null };
  const over = inArea(lon, pos[1], area);
  const c = r.geometry?.type === "LineString" ? (r.geometry.coordinates as [number, number][]) : [];
  const elapsed = r.observed_at ? (now - Date.parse(r.observed_at)) / 1000 : 0;
  let inMin: number | null = null, outMin: number | null = null;
  c.forEach(([x, y], k) => {
    const t = (k * trackStep(r) - elapsed) / 60;
    if (t <= 0) return;
    const inside = inArea(((x + 540) % 360) - 180, y, area);
    if (over && !inside && outMin === null) outMin = Math.round(t);
    if (!over && inside && inMin === null) inMin = Math.round(t);
  });
  return { orbit, over, inMin, outMin };
}

export const inArea = (lon: number, lat: number, area: Area) =>
  area.some(([outer, ...holes]) => inRing(lon, lat, outer) && !holes.some((h) => inRing(lon, lat, h)));
/** Records with no position always pass (press releases, space weather): they aren't somewhere else. */
/** Satellites are never cut by the India view: Indian ones matter wherever they are (NavIC sits over the ocean).
 *  Flights show over the whole region: Arabian Sea, Bay of Bengal and Indian Ocean (REGION_BBOX in packages/common/geo.py). */
const REGION_BBOX = [40, -15, 105, 42];
const FLIGHT_FEEDS = new Set(["aircraft", "opensky"]);
export const inScope = (r: Rec, area: Area | null) => !area || r.lon === null || r.feed === "satellites" || inArea(r.lon, r.lat!, area) ||
  FLIGHT_FEEDS.has(r.feed) && r.lon >= REGION_BBOX[0] && r.lat! >= REGION_BBOX[1] && r.lon <= REGION_BBOX[2] && r.lat! <= REGION_BBOX[3];

// Tracks (satellite ground tracks, forecast paths of moving things) only for the selected record: all at once is clutter.
const TRACK_ONLY_SELECTED = new Set(["satellites"]);

/** A quake from the last 30 minutes: drawn with ripples. */
export const freshQuake = (r: Rec, now = Date.now()) =>
  r.kind === "earthquake" && !!r.observed_at && now - Date.parse(r.observed_at) < 30 * 60e3;

/** Map relevance: old small quakes are history, not situation (they stay in the archive and the alert list rules). */
export function onMap(r: Rec, now = Date.now()) {
  if (r.kind !== "earthquake") return true;
  const mag = Number(r.attrs.mag ?? r.attrs.magnitude ?? 0);
  return mag >= 3.5 || (!!r.observed_at && now - Date.parse(r.observed_at) < 864e5);
}

export function toFeatures(records: Rec[], section?: Section, area: Area | null = null, now?: number, selectedId?: string, allTracks = false) {
  const features: any[] = [];
  for (const r of records) {
    if (!inScope(r, area) || !onMap(r, now)) continue;
    const h = heading(r);
    const icon = MOVERS.has(r.kind) && h !== null ? (r.kind === "ship" ? "openwatch-ship" : "openwatch-plane") : "";
    const props = { id: r.id, feed: r.feed, kind: r.kind, color: color(r, section), title: r.title, rot: h ?? 0,
      arrow: !!icon, icon, glyph: icon ? "" : glyphOf(r), alert: r.severity === "warning" || r.severity === "critical",
      sev: r.severity ? SEVERITY_RANK[r.severity] : 0, minor: MINOR_KINDS.has(r.kind), past: !!r.attrs._past, fresh: freshQuake(r), mag: Number(r.attrs.mag ?? r.attrs.magnitude ?? 0) };
    const g = r.geometry;
    // ground tracks / forecast tracks are drawn as lines *and* the thing itself as a point
    const hideTrack = TRACK_ONLY_SELECTED.has(r.feed) && !allTracks && r.id !== selectedId && g?.type.endsWith("LineString");
    if (g && g.type !== "Point" && !hideTrack) features.push({ type: "Feature", geometry: g, properties: props });
    if (r.lon !== null && r.lat !== null && (!g || g.type === "LineString" || g.type === "MultiLineString" || g.type === "Point"))
      features.push({ type: "Feature", geometry: { type: "Point", coordinates: now && icon ? project(r, now) : [r.lon, r.lat] }, properties: props });
  }
  return { type: "FeatureCollection" as const, features };
}
