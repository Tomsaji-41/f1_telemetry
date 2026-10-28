/**
 * Single API client module for Pitboss telemetry.
 * All URLs are constructed and fetched here using relative /api paths.
 * In DEMO_MODE, returns synthetic demo data for non-chat endpoints.
 */

import {
  DEMO_MODE,
  DEMO_RACE,
  DEMO_LABEL,
  DRIVERS,
  TEAM_LIST,
  getRace,
  sectorTable,
  degradation,
  buildTelemetry,
  compareTelemetry,
  brakingZones,
  aeroProxies,
  gearUsage,
  WEATHER,
  weatherAt,
  STANDINGS_DRIVERS,
  STANDINGS_CONSTRUCTORS,
  POINTS_PROGRESSION,
  SAMPLE_CALENDAR,
  LEGENDS,
  ERAS,
  teamById,
  driverByCode,
  fmtLap,
  Compound,
  COMPOUND_NAME,
} from "@/demo/demoData";

export interface HealthResponse {
  status: string;
  fetched_at?: string;
  sources?: string[];
  keys: {
    gemini_configured: boolean;
    groq_configured: boolean;
  };
  models?: Record<string, string>;
  cache?: Record<string, any>;
  source_reachability?: Record<string, string>;
}

export function getClientHeaders(): Record<string, string> {
  const clientId =
    typeof window !== "undefined"
      ? localStorage.getItem("pitboss_client_id") || "web-client"
      : "server";
  return {
    "Content-Type": "application/json",
    "X-Client-Id": clientId,
  };
}

/**
 * Intercept and synthesize demo responses for non-chat API calls
 */
