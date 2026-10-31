"""Generate the Grafana dashboards (JSON) in ./dashboards. Re-run after editing: python build_dashboards.py

Data sources are dashboard variables (`prom`, `loki`), so the same files work with the local stack and in
Grafana Cloud (Dashboards → New → Import → upload the JSON). `instance` picks the deployment (site name or local).
"""
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboards")
P = {"type": "prometheus", "uid": "${prom}"}
L = {"type": "loki", "uid": "${loki}"}
SEL = 'instance=~"$instance"'           # metric selector
A = '{job="access", instance=~"$instance"}'  # access-log stream
SEV = {"advisory": "#ffd23f", "warning": "#ff8c1a", "critical": "#ff4d4f", "info": "#5b9cff"}
PAGES = r'uri !~ "^/(api|assets|geo)/.*"'


def grid():
    pos = {"x": 0, "y": 0, "h": 0}

    def at(w, h):
        if pos["x"] + w > 24:
            pos.update(x=0, y=pos["y"] + pos["h"], h=0)
        g = {"x": pos["x"], "y": pos["y"], "w": w, "h": h}
        pos["x"] += w
        pos["h"] = max(pos["h"], h)
        return g
    return at


def target(ds, expr, legend="", instant=False, fmt=None):
    t = {"datasource": ds, "expr": expr, "legendFormat": legend, "refId": "A"}
    if instant:
        t.update(instant=True, range=False) if ds is P else t.update(queryType="instant")
    if fmt:
        t["format"] = fmt
    return t


def stat(title, ds, expr, unit="short", color="#7fd3ff", thresholds=None, desc=""):
    return {"type": "stat", "title": title, "description": desc, "datasource": ds,
            "targets": [target(ds, expr, instant=True)],
            "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "value", "graphMode": "none",
                        "textMode": "value"},
            "fieldConfig": {"defaults": {"unit": unit, "decimals": 0 if unit == "short" else None,
                                         "color": {"mode": "thresholds"},
                                         "thresholds": thresholds or {"mode": "absolute", "steps": [{"color": color, "value": None}]}},
                            "overrides": []}}


def series(title, ds, exprs, unit="short", stack=False, desc="", overrides=None, bars=False):
    return {"type": "timeseries", "title": title, "description": desc, "datasource": ds,
            "targets": [dict(target(ds, e, lg), refId=chr(65 + i)) for i, (e, lg) in enumerate(exprs)],
            "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi", "sort": "desc"}},
            "fieldConfig": {"defaults": {"unit": unit, "custom": {
                "drawStyle": "bars" if bars else "line", "lineWidth": 2, "fillOpacity": 18 if stack else 8,
                "gradientMode": "opacity", "showPoints": "never", "stacking": {"mode": "normal" if stack else "none"}}},
                "overrides": overrides or []}}


def top(title, ds, expr, label, unit="short"):
    return {"type": "bargauge", "title": title, "datasource": ds,
            "targets": [target(ds, expr, "{{" + label + "}}", instant=True)],
            "options": {"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True,
                        "reduceOptions": {"calcs": ["lastNotNull"], "values": False}, "valueMode": "text"},
            "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "continuous-BlYlRd"}}, "overrides": []}}


def logs(title, expr):
    return {"type": "logs", "title": title, "datasource": L, "targets": [target(L, expr)],
            "options": {"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending", "enableLogDetails": True}}


def sev_overrides():
    return [{"matcher": {"id": "byName", "options": s}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]}
            for s, c in SEV.items()]


def dashboard(uid, title, desc, panels_with_size, refresh="1m", time_from="now-24h"):
    at = grid()
    panels = []
    for i, (w, h, p) in enumerate(panels_with_size):
        p.update(id=i + 1, gridPos=at(w, h))
        panels.append(p)
    variables = [
        {"name": "prom", "label": "Metrics", "type": "datasource", "query": "prometheus", "hide": 0},
        {"name": "loki", "label": "Logs", "type": "datasource", "query": "loki", "hide": 0},
        {"name": "instance", "label": "Site", "type": "query", "datasource": P, "refresh": 2, "includeAll": True,
         "allValue": ".*", "current": {"text": "All", "value": "$__all"},
         "query": {"query": "label_values(openwatch_live_records, instance)", "refId": "v"}, "definition": "label_values(openwatch_live_records, instance)"},
    ]
    return {"uid": uid, "title": title, "description": desc, "tags": ["openwatch"], "schemaVersion": 39,
            "time": {"from": time_from, "to": "now"}, "refresh": refresh, "timezone": "browser",
            "templating": {"list": variables}, "panels": panels, "editable": True,
            "links": [{"title": "OpenWatch dashboards", "type": "dashboards", "tags": ["openwatch"], "asDropdown": True}]}


