import type { FeedMeta, Health, Rec } from "./types";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export const getFeeds = () => get<{ feeds: FeedMeta[] }>("/api/feeds").then((d) => d.feeds);
export const getLive = () => get<Record<string, Rec[]>>("/api/live");
export const getConfig = () => get<{ traffic_tiles: boolean; global: boolean; export: boolean }>("/api/config");
export const getHistory = (feed: string, id: string, hours = 6) =>
  get<{ records: Rec[] }>(`/api/history/${encodeURIComponent(feed)}/${encodeURIComponent(id)}?hours=${hours}`)
    .then((d) => d.records);
export const rawUrl = (feed: string, sha: string) => `/api/raw/${encodeURIComponent(feed)}/${sha}`;

// One EventSource for the app; reconnects by itself (server sends retry: 3000).
export function subscribe(on: (feed: string, records: Rec[], health: Health | null) => void) {
  const es = new EventSource("/api/stream");
  es.addEventListener("feed", (e) => {
    const d = JSON.parse((e as MessageEvent).data);
    on(d.feed, d.records, d.health);
  });
  return () => es.close();
}

export type ExportReq = {
  feeds: string[]; start: string; end: string; bbox: number[] | null;
  format: "geojson" | "csv" | "parquet"; include_unlocated: boolean; include_raw: boolean; time_field: "fetched" | "observed";
};
export async function runExport(q: ExportReq) {
  const r = await fetch("/api/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(q) });
  if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `export: ${r.status}`);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await r.blob());
  a.download = (r.headers.get("content-disposition") ?? "").match(/filename="?([^";]+)"?/)?.[1] ?? "openwatch-export.zip";
  a.click();
  URL.revokeObjectURL(a.href);
}
