// Mirrors packages/contracts/record.py and apps/api/main.py.
export type Severity = "info" | "advisory" | "warning" | "critical";
export type Rec = {
  feed: string; id: string; title: string; kind: string; severity: Severity | null;
  lon: number | null; lat: number | null; geometry: { type: string; coordinates: any } | null;
  observed_at: string | null; fetched_at: string; raw_sha256: string | null; attrs: Record<string, any>;
};
export type Health = {
  state: "STARTING" | "OK" | "DEGRADED" | "DOWN" | "NEEDS_KEY"; last_ok_at: string | null; last_error: string | null;
  last_error_at: string | null; last_count: number; stored_total: number; live_count?: number;
};
export type FeedMeta = {
  id: string; label: string; section: Section; homepage: string; terms: string; every: number;
  key: string | null; streaming: boolean; health: Health | null;
};
export type Section = "air" | "sea" | "space" | "defence" | "hazards" | "infrastructure" | "economy" | "govt";

export const SECTIONS: { id: Section; label: string }[] = [
  { id: "air", label: "Air" }, { id: "sea", label: "Sea" }, { id: "space", label: "Space" },
  { id: "hazards", label: "Hazards" }, { id: "infrastructure", label: "Infrastructure" }, { id: "govt", label: "Govt & news" },
];
export const SEVERITY_COLOR: Record<Severity, string> = {
  info: "#5b9cff", advisory: "#ffd23f", warning: "#ff8c1a", critical: "#ff3b3b",
};
export const SEVERITY_RANK: Record<Severity, number> = { info: 0, advisory: 1, warning: 2, critical: 3 };