uv = f'count(sum by (ip) (count_over_time({A} | json ip="request.remote_ip" [24h])))'
served = f'sum(sum_over_time({A} | json size="size" | unwrap size [24h]))'

overview = dashboard("openwatch-overview", "OpenWatch · Overview", "Feeds, archive and visitors at a glance", [
    (4, 4, stat("Feeds healthy", P, f"count(openwatch_feed_failing{{{SEL}}} == 0)", color="#22d3a6")),
    (4, 4, stat("Feeds failing", P, f"sum(openwatch_feed_failing{{{SEL}}})",
                thresholds={"mode": "absolute", "steps": [{"color": "#22d3a6", "value": None}, {"color": "#ffd23f", "value": 1}, {"color": "#ff4d4f", "value": 5}]})),
    (4, 4, stat("Live records", P, f"sum(openwatch_live_records{{{SEL}}})")),
    (4, 4, stat("Archived · 24 h", P, f"sum(increase(openwatch_records_stored_total{{{SEL}}}[24h]))", color="#b69cff")),
    (4, 4, stat("Visitors · 24 h", L, uv, color="#ff9933")),
    (4, 4, stat("Data served · 24 h", L, served, unit="decbytes", color="#38bdf8")),
    (24, 10, {"type": "table", "title": "Feed health", "datasource": P,
              "targets": [dict(target(P, f"max by (feed) (openwatch_feed_failing{{{SEL}}})", instant=True, fmt="table"), refId="A"),
                          dict(target(P, f"max by (feed) (openwatch_live_records{{{SEL}}})", instant=True, fmt="table"), refId="B"),
                          dict(target(P, f"time() - max by (feed) (openwatch_last_ok_timestamp{{{SEL}}})", instant=True, fmt="table"), refId="C"),
                          dict(target(P, f"sum by (feed) (increase(openwatch_fetch_total{{result=\"error\", {SEL}}}[1h]))", instant=True, fmt="table"), refId="D")],
              "transformations": [{"id": "merge"}, {"id": "organize", "options": {"excludeByName": {"Time": True},
                  "renameByName": {"Value #A": "Failing", "Value #B": "Live records", "Value #C": "Since last OK", "Value #D": "Errors · 1 h"}}},
                  {"id": "sortBy", "options": {"sort": [{"field": "Failing", "desc": True}]}}],
              "fieldConfig": {"defaults": {}, "overrides": [
                  {"matcher": {"id": "byName", "options": "Since last OK"}, "properties": [{"id": "unit", "value": "s"}]},
                  {"matcher": {"id": "byName", "options": "Failing"}, "properties": [
                      {"id": "mappings", "value": [{"type": "value", "options": {"0": {"text": "OK", "color": "#22d3a6"}, "1": {"text": "FAILING", "color": "#ff4d4f"}}}]},
                      {"id": "custom.cellOptions", "value": {"type": "color-background"}}]}]}}),
    (12, 8, series("Records received / min", P, [(f"sum by (feed) (rate(openwatch_records_total{{{SEL}}}[5m])) * 60", "{{feed}}")], stack=True)),
    (12, 8, series("Fetch errors / 15 min", P, [(f"sum by (feed) (increase(openwatch_fetch_total{{result=\"error\", {SEL}}}[15m])) > 0", "{{feed}}")], bars=True)),
    (24, 9, logs("Warnings & errors", '{level=~"WARNING|ERROR", instance=~"$instance"}')),
])

