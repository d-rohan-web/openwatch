// Satellites at altitude on the globe: a WebGL custom layer that draws each satellite above its ground point, and for
// the selected one a tether down to it and its orbit (all orbits with the "orbits" overlay). Clicks pick by screen distance. MapLibre's globe is a unit
// sphere that ProjectionData.mainMatrix projects to screen, so positions are plain 3D points. Height is log-compressed
// so GEO stays on screen: LEO, HEO and GEO read apart, but it is not to scale.
import type maplibregl from "maplibre-gl";
import { alongTrack } from "./features";
import type { Rec } from "./types";

type V3 = [number, number, number];

/** From this zoom the ground markers take over: a satellite drawn hundreds of km up is nowhere near the street below. */
export const SAT_3D_MAX_ZOOM = 6;

/** Drawn height above the surface, in earth radii: LEO (500 km) ≈ 0.09, HEO (10,000 km) ≈ 0.33, GEO ≈ 0.45. */
export const shownAlt = (km: number) => (0.45 * Math.log1p(Math.max(km, 0) / 300)) / Math.log1p(36000 / 300);

/** (lon, lat, height in earth radii) → MapLibre globe space (unit sphere; see getMatrixForModel). */
export function spherePos(lon: number, lat: number, h = 0): V3 {
  const λ = (lon * Math.PI) / 180, φ = (lat * Math.PI) / 180, r = 1 + h;
  return [r * Math.cos(φ) * Math.sin(λ), r * Math.sin(φ), r * Math.cos(φ) * Math.cos(λ)];
}

/** The camera in globe space: the point the (column-major) matrix sends to clip x = y = w = 0. */
export function eyeOf(m: ArrayLike<number>): V3 {
  const [a, b, c] = [0, 1, 3].map((i) => [m[i], m[4 + i], m[8 + i], -m[12 + i]]);
  const det = (p: number[], q: number[], r: number[]) =>
    p[0] * (q[1] * r[2] - q[2] * r[1]) - p[1] * (q[0] * r[2] - q[2] * r[0]) + p[2] * (q[0] * r[1] - q[1] * r[0]);
  const d = det(a, b, c);
  const swap = (k: number) => [a, b, c].map((row) => row.map((v, j) => (j === k ? row[3] : v)));
  return [0, 1, 2].map((k) => det(...(swap(k) as [number[], number[], number[]])) / d) as V3;
}

/** True when nothing of the planet is between the camera and p. */
export function visible(e: V3, p: V3) {
  const d = [p[0] - e[0], p[1] - e[1], p[2] - e[2]];
  const a = d[0] * d[0] + d[1] * d[1] + d[2] * d[2], b = e[0] * d[0] + e[1] * d[1] + e[2] * d[2];
  const disc = b * b - a * (e[0] * e[0] + e[1] * e[1] + e[2] * e[2] - 1);
  if (disc <= 0) return true;
  const t = (-b - Math.sqrt(disc)) / a;
  return !(t > 1e-6 && t < 1 - 1e-6);
}

const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);

const VS = `attribute vec3 a_pos; attribute vec4 a_col; attribute float a_size; uniform mat4 u_m; varying vec4 v_col;
void main() { gl_Position = u_m * vec4(a_pos, 1.0); gl_PointSize = a_size; v_col = a_col; }`;
// Points are drawn as a satellite glyph: a body, a strut and two solar panels, with a dark outline so they read on any map.
const FS = `precision mediump float; varying vec4 v_col; uniform float u_round;
float sat(vec2 q, float g) {
  vec2 a = abs(q);
  float body = step(max(a.x, a.y), 0.15 + g);
  float panel = step(a.y, 0.17 + g) * step(0.22 - g, a.x) * step(a.x, 0.45 + g);
  float strut = step(a.y, 0.035 + g) * step(a.x, 0.22);
  return max(body, max(panel, strut));
}
void main() {
  if (u_round < 0.5) { gl_FragColor = vec4(v_col.rgb * v_col.a, v_col.a); return; }
  vec2 q = gl_PointCoord - 0.5;
  if (sat(q, 0.0) > 0.5) gl_FragColor = vec4(v_col.rgb, 1.0);
  else if (sat(q, 0.045) > 0.5) gl_FragColor = vec4(0.008, 0.016, 0.04, 0.9);
  else discard;
}`;

type State = { sats: Rec[]; color: (r: Rec) => string; selected?: string; allOrbits: boolean };

