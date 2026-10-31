import { expect, test } from "vitest";
import { alongTrack, glyphOf, heading, inScope, onMap, passOver, project, toFeatures } from "./features";
import type { Rec } from "./types";

const rec = (o: Partial<Rec>): Rec => ({ feed: "f", id: "1", title: "t", kind: "x", severity: null, lon: 77, lat: 28,
  geometry: null, observed_at: null, fetched_at: "", raw_sha256: null, attrs: {}, ...o });

test("point record → one point feature", () => {
  expect(toFeatures([rec({})]).features).toHaveLength(1);
});

test("polygon → polygon only; track line → line + point", () => {
  const poly = { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] };
  expect(toFeatures([rec({ geometry: poly })]).features.map((f) => f.geometry.type)).toEqual(["Polygon"]);
  const line = { type: "LineString", coordinates: [[0, 0], [1, 1]] };
  expect(toFeatures([rec({ geometry: line })]).features.map((f) => f.geometry.type)).toEqual(["LineString", "Point"]);
});

test("unlocated records draw nothing", () => {
  expect(toFeatures([rec({ lon: null, lat: null })]).features).toHaveLength(0);
});

test("aircraft with a track becomes a rotated arrow, severity colours win", () => {
  const [f] = toFeatures([rec({ kind: "aircraft", attrs: { track: 90 } })]).features;
  expect(f.properties).toMatchObject({ arrow: true, rot: 90 });
  expect(heading(rec({ attrs: { track: 400 } }))).toBeNull();
  expect(toFeatures([rec({ severity: "critical" })]).features[0].properties.color).toBe("#ff3b3b");
});

test("India scope drops located records outside the area, keeps unlocated; holes count as outside", () => {
  const area = [[[[60, 0], [100, 0], [100, 40], [60, 40], [60, 0]], [[70, 10], [72, 10], [72, 12], [70, 12], [70, 10]]]] as any;
  expect(toFeatures([rec({ lon: -70, lat: 40 }), rec({ id: "2" }), rec({ id: "3", lon: null, lat: null, geometry: null })], undefined, area)
    .features).toHaveLength(1);
  expect(inScope(rec({ lon: 71, lat: 11 }), area)).toBe(false);
  expect(inScope(rec({ lon: null, lat: null }), area)).toBe(true);
});

test("dead reckoning: 360 kt due east for 60 s ≈ 0.11° of longitude at the equator; ground traffic stays", () => {
  const t0 = Date.parse("2026-01-01T00:00:00Z");
  const a = rec({ lon: 77, lat: 0, observed_at: "2026-01-01T00:00:00Z", attrs: { gs_kt: 360, track: 90 } });
  const [lon, lat] = project(a, t0 + 60_000)!;
  expect(lon - 77).toBeCloseTo(0.0998, 3);
  expect(lat).toBeCloseTo(0, 6);
  expect(project({ ...a, attrs: { ...a.attrs, on_ground: true } }, t0 + 60_000)).toEqual([77, 0]);
  expect(project(a, t0 + 3_600_000)![0] - 77).toBeCloseTo(0.0998 * 3, 2);  // capped at 180 s
});

test("satellite ground tracks only for the selected one", () => {
  const sat = rec({ feed: "satellites", geometry: { type: "LineString", coordinates: [[0, 0], [1, 1]] } });
  expect(toFeatures([sat]).features.map((f) => f.geometry.type)).toEqual(["Point"]);
  expect(toFeatures([sat], undefined, null, undefined, "1").features.map((f) => f.geometry.type)).toEqual(["LineString", "Point"]);
});

test("satellites glide along their track and report passes over an area", () => {
  const t0 = Date.parse("2026-01-01T00:00:00Z");
  const sat = rec({ feed: "satellites", kind: "indian", lon: 0, lat: 0, observed_at: "2026-01-01T00:00:00Z", attrs: { orbit: "LEO" },
    geometry: { type: "LineString", coordinates: [[0, 0], [10, 0], [20, 0], [30, 0]] } });
  expect(alongTrack(sat, t0 + 60_000)).toEqual([5, 0]);  // halfway through the first 2-min step
  const box = [[[[15, -5], [25, -5], [25, 5], [15, 5], [15, -5]]]] as any;
  expect(passOver(sat, box, t0)).toMatchObject({ over: false, inMin: 4 });
  expect(passOver(sat, box, t0 + 240_000)).toMatchObject({ over: true, outMin: 2 });
  expect(inScope(rec({ feed: "satellites", lon: -100, lat: 0 }), box)).toBe(true);
  expect(glyphOf(rec({ kind: "earthquake" }))).toBe("activity");
});

test("map shows quakes that are significant (M3.5+) or from the last 24 h", () => {
  const now = Date.parse("2026-01-10T00:00:00Z");
  const q = (mag: number, at: string) => rec({ kind: "earthquake", observed_at: at, attrs: { mag } });
  expect(onMap(q(2.8, "2026-01-05T00:00:00Z"), now)).toBe(false);
  expect(onMap(q(2.8, "2026-01-09T12:00:00Z"), now)).toBe(true);
  expect(onMap(q(4.1, "2026-01-01T00:00:00Z"), now)).toBe(true);
  expect(onMap(rec({}), now)).toBe(true);
});
