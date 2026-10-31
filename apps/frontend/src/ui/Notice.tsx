// Purpose & acceptable-use notice: shown once on first visit, reopened from the logo.
import { ShieldAlert } from "lucide-react";

export function Notice({ close }: { close: () => void }) {
  return (
    <div className="backdrop" onMouseDown={close}>
      <div className="glass notice" role="dialog" aria-modal="true" aria-labelledby="notice-title" onMouseDown={(e) => e.stopPropagation()}>
        <div className="notice-head"><ShieldAlert size={18} color="var(--accent)" /><b id="notice-title">About OpenWatch India</b></div>
        <p>An independent, non-commercial project for <b>study, research and general public awareness</b>.</p>
        <ul>
          <li>Not affiliated with or built for any military, defence or government body. No military involvement.</li>
          <li>Shows only publicly available data (open APIs, public government pages, open datasets).</li>
          <li>Data may be delayed, incomplete or wrong. Not for navigation, emergency response, safety-of-life or
            any operational decisions; rely on the official source.</li>
          <li><b>Please don't use it for military, targeting, surveillance or unlawful purposes.</b></li>
          <li>India's boundary is shown as per the Survey of India.</li>
        </ul>
        <div className="notice-foot">
          <a href="https://github.com/d-rohan-web/openwatch/blob/main/NOTICE.md" target="_blank" rel="noreferrer">Full notice</a>
          <button className="btn primary" onClick={close} autoFocus>I understand</button>
        </div>
      </div>
    </div>
  );
}
