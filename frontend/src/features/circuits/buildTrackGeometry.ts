/**
 * frontend/src/features/circuits/buildTrackGeometry.ts
 *
 * Pure geometry calculations for 3D track ribbon, boundaries, and corner markers.
 * Zero DOM or Three.js dependencies — fully testable in Node/Vitest.
 */

export interface TrackPoint {
  x: number;
  y: number;
  z: number;
}

export interface CornerMarker {
  number: number;
  letter: string;
  angle: number;
  x: number;
  y: number;
  z: number;
  distance: number;
}

export interface TrackGeometryOptions {
  trackWidth?: number; // width in meters (default: 14)
  elevationExaggeration?: number; // vertical exaggeration factor (default: 3)
}

export interface BuiltTrackGeometry {
  centerline: Float32Array; // [x, y, z, x, y, z, ...]
  ribbon: {
    vertices: Float32Array; // 2 * N * 3
    normals: Float32Array; // 2 * N * 3
    indices: Uint32Array; // 6 * N
  };
  innerEdge: Float32Array; // N * 3
  outerEdge: Float32Array; // N * 3
  corners: CornerMarker[];
  bounds: {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
    minZ: number;
    maxZ: number;
    width: number;
    height: number;
    depth: number;
  };
  totalLength: number;
}

/**
 * Builds 3D ribbon geometry, boundaries, and lifted corner markers from raw telemetry coordinates.
 */
