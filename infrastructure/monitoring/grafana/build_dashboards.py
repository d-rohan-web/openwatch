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
    if instant and ds is L and legend:  # Loki instant results lose their labels in Grafana: query a range, take the last value
        instant = False
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
            "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "continuous-BlYlRd"},
                                         "displayName": "${__field.labels." + label + "}"}, "overrides": []}}


def geomap(title, expr):
    """World map of visitors: Loki structured metadata lat/lon (DB-IP Lite) as markers sized by requests."""
    return {"type": "geomap", "title": title, "datasource": L,
            "targets": [dict(target(L, expr, instant=True), legendFormat="")],
            "transformations": [{"id": "labelsToFields", "options": {"mode": "columns"}},
                                {"id": "convertFieldType", "options": {"conversions": [
                                    {"targetField": "lat", "destinationType": "number"},
                                    {"targetField": "lon", "destinationType": "number"}]}}],
            "options": {"view": {"id": "coords", "lat": 22, "lon": 79, "zoom": 2},
                        "basemap": {"type": "osm-standard", "name": "OpenStreetMap"},  # no API key needed
                        "controls": {"showZoom": True, "mouseWheelZoom": True},
                        "layers": [{"type": "markers", "name": "visitors",
                                    "location": {"mode": "coords", "latitude": "lat", "longitude": "lon"},
                                    "config": {"size": {"field": "Value", "min": 4, "max": 22, "fixed": 6},
                                               "color": {"fixed": "#ff9933"}, "fillOpacity": 0.55,
                                               "style": {"symbol": {"fixed": "img/icons/marker/circle.svg"}}},
                                    "tooltip": True}]},
            "fieldConfig": {"defaults": {}, "overrides": []}}


def pie(title, ds, expr, label):
    return {"type": "piechart", "title": title, "datasource": ds,
            "targets": [target(ds, expr, "{{" + label + "}}", instant=True)],
            "options": {"pieType": "donut", "legend": {"displayMode": "table", "placement": "right", "values": ["percent"]},
                        "reduceOptions": {"calcs": ["lastNotNull"]}},
            "fieldConfig": {"defaults": {"displayName": "${__field.labels." + label + "}"}, "overrides": []}}


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
        # skip Grafana Cloud's internal sources (alert-state history, usage insights, ...) that share these types
        {"name": "prom", "label": "Metrics", "type": "datasource", "query": "prometheus", "hide": 0,
         "regex": "/^(?!.*(usage|alert-state|ml-metrics|insights)).*$/"},
        {"name": "loki", "label": "Logs", "type": "datasource", "query": "loki", "hide": 0,
         "regex": "/^(?!.*(alert-state|usage|insights)).*$/"},
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

visitors = dashboard("openwatch-visitors", "OpenWatch · Visitors & traffic", "Who visits, from where (DB-IP Lite, CC BY 4.0), with what, and what it costs in bandwidth. IPv4 addresses are truncated to /24 before leaving the server, so 'unique visitors' is approximate.", [
    (6, 4, stat("Unique visitors · 24 h", L, uv, color="#ff9933")),
    (6, 4, stat("Page views · 24 h", L, f'sum(count_over_time({A} | json uri="request.uri" | {PAGES} [24h]))')),
    (6, 4, stat("Data served · 24 h", L, served, unit="decbytes", color="#38bdf8")),
    (6, 4, stat("Projected egress / month", L, served.replace("[24h]))", "[24h])) * 30"), unit="decbytes",
                thresholds={"mode": "absolute", "steps": [{"color": "#22d3a6", "value": None}, {"color": "#ffd23f", "value": 8e8}, {"color": "#ff4d4f", "value": 1e9}]},
                desc="Last 24 h × 30. Google Cloud's free egress is 1 GB/month; above that ≈ $0.12/GB")),
    (16, 8, series("Unique visitors / hour", L, [(f'count(sum by (ip) (count_over_time({A} | json ip="request.remote_ip" [1h])))', "visitors")], bars=True)),
    (8, 8, top("Top referrers", L, f'topk(10, sum by (referer) (count_over_time({A} | json referer="request.headers.Referer[0]" | referer != "" [$__range])))', "referer")),
    (8, 9, top("Top pages", L, f'topk(10, sum by (uri) (count_over_time({A} | json uri="request.uri" | {PAGES} [$__range])))', "uri")),
    (16, 12, geomap("Where visitors come from", f'sum by (lat, lon, city, country) (count_over_time({A} | lat != "" | json uri="request.uri" | {PAGES} [$__range]))')),
    (8, 12, top("Top countries", L, f'topk(12, sum by (country) (count_over_time({A} | country != "" | json uri="request.uri" | {PAGES} [$__range])))', "country")),
    (8, 9, top("Top cities", L, f'topk(10, sum by (city) (count_over_time({A} | city != "" | json uri="request.uri" | {PAGES} [$__range])))', "city")),
    (8, 9, pie("Browsers", L, f'sum by (browser) (count_over_time({A} | browser != "" | json uri="request.uri" | {PAGES} [$__range]))', "browser")),
    (8, 9, pie("Operating systems", L, f'sum by (os) (count_over_time({A} | os != "" | json uri="request.uri" | {PAGES} [$__range]))', "os")),
    (8, 9, pie("Devices", L, f'sum by (device) (count_over_time({A} | json uri="request.uri" | {PAGES} [$__range]))', "device")),
    (8, 9, series("Responses by status", L, [(f'sum by (status) (count_over_time({A} | json status="status" [5m]))', "{{status}}")], stack=True)),
    (12, 8, series("Bandwidth served / hour", L, [(f'sum(sum_over_time({A} | json size="size" | unwrap size [1h]))', "bytes")], unit="decbytes", bars=True)),
    (12, 8, series("Response time p95 (excl. live stream)", L, [(f'quantile_over_time(0.95, {A} | json uri="request.uri", duration="duration" | uri !~ "/api/stream.*" | unwrap duration [5m]) by (instance)', "p95")], unit="s")),
    (24, 10, logs("Recent visitors", f'{A} | json uri="request.uri", status="status", ref="request.headers.Referer[0]" | {PAGES} | line_format "{{{{.country}}}} · {{{{.city}}}}   {{{{.browser}}}} / {{{{.os}}}} ({{{{.device}}}})   {{{{.status}}}} {{{{.uri}}}}   ← {{{{.ref}}}}"')),
])

