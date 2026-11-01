import type { FeedMeta, Health, Rec } from "./types";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

// Everything goes through the backend for frontend (apps/bff, /ui/*); the core API isn't reachable from the browser.
export type Config = { traffic_tiles: boolean; global: boolean; export: boolean };
/** The first frame in one request: config, feeds with health, and every feed's live records. */
export const getBootstrap = () => get<{ config: Config; feeds: FeedMeta[]; live: Record<string, Rec[]> }>("/ui/bootstrap");
export const getFeeds = () => get<{ feeds: FeedMeta[] }>("/ui/feeds").then((d) => d.feeds);
export const getHistory = (feed: string, id: string, hours = 6) =>
  get<{ records: Rec[] }>(`/ui/history/${encodeURIComponent(feed)}/${encodeURIComponent(id)}?hours=${hours}`)
    .then((d) => d.records);
export const getWindow = (feed: string, hours: number) =>
  get<{ records: Rec[] }>(`/ui/window/${encodeURIComponent(feed)}?hours=${hours}`).then((d) => d.records);
export const rawUrl = (feed: string, sha: string) => `/ui/raw/${encodeURIComponent(feed)}/${sha}`;

// One EventSource for the app; reconnects by itself (server sends retry: 3000). `records` is undefined when only a
// feed's health changed. A tab hidden for 2 min closes the stream (no bandwidth for nobody); when it's visible again
// the stream reopens and `resume` reloads the current state once.
const HIDDEN_CLOSE_MS = 2 * 60e3;
export function subscribe(on: (feed: string, records: Rec[] | undefined, health: Health | null) => void, resume: () => void) {
  let es: EventSource | null = null, timer = 0;
  const open = () => {
    es = new EventSource("/ui/stream");
    es.addEventListener("feed", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      on(d.feed, d.records, d.health);
    });
  };
  const visibility = () => {
    clearTimeout(timer);
    if (document.hidden) timer = window.setTimeout(() => { es?.close(); es = null; }, HIDDEN_CLOSE_MS);
    else if (!es) { open(); resume(); }
  };
  open();
  document.addEventListener("visibilitychange", visibility);
  return () => { clearTimeout(timer); es?.close(); document.removeEventListener("visibilitychange", visibility); };
}

export type ExportReq = {
  feeds: string[]; start: string; end: string; bbox: number[] | null;
  format: "geojson" | "csv" | "parquet"; include_unlocated: boolean; include_raw: boolean; time_field: "fetched" | "observed";
};
export async function runExport(q: ExportReq) {
  const r = await fetch("/ui/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(q) });
  if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `export: ${r.status}`);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await r.blob());
  a.download = (r.headers.get("content-disposition") ?? "").match(/filename="?([^";]+)"?/)?.[1] ?? "openwatch-export.zip";
  a.click();
  URL.revokeObjectURL(a.href);
}