function getDemoResponse(url: string): any | null {
  if (!DEMO_MODE) return null;

  // Don't intercept chat endpoints!
  if (url.includes("/api/chat")) return null;

  const parsed = new URL(url, "http://localhost:3000");
  const path = parsed.pathname;
  const params = parsed.searchParams;

  // 1. Health
  if (path === "/api/health") {
    return {
      status: "ok",
      fetched_at: "14:00 UTC",
      sources: ["Demo Engine (Sample Data)"],
      keys: { gemini_configured: true, groq_configured: true },
    };
  }

  // 2. Schedule
  if (path === "/api/schedule") {
    return {
      status: "ok",
      year: parseInt(params.get("year") || "2026", 10),
      total_rounds: 24,
      latest_completed_round: 12,
      latest_completed_race: {
        round: 12,
        race_name: DEMO_RACE.name,
        grand_prix: DEMO_RACE.name,
      },
      schedule: SAMPLE_CALENDAR.map((c) => ({
        round: c.round,
        race_name: c.name,
        grand_prix: c.name,
        status: c.status,
        date: "2026-06-15",
      })),
    };
  }

  // 3. Live
  if (path === "/api/live" || path === "/api/live/status") {
    const lap = parseInt(params.get("lap") || "30", 10);
    const race = getRace();
    const w = weatherAt(lap);
    return {
      status: "ok",
      is_live: false,
      mode: "replay",
      session_label: `Replay: ${DEMO_RACE.name}, ${DEMO_RACE.session}`,
      lap,
      weather: {
        airTemp: `${w.airC}°C`,
        trackTemp: `${w.trackC}°C`,
        humidity: `${w.humidity}%`,
        windSpeed: `${w.windMs} m/s`,
        rainRisk: w.rain ? "100%" : "0%",
      },
      race_control: race.raceControl.filter((m) => m.lap <= lap),
    };
  }

  // 4. Standings / progression / championship
  if (path === "/api/charts/championship-progression") {
    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      series: Object.entries(POINTS_PROGRESSION).map(([code, pts]) => ({
        code,
        name: driverByCode(code).name,
        points: pts[pts.length - 1],
        position: STANDINGS_DRIVERS.find((s) => s.code === code)?.pos ?? 1,
        y: pts,
        color: teamById(driverByCode(code).team).color,
      })),
      standings_drivers: STANDINGS_DRIVERS,
      standings_constructors: STANDINGS_CONSTRUCTORS,
    };
  }

  // 5. Grid vs Finish
  if (path === "/api/charts/grid-vs-finish") {
    const race = getRace();
    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      series: race.classification.map((c) => ({
        code: c.code,
        name: c.name,
        team: c.team,
        color: c.teamColor,
        grid: c.grid,
        finish: c.pos,
        delta: c.placesGained,
        status: c.status,
        badge: c.status.startsWith("Retired") ? "DNF" : null,
        is_dnf: c.status.startsWith("Retired"),
        is_dsq: false,
        points: c.points,
        timeOrGap: c.timeOrGap,
      })),
    };
  }

  // 6. Stints
  if (path === "/api/charts/stints") {
    const race = getRace();
    const series = race.stints.map((s) => ({
      driver: s.driver,
      code: s.driver,
      stint: s.stint,
      compound: COMPOUND_NAME[s.compound],
      compound_code: s.compound,
      start_lap: s.startLap,
      end_lap: s.endLap,
      laps: s.laps,
      length: s.laps,
    }));
    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      stints: series,
      series,
      order: DRIVERS.map((d) => d.code),
    };
  }

  // 7. Pit stops
  if (path === "/api/charts/pit-stops") {
    const race = getRace();
    const stops = race.pits.map((p) => {
      const d = driverByCode(p.driver);
      const team = teamById(d.team);
      return {
        driver_id: p.driver,
        code: p.driver,
        name: d.name,
        team: team.name,
        color: team.color,
        stop: p.stop,
        lap: p.lap,
        duration_s: p.stationaryS,
        pit_lane_s: p.pitLaneS,
        suspect: false,
      };
    });
    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      stops,
      series: stops,
      p95_duration_s: 4.5,
    };
  }

  // 8. Position by lap
  if (path === "/api/charts/position-by-lap") {
    const race = getRace();
    const x = race.positionsByLap.map((r) => r.lap as number);
    const series = DRIVERS.map((d) => ({
      driver: d.code,
      code: d.code,
      name: d.name,
      team: teamById(d.team).name,
      colour: teamById(d.team).color,
      color: teamById(d.team).color,
      x,
      y: race.positionsByLap.map((r) => (r[d.code] !== null ? (r[d.code] as number) : 10)),
    }));
    const driver_meta = DRIVERS.map((d) => ({
      code: d.code,
      name: d.name,
      team: teamById(d.team).name,
      colour: teamById(d.team).color,
    }));
    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      x,
      series,
      driver_meta,
      axes: {
        x: { label: "Lap", unit: "" },
        y: { label: "Position", unit: "" },
      },
    };
  }

  // 9. Gap evolution
  if (path === "/api/charts/gap-evolution") {
    const race = getRace();
    const x = race.gapByLap.map((r) => r.lap as number);
    const series = race.classification.map((c) => ({
      driver: c.code,
      code: c.code,
      name: c.name,
      position: c.pos,
      gap: c.timeOrGap,
      color: c.teamColor,
    }));
    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      x,
      series,
      axes: {
        x: { label: "Lap", unit: "" },
        y: { label: "Gap to leader", unit: "s" },
      },
    };
  }

  // 10. Lap scatter / pace
  if (path === "/api/charts/lap-scatter") {
    const race = getRace();
    const points: any[] = [];
    DRIVERS.forEach((d) => {
      const driverLaps = race.laps[d.code] || [];
      driverLaps.forEach((l) => {
        points.push({
          lap: l.lap,
          t_s: l.time,
          compound: l.compound,
          tyre_life: l.tyreAge,
          code: d.code,
          is_pit: l.pit,
        });
      });
    });
    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      points,
      series: points,
    };
  }

  // 11. Sectors
  if (path === "/api/charts/sector-heatmap" || path === "/api/charts/sectors") {
    const tbl = sectorTable();
    const rows = tbl.rows.map((r) => ({
      code: r.code,
      s1_best_ms: Math.round(r.bestS1 * 1000),
      s1_mean_ms: Math.round(r.avgS1 * 1000),
      s1_gap_ms: Math.round((r.bestS1 - tbl.sessionBest.s1) * 1000),
      s1_session_best: r.bestS1 === tbl.sessionBest.s1,
      s2_best_ms: Math.round(r.bestS2 * 1000),
      s2_mean_ms: Math.round(r.avgS2 * 1000),
      s2_gap_ms: Math.round((r.bestS2 - tbl.sessionBest.s2) * 1000),
      s2_session_best: r.bestS2 === tbl.sessionBest.s2,
      s3_best_ms: Math.round(r.bestS3 * 1000),
      s3_mean_ms: Math.round(r.avgS3 * 1000),
      s3_gap_ms: Math.round((r.bestS3 - tbl.sessionBest.s3) * 1000),
      s3_session_best: r.bestS3 === tbl.sessionBest.s3,
      ideal_ms: Math.round(r.ideal * 1000),
    }));
    const drivers = DRIVERS.map((d) => ({
      code: d.code,
      name: d.name,
      colour: teamById(d.team).color,
    }));
    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      rows,
      drivers,
      table: tbl,
    };
  }

  // 12. Qualifying Gap
  if (path === "/api/charts/quali-gap") {
    const final_grid = DRIVERS.map((d) => ({
      position: d.grid,
      code: d.code,
      name: d.name,
      team: teamById(d.team).name,
      best_time_s: buildTelemetry(d.code).lapTime,
      eliminated_in: d.grid <= 10 ? "Q3" : "Q2",
    })).sort((a, b) => a.position - b.position);
    const poleTime = final_grid[0].best_time_s;
    const stages: Record<string, any[]> = {
      Q3: final_grid.map((g) => ({
        code: g.code,
        name: g.name,
        team: g.team,
        time_s: g.best_time_s,
        gap_s: +(g.best_time_s - poleTime).toFixed(3),
        gap_str: g.position === 1 ? "POLE" : `+${(g.best_time_s - poleTime).toFixed(3)}s`,
      })),
      Q2: final_grid.map((g) => ({
        code: g.code,
        name: g.name,
        team: g.team,
        time_s: +(g.best_time_s + 0.3).toFixed(3),
        gap_s: +(g.best_time_s - poleTime).toFixed(3),
        gap_str: `+${(g.best_time_s - poleTime).toFixed(3)}s`,
      })),
      Q1: final_grid.map((g) => ({
        code: g.code,
        name: g.name,
        team: g.team,
        time_s: +(g.best_time_s + 0.7).toFixed(3),
        gap_s: +(g.best_time_s - poleTime).toFixed(3),
        gap_str: `+${(g.best_time_s - poleTime).toFixed(3)}s`,
      })),
    };
    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      stages,
      final_grid,
    };
  }

  // 13. Degradation
  if (path === "/api/charts/degradation") {
    const driver = params.get("driver") || "VER";
    const degs = degradation(driver);
    const race = getRace();
    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      driver,
      stints: degs.map((dg) => {
        const pts = (race.laps[driver] || [])
          .filter((l) => {
            const st = race.stints.find((s) => s.driver === driver && s.stint === dg.stint);
            return st && l.lap >= st.startLap && l.lap <= st.endLap && !l.pit;
          })
          .map((l) => ({ tyre_life: l.tyreAge, t_s: l.time }));
        return {
          stint: dg.stint,
          compound: COMPOUND_NAME[dg.compound as Compound]?.toUpperCase() || "MEDIUM",
          n: dg.n,
          slope_s_per_lap: dg.slope,
          r2: dg.r2,
          points: pts,
          fuel_corrected: true,
          low_sample: dg.confidence === "low",
        };
      }),
    };
  }

  // 14. Weather chart
  if (path === "/api/charts/weather") {
    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      rows: WEATHER.map((w) => ({
        lap: w.lap,
        air_c: w.airC,
        track_c: w.trackC,
        humidity: w.humidity,
        wind_ms: w.windMs,
        rain: w.rain,
      })),
      rain_bands: [],
    };
  }

  // 15. Telemetry Compare
  if (path === "/api/charts/telemetry-compare") {
    const d1 = params.get("d1") || params.get("driver1") || "VER";
    const d2 = params.get("d2") || params.get("driver2") || "NOR";
    const cmp = compareTelemetry(d1, d2);
    const zonesA = brakingZones(cmp.a);
    const zonesB = brakingZones(cmp.b);
    const aeroA = aeroProxies(cmp.a);
    const aeroB = aeroProxies(cmp.b);
    const gearA = gearUsage(cmp.a);
    const gearB = gearUsage(cmp.b);

    return {
      status: "ok",
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
      circuit_name: DEMO_RACE.circuit,
      driver1: d1,
      driver2: d2,
      drivers: [
        {
          code: cmp.a.code,
          name: driverByCode(cmp.a.code).name,
          team: teamById(driverByCode(cmp.a.code).team).name,
          colour: teamById(driverByCode(cmp.a.code).team).color,
        },
        {
          code: cmp.b.code,
          name: driverByCode(cmp.b.code).name,
          team: teamById(driverByCode(cmp.b.code).team).name,
          colour: teamById(driverByCode(cmp.b.code).team).color,
        },
      ],
      lap_time_1: cmp.a.lapTime,
      lap_time_2: cmp.b.lapTime,
      lap_delta: +(cmp.b.lapTime - cmp.a.lapTime).toFixed(3),
      distance: cmp.a.dist,
      traces: {
        driver1: {
          code: cmp.a.code,
          speed: cmp.a.speed,
          throttle: cmp.a.throttle,
          brake: cmp.a.brake,
          gear: cmp.a.gear,
          rpm: cmp.a.rpm,
          drs: cmp.a.drs,
        },
        driver2: {
          code: cmp.b.code,
          speed: cmp.b.speed,
          throttle: cmp.b.throttle,
          brake: cmp.b.brake,
          gear: cmp.b.gear,
          rpm: cmp.b.rpm,
          drs: cmp.b.drs,
        },
        speed_delta: cmp.a.speed.map((s, i) => +(s - cmp.b.speed[i]).toFixed(1)),
      },
      track_map: cmp.a.x.map((x, i) => ({
        x,
        y: cmp.a.y[i],
        dist: cmp.a.dist[i],
        delta_speed: +(cmp.a.speed[i] - cmp.b.speed[i]).toFixed(1),
      })),
      braking_table: zonesA.map((z, i) => ({
        zone: i + 1,
        distance_m: z.startM,
        length_m: z.endM - z.startM,
        entry_speed_kmh: z.entryKmh,
        min_speed_kmh: z.minKmh,
        delta_kmh: +(z.entryKmh - z.minKmh).toFixed(1),
        decel_g: z.peakG,
      })),
      proxies: {
        top_speed: {
          proxy: "Top Speed",
          [cmp.a.code]: aeroA.topSpeedKmh,
          [cmp.b.code]: aeroB.topSpeedKmh,
          unit: "km/h",
        },
        min_speed: {
          proxy: "Minimum Apex Speed",
          [cmp.a.code]: aeroA.minSpeedKmh,
          [cmp.b.code]: aeroB.minSpeedKmh,
          unit: "km/h",
        },
        high_speed_avg: {
          proxy: "High Speed (>250km/h) Mean",
          [cmp.a.code]: aeroA.highSpeedAvgKmh,
          [cmp.b.code]: aeroB.highSpeedAvgKmh,
          unit: "km/h",
        },
      },
    };
  }

  // 15. Facts endpoint
  if (path.startsWith("/api/v1/facts")) {
    const race = getRace();
    return {
      status: "ok",
      year: 2026,
      round: 12,
      grand_prix: DEMO_RACE.name,
      circuit: DEMO_RACE.circuit,
      winner: race.classification[0].name,
      results: race.classification.map((c) => ({
        position: c.pos,
        driver: c.name,
        code: c.code,
        constructor: c.team,
        grid: c.grid,
        status: c.status,
        time: c.timeOrGap,
        points: c.points,
        fastest_lap: fmtLap(c.bestLap),
        laps: c.lapsCompleted,
      })),
      source: "Demo Data",
      coverage_note: DEMO_LABEL,
    };
  }

  return null;
}

