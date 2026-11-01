import { describe, expect, it } from "vitest";
import { eyeOf, shownAlt, spherePos, visible } from "./orbits3d";

const near = (a: number[], b: number[]) => a.forEach((v, i) => expect(v).toBeCloseTo(b[i], 6));

describe("satellites in 3D", () => {
  it("places lon/lat on MapLibre's unit globe", () => {
    near(spherePos(0, 0), [0, 0, 1]);
    near(spherePos(90, 0), [1, 0, 0]);
    near(spherePos(0, 90, 1), [0, 2, 0]);
  });

  it("finds the camera from a projection matrix", () => {
    // perspective (90°, near 0.1, far 10) × translate(0, 0, -3): a camera at z = 3 looking at the planet
    const n = 0.1, f = 10, A = -(f + n) / (f - n), B = (-2 * f * n) / (f - n);
    const m = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, A, -1, 0, 0, -3 * A + B, 3];
    near(eyeOf(m), [0, 0, 3]);
  });

  it("hides what the planet is in front of", () => {
    expect(visible([0, 0, 3], [0, 0, 1.1])).toBe(true);
    expect(visible([0, 0, 3], [0, 0, -1.1])).toBe(false);
    expect(visible([0, 0, 3], spherePos(0, 0, 0.002))).toBe(true);
    expect(visible([0, 0, 3], [3, 0, -0.5])).toBe(true); // off to the side, not behind
  });

  it("keeps GEO on screen and orbits in order", () => {
    expect(shownAlt(500)).toBeLessThan(shownAlt(10000));
    expect(shownAlt(35786)).toBeCloseTo(0.45, 1);
  });
});