export function buildTrackGeometry(
  rawXs: number[],
  rawYs: number[],
  rawZs?: number[],
  rawCorners?: Array<{
    number: number;
    letter?: string;
    angle?: number;
    distance?: number;
    x?: number;
    y?: number;
  }>,
  options: TrackGeometryOptions = {}
): BuiltTrackGeometry {
  const width = options.trackWidth ?? 14.0;
  const exaggeration = options.elevationExaggeration ?? 3.0;

  const n = rawXs.length;
  if (n < 3) {
    throw new Error("Track coordinates must contain at least 3 points to build geometry.");
  }

  const zs = rawZs && rawZs.length === n ? rawZs : new Array(n).fill(0);

  // 1. Calculate raw bounds & center of mass
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;

  for (let i = 0; i < n; i++) {
    const x = rawXs[i];
    const y = rawYs[i];
    const z = zs[i] * exaggeration;
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
    if (z < minZ) minZ = z;
    if (z > maxZ) maxZ = z;
  }

  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  const centerZ = (minZ + maxZ) / 2;

  // 2. Zero-center coordinates and populate centerline
  const centeredPoints: TrackPoint[] = new Array(n);
  const centerline = new Float32Array(n * 3);
  let totalLength = 0;

  for (let i = 0; i < n; i++) {
    const cx = rawXs[i] - centerX;
    const cy = rawYs[i] - centerY;
    const cz = zs[i] * exaggeration - centerZ;

    centeredPoints[i] = { x: cx, y: cy, z: cz };
    centerline[i * 3] = cx;
    centerline[i * 3 + 1] = cy;
    centerline[i * 3 + 2] = cz;

    if (i > 0) {
      const prev = centeredPoints[i - 1];
      totalLength += Math.sqrt((cx - prev.x) ** 2 + (cy - prev.y) ** 2 + (cz - prev.z) ** 2);
    }
  }

  // Close loop length if circuit loop
  const p0 = centeredPoints[0];
  const pn = centeredPoints[n - 1];
  totalLength += Math.sqrt((p0.x - pn.x) ** 2 + (p0.y - pn.y) ** 2 + (p0.z - pn.z) ** 2);

  // 3. Build Extruded Ribbon Mesh & Edges
  // Each point i has 2 ribbon vertices: Left (inner/outer) and Right
  const ribbonVertices = new Float32Array(n * 2 * 3);
  const ribbonNormals = new Float32Array(n * 2 * 3);
  const innerEdge = new Float32Array(n * 3);
  const outerEdge = new Float32Array(n * 3);
  const halfWidth = width / 2;

  for (let i = 0; i < n; i++) {
    const prev = centeredPoints[(i - 1 + n) % n];
    const next = centeredPoints[(i + 1) % n];
    const curr = centeredPoints[i];

    // Tangent vector
    let tx = next.x - prev.x;
    let ty = next.y - prev.y;
    let tz = next.z - prev.z;
    const tLen = Math.sqrt(tx * tx + ty * ty + tz * tz) || 1.0;
    tx /= tLen;
    ty /= tLen;
    tz /= tLen;

    // Lateral normal in XY plane perpendicular to tangent: (-ty, tx, 0)
    let lx = -ty;
    let ly = tx;
    let lz = 0;
    const lLen = Math.sqrt(lx * lx + ly * ly) || 1.0;
    lx /= lLen;
    ly /= lLen;

    // Up vector = Lateral cross Tangent
    let nx = ly * tz - lz * ty;
    let ny = lz * tx - lx * tz;
    let nz = lx * ty - ly * tx;
    const nLen = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1.0;
    nx /= nLen;
    ny /= nLen;
    nz /= nLen;
    if (nz < 0) {
      // Ensure upward normal facing Z+
      nx = -nx;
      ny = -ny;
      nz = -nz;
    }

    // Left edge (Inner/Outer)
    const leftX = curr.x - halfWidth * lx;
    const leftY = curr.y - halfWidth * ly;
    const leftZ = curr.z - halfWidth * lz;

    // Right edge
    const rightX = curr.x + halfWidth * lx;
    const rightY = curr.y + halfWidth * ly;
    const rightZ = curr.z + halfWidth * lz;

    // Store edges
    innerEdge[i * 3] = leftX;
    innerEdge[i * 3 + 1] = leftY;
    innerEdge[i * 3 + 2] = leftZ;

    outerEdge[i * 3] = rightX;
    outerEdge[i * 3 + 1] = rightY;
    outerEdge[i * 3 + 2] = rightZ;

    // Store ribbon vertices
    const idx2 = i * 2;
    ribbonVertices[idx2 * 3] = leftX;
    ribbonVertices[idx2 * 3 + 1] = leftY;
    ribbonVertices[idx2 * 3 + 2] = leftZ;

    ribbonVertices[(idx2 + 1) * 3] = rightX;
    ribbonVertices[(idx2 + 1) * 3 + 1] = rightY;
    ribbonVertices[(idx2 + 1) * 3 + 2] = rightZ;

    // Store ribbon normals
    ribbonNormals[idx2 * 3] = nx;
    ribbonNormals[idx2 * 3 + 1] = ny;
    ribbonNormals[idx2 * 3 + 2] = nz;

    ribbonNormals[(idx2 + 1) * 3] = nx;
    ribbonNormals[(idx2 + 1) * 3 + 1] = ny;
    ribbonNormals[(idx2 + 1) * 3 + 2] = nz;
  }

  // 4. Triangle indices for ribbon mesh (2 triangles per segment)
  const indices = new Uint32Array(n * 6);
  for (let i = 0; i < n; i++) {
    const next = (i + 1) % n;
    const i0 = i * 2; // Left i
    const i1 = i * 2 + 1; // Right i
    const i2 = next * 2; // Left next
    const i3 = next * 2 + 1; // Right next

    const idx6 = i * 6;
    // Triangle 1: i0, i1, i2
    indices[idx6] = i0;
    indices[idx6 + 1] = i1;
    indices[idx6 + 2] = i2;

    // Triangle 2: i1, i3, i2
    indices[idx6 + 3] = i1;
    indices[idx6 + 4] = i3;
    indices[idx6 + 5] = i2;
  }

  // 5. Corner markers: zero-center and lift slightly above surface
  const corners: CornerMarker[] = [];
  if (rawCorners && rawCorners.length > 0) {
    for (const c of rawCorners) {
      let cx = 0;
      let cy = 0;
      let cz = 0;

      if (c.x !== undefined && c.y !== undefined) {
        cx = c.x - centerX;
        cy = c.y - centerY;
        // Find nearest Z from centerline
        let bestDist = Infinity;
        for (const pt of centeredPoints) {
          const d = (pt.x - cx) ** 2 + (pt.y - cy) ** 2;
          if (d < bestDist) {
            bestDist = d;
            cz = pt.z;
          }
        }
      } else if (c.distance !== undefined && totalLength > 0) {
        // Approximate from track distance ratio
        const ratio = (c.distance % totalLength) / totalLength;
        const ptIdx = Math.floor(ratio * n);
        const pt = centeredPoints[ptIdx % n];
        cx = pt.x;
        cy = pt.y;
        cz = pt.z;
      }

      corners.push({
        number: c.number,
        letter: c.letter || "",
        angle: c.angle || 0,
        x: cx,
        y: cy,
        z: cz + 8.0, // lifted 8m above track surface for clear billboard visibility
        distance: c.distance || 0,
      });
    }
  }

  return {
    centerline,
    ribbon: {
      vertices: ribbonVertices,
      normals: ribbonNormals,
      indices,
    },
    innerEdge,
    outerEdge,
    corners,
    bounds: {
      minX: minX - centerX,
      maxX: maxX - centerX,
      minY: minY - centerY,
      maxY: maxY - centerY,
      minZ: minZ - centerZ,
      maxZ: maxZ - centerZ,
      width: maxX - minX,
      height: maxY - minY,
      depth: maxZ - minZ,
    },
    totalLength,
  };
}
