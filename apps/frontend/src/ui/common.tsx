import { SEVERITY_COLOR, type Health, type Severity } from "../types";

export const ago = (t: string | null | undefined, now = Date.now()) => {
  if (!t) return "—";
  const s = Math.max(0, (now - Date.parse(t)) / 1000);
  return s < 60 ? `${Math.round(s)}s` : s < 3600 ? `${Math.round(s / 60)}m` : s < 172800 ? `${Math.round(s / 3600)}h` : `${Math.round(s / 86400)}d`;
};

export const STATE: Record<Health["state"], { color: string; label: string }> = {
  OK: { color: "#22d3a6", label: "Live" }, DEGRADED: { color: "#ffd23f", label: "Degraded" }, DOWN: { color: "#ff4d4f", label: "Down" },
  STARTING: { color: "#74819a", label: "Starting" }, NEEDS_KEY: { color: "#4b5568", label: "Needs key" },
};

export const SevTag = ({ s }: { s: Severity }) => <span className="tag" style={{ color: SEVERITY_COLOR[s] }}>{s}</span>;

/** Logo: an eye whose iris is a radar sweep. */
export const Mark = () => (
  <svg className="brand-mark" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
    <path d="M2 16c3.5-6 8.2-9 14-9s10.5 3 14 9c-3.5 6-8.2 9-14 9S5.5 22 2 16Z" />
    <circle cx="16" cy="16" r="5" />
    <path d="M16 16 19.5 12.5" strokeLinecap="round" />
    <circle cx="16" cy="16" r="1.2" fill="currentColor" stroke="none" />
  </svg>
);
