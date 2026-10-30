import { describe, it, expect } from "vitest";
import { buildTrackGeometry } from "../buildTrackGeometry";

describe("buildTrackGeometry", () => {
  it("rejects fewer than 3 coordinate points", () => {
    expect(() => buildTrackGeometry([0, 1], [0, 1])).toThrow();
  });

  it("builds valid ribbon vertices, normals, and triangle indices for a closed loop", () => {
    // Simple 4-point rectangle loop
    const xs = [0, 100, 100, 0];
    const ys = [0, 0, 100, 100];
    const zs = [0, 5, 10, 5];
    const corners = [
      { number: 1, letter: "", angle: 90, x: 100, y: 0, distance: 100 },
      { number: 2, letter: "", angle: 90, x: 100, y: 100, distance: 200 },
    ];

    const geom = buildTrackGeometry(xs, ys, zs, corners, {
      trackWidth: 12,
      elevationExaggeration: 2,
    });

    // Check bounds
    expect(geom.bounds.width).toBe(100);
    expect(geom.bounds.height).toBe(100);
    expect(geom.totalLength).toBeGreaterThan(300);

    // Check ribbon
    expect(geom.ribbon.vertices.length).toBe(xs.length * 2 * 3);
    expect(geom.ribbon.normals.length).toBe(xs.length * 2 * 3);
    expect(geom.ribbon.indices.length).toBe(xs.length * 6);

    // Check centerline and edges
    expect(geom.centerline.length).toBe(xs.length * 3);
    expect(geom.innerEdge.length).toBe(xs.length * 3);
    expect(geom.outerEdge.length).toBe(xs.length * 3);

    // Check corners
    expect(geom.corners.length).toBe(2);
    expect(geom.corners[0].number).toBe(1);
    expect(geom.corners[0].z).toBeGreaterThan(0); // Lifted
  });
});