situation = dashboard("openwatch-situation", "OpenWatch · Situation", "How the situation in India changes over time", [
    (4, 4, stat("Critical now", P, f'sum(openwatch_live_severity{{severity="critical", {SEL}}})', thresholds={"mode": "absolute", "steps": [{"color": "#22d3a6", "value": None}, {"color": "#ff4d4f", "value": 1}]})),
    (4, 4, stat("Warnings now", P, f'sum(openwatch_live_severity{{severity="warning", {SEL}}})', color="#ff8c1a")),
    (4, 4, stat("Advisories now", P, f'sum(openwatch_live_severity{{severity="advisory", {SEL}}})', color="#ffd23f")),
    (4, 4, stat("Aircraft tracked", P, f'sum(openwatch_live_records{{feed=~"aircraft|opensky", {SEL}}})', desc="adsb.fi + OpenSky; the two can overlap")),
    (4, 4, stat("Satellites tracked", P, f'sum(openwatch_live_records{{feed="satellites", {SEL}}})', color="#b69cff")),
    (4, 4, stat("Quakes (NCS, 10 days)", P, f'sum(openwatch_live_records{{feed="ncs_quakes", {SEL}}})', color="#ff8c1a")),
    (24, 9, series("Active alerts by severity", P, [(f'sum by (severity) (openwatch_live_severity{{severity=~"advisory|warning|critical", {SEL}}})', "{{severity}}")],
                   stack=True, overrides=sev_overrides(), desc="All sources: IMD, SACHET, INCOIS, CWC, NCS, NAVAREA, CERT-In …")),
    (12, 8, series("Warnings & critical by source", P, [(f'sum by (feed) (openwatch_live_severity{{severity=~"warning|critical", {SEL}}}) > 0', "{{feed}}")], stack=True)),
    (12, 8, series("Weather & disaster alerts", P, [(f'sum by (feed) (openwatch_live_records{{feed=~"sachet|imd_warnings|imd_nowcast|incois|imd_cyclone", {SEL}}})', "{{feed}}")])),
    (12, 8, series("Aircraft tracked over India", P, [(f'sum by (feed) (openwatch_live_records{{feed=~"aircraft|opensky", {SEL}}})', "{{feed}}")])),
    (12, 8, series("Maritime & airspace", P, [(f'sum by (feed) (openwatch_live_records{{feed=~"navarea8|ais|restricted_areas|faa_notam", {SEL}}})', "{{feed}}")])),
    (12, 8, series("Internet outages (IODA)", P, [(f'sum(openwatch_live_records{{feed="ioda", {SEL}}})', "outage events")], bars=True)),
    (12, 8, series("Quakes in the live window", P, [(f'sum by (feed) (openwatch_live_records{{feed=~"ncs_quakes|usgs_quakes", {SEL}}})', "{{feed}}")])),
], time_from="now-7d")

visitors = dashboard("openwatch-visitors", "OpenWatch · Visitors & traffic", "Who visits, from where, and what it costs in bandwidth", [
    (6, 4, stat("Unique visitors · 24 h", L, uv, color="#ff9933")),
    (6, 4, stat("Page views · 24 h", L, f'sum(count_over_time({A} | json uri="request.uri" | {PAGES} [24h]))')),
    (6, 4, stat("Data served · 24 h", L, served, unit="decbytes", color="#38bdf8")),
    (6, 4, stat("Projected egress / month", L, served.replace("[24h]))", "[24h])) * 30"), unit="decbytes",
                thresholds={"mode": "absolute", "steps": [{"color": "#22d3a6", "value": None}, {"color": "#ffd23f", "value": 8e8}, {"color": "#ff4d4f", "value": 1e9}]},
                desc="Last 24 h × 30. Google Cloud's free egress is 1 GB/month; above that ≈ $0.12/GB")),
    (16, 8, series("Unique visitors / hour", L, [(f'count(sum by (ip) (count_over_time({A} | json ip="request.remote_ip" [1h])))', "visitors")], bars=True)),
    (8, 8, top("Top referrers", L, f'topk(10, sum by (referer) (count_over_time({A} | json referer="request.headers.Referer[0]" | referer != "" [$__range])))', "referer")),
    (8, 9, top("Top pages", L, f'topk(10, sum by (uri) (count_over_time({A} | json uri="request.uri" | {PAGES} [$__range])))', "uri")),
    (8, 9, top("Browsers", L, f'sum by (browser) (count_over_time({A} | json ua="request.headers[\\"User-Agent\\"][0]" | regexp "(?P<browser>Edg|Firefox|OPR|Chrome|Safari|curl|bot|Bot)" [$__range]))', "browser")),
    (8, 9, series("Responses by status", L, [(f'sum by (status) (count_over_time({A} | json status="status" [5m]))', "{{status}}")], stack=True)),
    (12, 8, series("Bandwidth served / hour", L, [(f'sum(sum_over_time({A} | json size="size" | unwrap size [1h]))', "bytes")], unit="decbytes", bars=True)),
    (12, 8, series("Response time p95 (excl. live stream)", L, [(f'quantile_over_time(0.95, {A} | json uri="request.uri", duration="duration" | uri !~ "/api/stream.*" | unwrap duration [5m]) by (instance)', "p95")], unit="s")),
    (24, 9, logs("Recent requests", f'{A} | json uri="request.uri", status="status", ref="request.headers.Referer[0]" | line_format "{{{{.status}}}} {{{{.uri}}}}  ← {{{{.ref}}}}"')),
])