export async function fetchApi<T = any>(endpoint: string, options?: RequestInit): Promise<T> {
  const path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = path.startsWith("/api") ? path : `/api${path}`;

  // Demo mode interception
  const demoData = getDemoResponse(url);
  if (demoData !== null) {
    return Promise.resolve(demoData as T);
  }

  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        ...getClientHeaders(),
        ...options?.headers,
      },
    });

    if (!res.ok) {
      console.error(`[API Error] Cannot reach the data service: ${res.status} ${res.statusText} at ${url}`);
      const err: any = new Error(`Cannot reach the data service. Retry (URL: ${url}, Status: ${res.status})`);
      err.url = url;
      err.status = res.status;
      throw err;
    }

    return await res.json();
  } catch (err: any) {
    if (!err.url) {
      err.url = url;
      err.status = err.status || "offline";
    }
    console.error(`[Network Error] Cannot reach the data service at ${url}:`, err);
    throw err;
  }
}

export async function checkHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>("/api/health");
}

// ── Chart-specific fetcher and helpers ────────────────────────────────────

export class ApiError extends Error {
  url: string;
  statusCode: number;
  constructor(url: string, statusCode: number) {
    super(`${statusCode} ${url}`);
    this.url = url;
    this.statusCode = statusCode;
    this.name = "ApiError";
  }
}

/**
 * Minimal fetcher for SWR — returns JSON or throws ApiError.
 * In DEMO_MODE, returns synthetic data.
 */
export async function fetcher<T = any>(url: string): Promise<T> {
  const demoData = getDemoResponse(url);
  if (demoData !== null) {
    return Promise.resolve(demoData as T);
  }

  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) {
    console.error("API error", r.status, url);
    throw new ApiError(url, r.status);
  }
  return r.json();
}

/**
 * Build a query string from an object.
 * Arrays are expanded to repeated keys, null/empty values are dropped.
 */
export const qs = (p: Record<string, any>): string =>
  new URLSearchParams(
    Object.entries(p)
      .filter(([, v]) => v != null && v !== "")
      .flatMap(([k, v]) =>
        Array.isArray(v) ? v.map((x) => [k, String(x)]) : [[k, String(v)]]
      )
  ).toString();