export function satelliteLayer(get: () => State): maplibregl.CustomLayerInterface & { pick(x: number, y: number): string | null } {
  let prog: WebGLProgram, buf: WebGLBuffer, vao: WebGLVertexArrayObject | null = null, map: maplibregl.Map;
  let hits: { id: string; x: number; y: number }[] = []; // where each drawn satellite landed on screen (CSS px)
  return {
    id: "sat-3d", type: "custom", renderingMode: "3d",
    pick(x, y) {
      let best: string | null = null, d2 = 14 * 14;
      for (const h of hits) { const d = (h.x - x) ** 2 + (h.y - y) ** 2; if (d < d2) { d2 = d; best = h.id; } }
      return best;
    },
    onAdd(m, gl) {
      map = m;
      const sh = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s); return s; };
      prog = gl.createProgram()!;
      gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
      gl.linkProgram(prog);
      buf = gl.createBuffer()!;
      if ("createVertexArray" in gl) vao = gl.createVertexArray();
    },
    render(gl, args) {
      const pd = args.defaultProjectionData;
      hits = [];
      if (pd.projectionTransition < 0.99 || map.getZoom() >= SAT_3D_MAX_ZOOM) return; // the ground markers take over
      const { sats, color, selected, allOrbits } = get();
      if (!sats.length) return;
      const M = pd.mainMatrix, eye = eyeOf(M), now = Date.now(), cv = map.getCanvas();
      const toScreen = (p: V3) => {
        const w = M[3] * p[0] + M[7] * p[1] + M[11] * p[2] + M[15];
        return { x: ((M[0] * p[0] + M[4] * p[1] + M[8] * p[2] + M[12]) / w + 1) / 2 * cv.clientWidth,
          y: (1 - (M[1] * p[0] + M[5] * p[1] + M[9] * p[2] + M[13]) / w) / 2 * cv.clientHeight };
      };
      const lines: number[] = [], points: number[] = [];
      const vert = (out: number[], p: V3, c: number[], a: number, size = 1) => out.push(...p, ...c, a, size);
      for (const r of sats) {
        const g = alongTrack(r, now) ?? (r.lon !== null ? [r.lon, r.lat!] : null);
        if (!g) continue;
        const h = shownAlt(Number(r.attrs.alt_km) || 500), c = rgb(color(r)), sel = r.id === selected;
        const top = spherePos(g[0], g[1], h), foot = spherePos(g[0], g[1], 0.002);
        if (visible(eye, top)) {
          vert(points, top, c, 1, (sel ? 36 : 26) * devicePixelRatio); // gl_PointSize is in device pixels
          hits.push({ id: r.id, ...toScreen(top) });
          if (sel && visible(eye, foot)) { vert(lines, top, c, 0.8); vert(lines, foot, c, 0.8); }
        }
        const track = r.geometry?.type === "LineString" ? (r.geometry.coordinates as [number, number][]) : [];
        if (!sel && !allOrbits) continue;
        for (let i = 1; i < track.length; i++) {
          const p = spherePos(track[i - 1][0], track[i - 1][1], h), q = spherePos(track[i][0], track[i][1], h);
          if (visible(eye, p) && visible(eye, q)) { vert(lines, p, c, sel ? 0.9 : 0.25); vert(lines, q, c, sel ? 0.9 : 0.25); }
        }
      }
      const g2 = gl as WebGL2RenderingContext;
      if (vao) g2.bindVertexArray(vao);
      gl.useProgram(prog);
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([...lines, ...points]), gl.DYNAMIC_DRAW);
      const attr = (name: string, n: number, off: number) => {
        const loc = gl.getAttribLocation(prog, name);
        gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, n, gl.FLOAT, false, 32, off);
      };
      attr("a_pos", 3, 0); attr("a_col", 4, 12); attr("a_size", 1, 28);
      gl.uniformMatrix4fv(gl.getUniformLocation(prog, "u_m"), false, pd.mainMatrix as Float32Array);
      gl.disable(gl.DEPTH_TEST);
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      const round = gl.getUniformLocation(prog, "u_round");
      gl.uniform1f(round, 0); gl.drawArrays(gl.LINES, 0, lines.length / 8);
      gl.uniform1f(round, 1); gl.drawArrays(gl.POINTS, lines.length / 8, points.length / 8);
      if (vao) g2.bindVertexArray(null);
    },
  };
}
