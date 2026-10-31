// Layer categories (the dock), their colours and the one-click views.
import { Activity, Building2, Plane, Satellite, Shield, Ship, TrendingUp, TriangleAlert, type LucideIcon } from "lucide-react";
import type { Section } from "./types";

export const CATS: { id: Section; label: string; icon: LucideIcon; color: string }[] = [
  { id: "air", label: "Air", icon: Plane, color: "#7fd3ff" },
  { id: "sea", label: "Sea", icon: Ship, color: "#2dd4bf" },
  { id: "space", label: "Space", icon: Satellite, color: "#b69cff" },
  { id: "defence", label: "Defence", icon: Shield, color: "#ff5c8a" },
  { id: "hazards", label: "Hazards", icon: TriangleAlert, color: "#ff8c1a" },
  { id: "infrastructure", label: "Infra", icon: Activity, color: "#4ade80" },
  { id: "economy", label: "Markets", icon: TrendingUp, color: "#fbbf24" },
  { id: "govt", label: "Govt", icon: Building2, color: "#cbd5e1" },
];
export const catOf = (s: Section) => CATS.find((c) => c.id === s)!;

// Views: a starting set of layers for a job. Ids that don't exist (feed not installed) are ignored.
export const VIEWS: { id: string; label: string; feeds: string[] }[] = [
  { id: "overview", label: "Overview (default)", feeds: ["aircraft", "opensky", "satellites", "sachet", "imd_warnings", "imd_nowcast", "imd_cyclone",
    "ncs_quakes", "cwc_rivers", "incois", "ioda", "launches", "markets_india", "fx_inr", "commodities_india", "volcanoes"] },
  { id: "all", label: "Everything", feeds: [] },
  { id: "defence", label: "Defence", feeds: ["aircraft", "opensky", "ais", "navarea8", "faa_notam", "restricted_areas", "defence_sites", "nuclear", "satellites", "launches"] },
  { id: "disaster", label: "Disaster", feeds: ["sachet", "imd_warnings", "imd_nowcast", "imd_cyclone", "ncs_quakes", "usgs_quakes", "incois", "cwc_rivers", "firms", "gsi_landslide", "ioda"] },
  { id: "aviation", label: "Aviation", feeds: ["aircraft", "opensky", "faa_notam", "restricted_areas", "airports", "airport_infra"] },
  { id: "maritime", label: "Maritime", feeds: ["ais", "navarea8", "incois", "imd_cyclone"] },
  { id: "space", label: "Space", feeds: ["satellites", "launches", "space_weather"] },
];

// India view: the map can't pan far from here, and records outside it are hidden.
export const INDIA_BOUNDS: [number, number, number, number] = [52, -8, 110, 42];
export const INDIA_FIT: [number, number, number, number] = [67.5, 6.2, 97.6, 37.2];
