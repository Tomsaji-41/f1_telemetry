import { describe, it, expect } from "vitest";
import {
  DRIVERS,
  buildTelemetry,
  brakingZones,
  compareTelemetry,
  getRace,
  sectorTable,
  fmtLap,
  weatherAt,
  DEMO_RACE,
} from "./demoData";

describe("Sanity Tests for Demo Data", () => {
  it("1. For every driver: dist/t/speed/throttle/brake/gear/rpm/accelG/drs/x/y all have length 500", () => {
    DRIVERS.forEach((d) => {
      const tel = buildTelemetry(d.code);
      expect(tel.dist.length).toBe(500);
      expect(tel.t.length).toBe(500);
      expect(tel.speed.length).toBe(500);
      expect(tel.throttle.length).toBe(500);
      expect(tel.brake.length).toBe(500);
      expect(tel.gear.length).toBe(500);
      expect(tel.rpm.length).toBe(500);
      expect(tel.accelG.length).toBe(500);
      expect(tel.drs.length).toBe(500);
      expect(tel.x.length).toBe(500);
      expect(tel.y.length).toBe(500);
    });
  });

  it("2. lapTime is between 80 and 100 s for every driver; the fastest driver is VER and slowest is STR", () => {
    const times = DRIVERS.map((d) => {
      const tel = buildTelemetry(d.code);
      return { code: d.code, lapTime: tel.lapTime, topSpeed: Math.max(...tel.speed) };
    });

    console.log("Telemetry performance per driver:");
    times.forEach((t) => {
      console.log(`  Driver ${t.code}: lapTime = ${t.lapTime}s (${fmtLap(t.lapTime)}), topSpeed = ${t.topSpeed} km/h`);
    });

    times.forEach((t) => {
      expect(t.lapTime).toBeGreaterThanOrEqual(80);
      expect(t.lapTime).toBeLessThanOrEqual(100);
    });

    const fastest = [...times].sort((a, b) => a.lapTime - b.lapTime)[0];
    const slowest = [...times].sort((a, b) => b.lapTime - a.lapTime)[0];

    expect(fastest.code).toBe("VER");
    expect(slowest.code).toBe("STR");
  });

  it("3. Max speed between 300 and 345 km/h and min speed between 60 and 120 km/h for VER. brake only 0 or 1", () => {
    const ver = buildTelemetry("VER");
    const maxV = Math.max(...ver.speed);
    const minV = Math.min(...ver.speed);

    expect(maxV).toBeGreaterThanOrEqual(300);
    expect(maxV).toBeLessThanOrEqual(345);
    expect(minV).toBeGreaterThanOrEqual(60);
    expect(minV).toBeLessThanOrEqual(120);

    ver.brake.forEach((b) => {
      expect(b === 0 || b === 1).toBe(true);
    });
  });

  it("4. brakingZones(VER) returns at least 8 zones with peakG between 1 and 6", () => {
    const ver = buildTelemetry("VER");
    const zones = brakingZones(ver);
    expect(zones.length).toBeGreaterThanOrEqual(8);
    zones.forEach((z) => {
      expect(z.peakG).toBeGreaterThanOrEqual(1);
      expect(z.peakG).toBeLessThanOrEqual(6);
    });
  });

  it("5. compareTelemetry delta[0] === 0 and delta at last sample equals B.lapTime - A.lapTime within 0.05 s", () => {
    const cmp = compareTelemetry("VER", "NOR");
    expect(cmp.delta[0]).toBe(0);
    const expectedDiff = cmp.b.lapTime - cmp.a.lapTime;
    const lastDelta = cmp.delta[cmp.delta.length - 1];
    expect(Math.abs(lastDelta - expectedDiff)).toBeLessThanOrEqual(0.05);
  });

  it("6. getRace(): classification 10 rows, first pos 1, STR last with Retired (sample), points sum check, 57 pos rows, stints = pits + 1", () => {
    const race = getRace();
    expect(race.classification.length).toBe(10);
    expect(race.classification[0].pos).toBe(1);
    const str = race.classification[race.classification.length - 1];
    expect(str.code).toBe("STR");
    expect(str.status).toBe("Retired (sample)");

    const pointsSum = race.classification.reduce((sum, c) => sum + c.points, 0);
    console.log("Real points sum:", pointsSum);
    expect(pointsSum).toBeGreaterThan(0);

    expect(race.positionsByLap.length).toBe(57);

    // Stint count check
    DRIVERS.forEach((d) => {
      const driverStints = race.stints.filter((s) => s.driver === d.code).length;
      const driverPits = race.pits.filter((p) => p.driver === d.code).length;
      expect(driverStints).toBe(driverPits + 1);
    });
  });

  it("7. sectorTable(): ideal lap equals bestS1 + bestS2 + bestS3, and s1+s2+s3 equals lap time within 0.002s", () => {
    const tbl = sectorTable();
    tbl.rows.forEach((r) => {
      const sumS = +(r.bestS1 + r.bestS2 + r.bestS3).toFixed(3);
      expect(Math.abs(r.ideal - sumS)).toBeLessThanOrEqual(0.001);
    });

    const race = getRace();
    Object.values(race.laps).forEach((driverLaps) => {
      driverLaps.forEach((l) => {
        const sum = l.s1 + l.s2 + l.s3;
        expect(Math.abs(sum - l.time)).toBeLessThanOrEqual(0.002);
      });
    });
  });

  it("8. API fetcher intercepts demo endpoints correctly without network", async () => {
    const { fetcher } = await import("../lib/api");

    const endpoints = [
      "/api/health",
      "/api/schedule",
      "/api/live",
      "/api/charts/championship-progression",
      "/api/charts/grid-vs-finish",
      "/api/charts/stints",
      "/api/charts/pit-stops",
      "/api/charts/position-by-lap",
      "/api/charts/gap-evolution",
      "/api/charts/sector-heatmap",
      "/api/charts/quali-gap",
      "/api/charts/degradation?driver=VER",
      "/api/charts/weather",
      "/api/charts/telemetry-compare?driver1=VER&driver2=NOR",
    ];

    for (const ep of endpoints) {
      const res = await fetcher(ep);
      expect(res).toBeDefined();
      expect(res.status).toBe("ok");
    }
  });

  it("9. Weather observations and scrubbing: valid numbers across all laps", () => {
    for (let lap = 1; lap <= DEMO_RACE.laps; lap++) {
      const w = weatherAt(lap);
      expect(w).toBeDefined();
      expect(typeof w.airC).toBe("number");
      expect(typeof w.trackC).toBe("number");
      expect(typeof w.humidity).toBe("number");
      expect(typeof w.windMs).toBe("number");
      expect(isNaN(w.airC)).toBe(false);
      expect(isNaN(w.trackC)).toBe(false);
    }
  });
});