health = dashboard("openwatch-server", "OpenWatch · Server health", "The VM: CPU, memory, swap, disk and network", [
    (6, 4, stat("CPU", P, f'1 - avg(rate(node_cpu_seconds_total{{mode="idle", {SEL}}}[5m]))', unit="percentunit",
                thresholds={"mode": "absolute", "steps": [{"color": "#22d3a6", "value": None}, {"color": "#ffd23f", "value": 0.7}, {"color": "#ff4d4f", "value": 0.9}]})),
    (6, 4, stat("Memory used", P, f'1 - avg(node_memory_MemAvailable_bytes{{{SEL}}}) / avg(node_memory_MemTotal_bytes{{{SEL}}})', unit="percentunit",
                thresholds={"mode": "absolute", "steps": [{"color": "#22d3a6", "value": None}, {"color": "#ffd23f", "value": 0.8}, {"color": "#ff4d4f", "value": 0.92}]})),
    (6, 4, stat("Swap used", P, f'avg(node_memory_SwapTotal_bytes{{{SEL}}} - node_memory_SwapFree_bytes{{{SEL}}})', unit="bytes", color="#b69cff")),
    (6, 4, stat("Disk used", P, f'1 - min(node_filesystem_avail_bytes{{fstype!~"tmpfs|overlay|squashfs", {SEL}}} / node_filesystem_size_bytes{{fstype!~"tmpfs|overlay|squashfs", {SEL}}})', unit="percentunit",
                thresholds={"mode": "absolute", "steps": [{"color": "#22d3a6", "value": None}, {"color": "#ffd23f", "value": 0.75}, {"color": "#ff4d4f", "value": 0.9}]})),
    (12, 8, series("CPU", P, [(f'1 - avg(rate(node_cpu_seconds_total{{mode="idle", {SEL}}}[5m]))', "busy")], unit="percentunit")),
    (12, 8, series("Memory", P, [(f'avg(node_memory_MemTotal_bytes{{{SEL}}} - node_memory_MemAvailable_bytes{{{SEL}}})', "used"),
                                 (f'avg(node_memory_SwapTotal_bytes{{{SEL}}} - node_memory_SwapFree_bytes{{{SEL}}})', "swap used")], unit="bytes")),
    (12, 8, series("Network", P, [(f'sum(rate(node_network_transmit_bytes_total{{device!~"lo|veth.*|docker.*|br-.*", {SEL}}}[5m]))', "out"),
                                  (f'sum(rate(node_network_receive_bytes_total{{device!~"lo|veth.*|docker.*|br-.*", {SEL}}}[5m]))', "in")], unit="Bps")),
    (12, 8, series("Load average", P, [(f"avg(node_load1{{{SEL}}})", "1 min"), (f"avg(node_load5{{{SEL}}})", "5 min")])),
], refresh="1m", time_from="now-24h")

os.makedirs(OUT, exist_ok=True)
for name, d in (("overview", overview), ("situation", situation), ("visitors", visitors), ("server", health)):
    with open(os.path.join(OUT, f"{name}.json"), "w") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    print("wrote", f"dashboards/{name}.json", f"({len(d['panels'])} panels)")