H = 'histogram_quantile(0.95, sum by (le, route) (rate(openwatch_http_request_seconds_bucket{{{sel}}}[5m])))'
app = dashboard("openwatch-app", "OpenWatch · App", "Live viewers, API, live stream, collector and archive", [
    (4, 4, stat("Live viewers now", P, f"sum(openwatch_live_viewers{{{SEL}}})", color="#ff9933", desc="Browsers connected to the live stream")),
    (4, 4, stat("API requests / s", P, f"sum(rate(openwatch_http_request_seconds_count{{{SEL}}}[5m]))", unit="reqps")),
    (4, 4, stat("API p95", P, f"histogram_quantile(0.95, sum by (le) (rate(openwatch_http_request_seconds_bucket{{{SEL}}}[5m])))", unit="s")),
    (4, 4, stat("API 5xx / 5 min", P, f'sum(increase(openwatch_http_request_seconds_count{{status=~"5..", {SEL}}}[5m])) or vector(0)',
                thresholds={"mode": "absolute", "steps": [{"color": "#22d3a6", "value": None}, {"color": "#ff4d4f", "value": 1}]})),
    (4, 4, stat("Live stream out", P, f"sum(rate(openwatch_stream_bytes_total{{{SEL}}}[5m]))", unit="Bps", color="#38bdf8", desc="Before compression")),
    (4, 4, stat("Archive on disk", P, f"sum(openwatch_archive_bytes{{{SEL}}})", unit="bytes", color="#b69cff")),
    (12, 8, series("Live viewers", P, [(f"sum(openwatch_live_viewers{{{SEL}}})", "viewers")])),
    (12, 8, series("API requests / s by route", P, [(f"sum by (route) (rate(openwatch_http_request_seconds_count{{{SEL}}}[5m]))", "{{route}}")], unit="reqps", stack=True)),
    (12, 8, series("API p95 latency by route", P, [(H.format(sel=SEL), "{{route}}")], unit="s")),
    (12, 8, series("Live stream bytes / s by feed", P, [(f"sum(rate(openwatch_stream_bytes_total{{{SEL}}}[5m]))", "bytes/s"),
                                                     (f"sum by (feed) (rate(openwatch_stream_events_total{{{SEL}}}[5m]))", "events/s {{feed}}")])),
    (8, 10, top("Slowest feeds (p95 fetch, 1 h)", P, f"topk(12, histogram_quantile(0.95, sum by (feed, le) (rate(openwatch_fetch_seconds_bucket{{{SEL}}}[1h]))))", "feed", unit="s")),
    (8, 10, series("Archive size", P, [(f"sum by (kind) (openwatch_archive_bytes{{{SEL}}})", "{{kind}}")], unit="bytes", stack=True)),
    (8, 10, series("Process memory", P, [(f"sum by (job) (process_resident_memory_bytes{{job=~\"collector|api\", {SEL}}})", "{{job}}")], unit="bytes")),
], time_from="now-6h")

NET = 'device!~"lo|veth.*|docker.*|br-.*"'
egress30 = f"sum(rate(node_network_transmit_bytes_total{{{NET}, {SEL}}}[1d])) * 86400 * 30"
health = dashboard("openwatch-server", "OpenWatch · Server & cost", "The VM (CPU, memory, swap, disk, network) and an estimate of the Google Cloud bill", [
    (6, 4, stat("Estimated bill / month", P, f"3.65 + clamp_min({egress30} - 1e9, 0) * 0.12 / 1e9", unit="currencyUSD", color="#22d3a6",
                desc="e2-micro + 30 GB disk free; public IPv4 $0.005/h ≈ $3.65; egress: first 1 GB free, then ≈ $0.12/GB (projected from the last day). Actual: Google Billing export, see docs/monitoring.md")),
    (6, 4, stat("Egress (projected 30 d)", P, egress30, unit="bytes",
                thresholds={"mode": "absolute", "steps": [{"color": "#22d3a6", "value": None}, {"color": "#ffd23f", "value": 8e8}, {"color": "#ff4d4f", "value": 1e9}]})),
    (6, 4, stat("Egress today", P, f"sum(increase(node_network_transmit_bytes_total{{{NET}, {SEL}}}[24h]))", unit="bytes", color="#38bdf8")),
    (6, 4, stat("Fixed: public IPv4", P, "vector(3.65)", unit="currencyUSD", color="#94a3b8", desc="Google bills in-use external IPv4 at $0.005/hour")),
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
    (24, 8, series("Egress per day", P, [(f"sum(increase(node_network_transmit_bytes_total{{{NET}, {SEL}}}[1d]))", "bytes out")], unit="bytes", bars=True)),
], refresh="1m", time_from="now-24h")

os.makedirs(OUT, exist_ok=True)
for name, d in (("overview", overview), ("situation", situation), ("visitors", visitors), ("app", app), ("server", health)):
    with open(os.path.join(OUT, f"{name}.json"), "w") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    print("wrote", f"dashboards/{name}.json", f"({len(d['panels'])} panels)")
