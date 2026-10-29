"use client";

/**
 * TelemetryTeleportView — Telemetry Teleport page view (V7-2 & V6 P10.2 spec).
 * Contains:
 * 1. Two-driver telemetry comparison stack (Speed, Delta, Throttle, Brake, Gear, RPM, DRS).
 * 2. Track map with speed delta heat map.
 * 3. Braking zones table (entry speed, apex min speed, distance, deceleration g).
 * 4. Aerodynamic & Chassis engineering proxies.
 * 5. Default drivers: two fastest qualifiers of selected race from the API.
 */
import React, { useState, useEffect, useMemo, useRef } from "react";
import { scaleLinear } from "d3-scale";
import { ChartState } from "@/components/charts/ChartState";
import { Gauge, Zap, Wind, ShieldAlert, ChevronRight, Activity } from "lucide-react";
import en from "@/content/en.json";
import { fetcher } from "@/lib/api";

interface DriverTrace {
  code: string;
  speed: number[];
  throttle: number[];
  brake: number[];
  gear: number[];
  rpm: number[];
  drs: number[];
}

interface TrackPoint {
  x: number;
  y: number;
  dist: number;
  delta_speed: number;
}

interface BrakingZone {
  zone: number;
  distance_m: number;
  length_m: number;
  entry_speed_kmh: number;
  min_speed_kmh: number;
  delta_kmh: number;
  decel_g: number;
}

interface TelemetryCompareData {
  status?: string;
  source?: string;
  coverage_note?: string;
  fetched_at?: string;
  driver1?: string;
  driver2?: string;
  drivers?: Array<{ code: string; name: string; team: string; colour: string }>;
  lap_time_1?: number | null;
  lap_time_2?: number | null;
  lap_delta?: number | null;
  distance?: number[];
  traces?: {
    driver1: DriverTrace;
    driver2: DriverTrace;
    speed_delta: number[];
  };
  track_map?: TrackPoint[];
  braking_table?: BrakingZone[];
  proxies?: Record<string, any>;
  job_id?: string;
  eta_s?: number;
}

interface TelemetryTeleportViewProps {
  year: number;
  round: number;
}

export function TelemetryTeleportView({ year, round }: TelemetryTeleportViewProps) {
  const [data, setData] = useState<TelemetryCompareData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<any>(null);
  const [selectedDriver1, setSelectedDriver1] = useState<string>("");
  const [selectedDriver2, setSelectedDriver2] = useState<string>("");
  const [hoverDist, setHoverDist] = useState<number | null>(null);

  // Poll job if status is preparing
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const fetchData = (d1?: string, d2?: string) => {
    setLoading(true);
    setError(null);
    let url = `/api/charts/telemetry-compare?year=${year}&round=${round}`;
    if (d1) url += `&driver1=${encodeURIComponent(d1)}`;
    if (d2) url += `&driver2=${encodeURIComponent(d2)}`;

    fetcher<TelemetryCompareData>(url)
      .then((resData: TelemetryCompareData) => {
        setData(resData);
        setLoading(false);

        if (resData.driver1 && !selectedDriver1) setSelectedDriver1(resData.driver1);
        if (resData.driver2 && !selectedDriver2) setSelectedDriver2(resData.driver2);

        if ((resData.status === "preparing" || resData.status === "loading") && resData.job_id) {
          const jobId = resData.job_id;
          if (pollTimerRef.current) clearInterval(pollTimerRef.current);
          pollTimerRef.current = setInterval(() => {
            fetcher(`/api/charts/job/${jobId}`)
              .then((jobData: any) => {
                if (jobData.status === "ok" || jobData.status === "source_error" || jobData.status === "not_published_yet") {
                  if (pollTimerRef.current) clearInterval(pollTimerRef.current);
                  setData(jobData);
                }
              })
              .catch(() => {});
          }, 3000);
        }
      })
      .catch((err) => {
        setError(err);
        setData({ status: "source_error", coverage_note: String(err) });
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchData();
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [year, round]);

  const handleApplyDrivers = () => {
    fetchData(selectedDriver1, selectedDriver2);
  };

  const status = data?.status || (loading ? "loading" : "ok");

  if (status !== "ok" || !data?.traces) {
    return (
      <div className="p-8 border border-[var(--border)] rounded-lg bg-[var(--surface)]">
        <ChartState
          data={data}
          error={error}
          isLoading={loading}
          retry={() => fetchData(selectedDriver1, selectedDriver2)}
        >
          <div />
        </ChartState>
      </div>
    );
  }

  const traces = data.traces;
  const d1 = traces.driver1;
  const d2 = traces.driver2;
  const dist = data.distance || [];
  const maxDist = dist.length > 0 ? dist[dist.length - 1] : 5000;

  const d1Meta = data.drivers?.find((d) => d.code === d1.code) || {
    colour: "var(--accent, #3b82f6)",
    name: d1.code,
    team: "Team 1",
  };
  const d2Meta = data.drivers?.find((d) => d.code === d2.code) || {
    colour: "var(--positive, #10b981)",
    name: d2.code,
    team: "Team 2",
  };

  const c1 = d1Meta.colour || "#3b82f6";
  const c2 = d2Meta.colour || "#10b981";

  // SVG Chart dimensions
  const W = 900;
  const H_SPEED = 200;
  const H_DELTA = 90;
  const H_INPUTS = 140;
  const H_GEAR = 130;
  const m = { l: 60, r: 20, t: 15, b: 20 };

  const xScale = scaleLinear().domain([0, maxDist]).range([m.l, W - m.r]);
  const speedScale = scaleLinear().domain([60, 360]).range([H_SPEED - m.b, m.t]);
  const deltaScale = scaleLinear().domain([-30, 30]).range([H_DELTA - m.b, m.t]);
  const inputScale = scaleLinear().domain([0, 100]).range([H_INPUTS - m.b, m.t]);
  const gearScale = scaleLinear().domain([1, 8]).range([H_GEAR - m.b, m.t]);

  // Build SVG path strings
  const buildPath = (ys: number[], yScale: (v: number) => number) => {
    if (!dist.length || !ys.length) return "";
    let d = "";
    for (let i = 0; i < dist.length; i++) {
      const x = xScale(dist[i]);
      const y = yScale(ys[i] ?? 0);
      d += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
    }
    return d;
  };

  const speedPath1 = buildPath(d1.speed, speedScale);
  const speedPath2 = buildPath(d2.speed, speedScale);
  const deltaPath = buildPath(traces.speed_delta || [], deltaScale);
  const thPath1 = buildPath(d1.throttle, inputScale);
  const thPath2 = buildPath(d2.throttle, inputScale);
  const gearPath1 = buildPath(d1.gear, gearScale);
  const gearPath2 = buildPath(d2.gear, gearScale);

  // Track map SVG bounds
  const trackMap = data.track_map || [];
  const trackBounds = useMemo(() => {
    if (!trackMap.length) return { minX: 0, maxX: 100, minY: 0, maxY: 100 };
    const xs = trackMap.map((p) => p.x);
    const ys = trackMap.map((p) => p.y);
    return {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    };
  }, [trackMap]);

  const mapW = 400;
  const mapH = 340;
  const pad = 24;
  const mapXScale = scaleLinear()
    .domain([trackBounds.minX, trackBounds.maxX])
    .range([pad, mapW - pad]);
  const mapYScale = scaleLinear()
    .domain([trackBounds.minY, trackBounds.maxY])
    .range([mapH - pad, pad]); // Invert Y for cartesian coordinates

  return (
    <div className="space-y-6">
      {/* Driver Pairing Header & Controls */}
      <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)] flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          {/* Driver 1 */}
          <div className="flex items-center gap-2.5">
            <span className="w-3 h-8 rounded-sm" style={{ backgroundColor: c1 }} />
            <div>
              <div className="text-[14px] font-bold text-[var(--text)] font-mono">
                {d1.code} ({d1Meta.name})
              </div>
              <div className="text-[11px] text-[var(--text-3)] font-mono">
                {d1Meta.team} · Fastest: {data.lap_time_1 ? `${data.lap_time_1.toFixed(3)}s` : "-"}
              </div>
            </div>
          </div>

          <div className="text-[12px] font-mono text-[var(--text-3)] font-bold">VS</div>

          {/* Driver 2 */}
          <div className="flex items-center gap-2.5">
            <span className="w-3 h-8 rounded-sm" style={{ backgroundColor: c2 }} />
            <div>
              <div className="text-[14px] font-bold text-[var(--text)] font-mono">
                {d2.code} ({d2Meta.name})
              </div>
              <div className="text-[11px] text-[var(--text-3)] font-mono">
                {d2Meta.team} · Fastest: {data.lap_time_2 ? `${data.lap_time_2.toFixed(3)}s` : "-"}
              </div>
            </div>
          </div>
        </div>

        {/* Delta Chip */}
        {data.lap_delta != null && (
          <div className="px-3 py-1.5 rounded bg-[var(--surface-2)] border border-[var(--border)] font-mono text-[12px]">
            <span className="text-[var(--text-3)]">Lap Delta: </span>
            <span
              className={`font-bold ${
                data.lap_delta < 0 ? "text-[var(--positive)]" : "text-[var(--accent)]"
              }`}
            >
              {data.lap_delta > 0 ? `+${data.lap_delta.toFixed(3)}s` : `${data.lap_delta.toFixed(3)}s`}
            </span>
          </div>
        )}
      </div>

      {/* Main Layout: Telemetry Traces Stack (left) + Track Map & Proxies (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Synchronized Telemetry Stacks */}
        <div className="lg:col-span-8 space-y-4">
          {/* 1. Speed Trace */}
          <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[12px] font-mono uppercase font-bold text-[var(--text)]">
                Speed Trace (km/h)
              </span>
              <div className="flex items-center gap-4 text-[11px] font-mono">
                <span style={{ color: c1 }}>● {d1.code}</span>
                <span style={{ color: c2 }}>● {d2.code}</span>
              </div>
            </div>
            <svg
              viewBox={`0 0 ${W} ${H_SPEED}`}
              className="w-full h-auto select-none"
              role="img"
              aria-label="Speed trace overlay"
            >
              {/* Grid lines */}
              {[100, 200, 300].map((s) => (
                <g key={s}>
                  <line
                    x1={m.l}
                    x2={W - m.r}
                    y1={speedScale(s)}
                    y2={speedScale(s)}
                    stroke="var(--border)"
                    strokeWidth={0.5}
                    strokeDasharray="3 3"
                  />
                  <text
                    x={m.l - 8}
                    y={speedScale(s)}
                    fill="var(--text-3)"
                    fontSize="10"
                    textAnchor="end"
                    dominantBaseline="central"
                    fontFamily="monospace"
                  >
                    {s}
                  </text>
                </g>
              ))}
              <path d={speedPath1} fill="none" stroke={c1} strokeWidth={2} />
              <path d={speedPath2} fill="none" stroke={c2} strokeWidth={2} strokeDasharray="3 2" />
            </svg>
          </div>

          {/* 2. Speed Delta (D1 - D2) */}
          <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[12px] font-mono uppercase font-bold text-[var(--text)]">
                Speed Delta ({d1.code} − {d2.code} km/h)
              </span>
            </div>
            <svg
              viewBox={`0 0 ${W} ${H_DELTA}`}
              className="w-full h-auto select-none"
              role="img"
              aria-label="Speed delta trace"
            >
              <line
                x1={m.l}
                x2={W - m.r}
                y1={deltaScale(0)}
                y2={deltaScale(0)}
                stroke="var(--border-strong)"
                strokeWidth={1}
              />
              <path d={deltaPath} fill="none" stroke="var(--text)" strokeWidth={1.5} />
            </svg>
          </div>

          {/* 3. Throttle and Brake Inputs */}
          <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[12px] font-mono uppercase font-bold text-[var(--text)]">
                Throttle (%) & Brake Inputs
              </span>
              <div className="flex items-center gap-3 text-[11px] font-mono text-[var(--text-3)]">
                <span>Line = Throttle</span>
                <span>Bar = Full Brake</span>
              </div>
            </div>
            <svg
              viewBox={`0 0 ${W} ${H_INPUTS}`}
              className="w-full h-auto select-none"
              role="img"
              aria-label="Throttle and brake traces"
            >
              {/* Brake applications as shaded regions */}
              {dist.map((d, i) => {
                if (d1.brake[i] > 0) {
                  return (
                    <rect
                      key={`b1-${i}`}
                      x={xScale(d)}
                      y={inputScale(100)}
                      width={Math.max(1, W / dist.length)}
                      height={H_INPUTS - m.b - m.t}
                      fill={c1}
                      opacity={0.12}
                    />
                  );
                }
                return null;
              })}
              <line
                x1={m.l}
                x2={W - m.r}
                y1={inputScale(100)}
                y2={inputScale(100)}
                stroke="var(--border)"
                strokeWidth={0.5}
                strokeDasharray="2 2"
              />
              <path d={thPath1} fill="none" stroke={c1} strokeWidth={1.5} />
              <path d={thPath2} fill="none" stroke={c2} strokeWidth={1.5} strokeDasharray="3 2" />
            </svg>
          </div>

          {/* 4. Gear Selection & RPM */}
          <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[12px] font-mono uppercase font-bold text-[var(--text)]">
                Gear Selection (1-8)
              </span>
            </div>
            <svg
              viewBox={`0 0 ${W} ${H_GEAR}`}
              className="w-full h-auto select-none"
              role="img"
              aria-label="Gear selection traces"
            >
              {[2, 4, 6, 8].map((g) => (
                <g key={g}>
                  <line
                    x1={m.l}
                    x2={W - m.r}
                    y1={gearScale(g)}
                    y2={gearScale(g)}
                    stroke="var(--border)"
                    strokeWidth={0.5}
                  />
                  <text
                    x={m.l - 8}
                    y={gearScale(g)}
                    fill="var(--text-3)"
                    fontSize="10"
                    textAnchor="end"
                    dominantBaseline="central"
                    fontFamily="monospace"
                  >
                    G{g}
                  </text>
                </g>
              ))}
              <path d={gearPath1} fill="none" stroke={c1} strokeWidth={1.5} />
              <path d={gearPath2} fill="none" stroke={c2} strokeWidth={1.5} strokeDasharray="3 2" />
            </svg>
          </div>
        </div>

        {/* Right Column: Track Map, Braking Table, Proxies */}
        <div className="lg:col-span-4 space-y-4">
          {/* Track Map */}
          <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
            <h4 className="text-[12px] font-mono uppercase font-bold text-[var(--text)] mb-2">
              Track Circuit Map
            </h4>
            {trackMap.length > 0 ? (
              <svg
                viewBox={`0 0 ${mapW} ${mapH}`}
                className="w-full h-auto select-none"
                role="img"
                aria-label="Track layout map"
              >
                {trackMap.map((pt, i) => {
                  if (i === 0) return null;
                  const prev = trackMap[i - 1];
                  const color = pt.delta_speed > 2 ? c1 : pt.delta_speed < -2 ? c2 : "var(--border-strong)";
                  return (
                    <line
                      key={i}
                      x1={mapXScale(prev.x)}
                      y1={mapYScale(prev.y)}
                      x2={mapXScale(pt.x)}
                      y2={mapYScale(pt.y)}
                      stroke={color}
                      strokeWidth={3}
                      strokeLinecap="round"
                    />
                  );
                })}
              </svg>
            ) : (
              <div className="h-48 flex items-center justify-center text-[11px] font-mono text-[var(--text-3)]">
                Track map coordinates unavailable for this session.
              </div>
            )}
          </div>

          {/* Aerodynamic & Chassis Proxies */}
          {data.proxies && (
            <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)] space-y-3">
              <h4 className="text-[12px] font-mono uppercase font-bold text-[var(--text)]">
                Engineering Proxies
              </h4>
              {Object.entries(data.proxies).map(([k, p]: [string, any]) => (
                <div key={k} className="p-2.5 rounded bg-[var(--surface-2)] border border-[var(--border)] text-[11px] font-mono space-y-1">
                  <div className="text-[var(--text-3)] uppercase font-semibold">{p.proxy || k}</div>
                  <div className="flex items-center justify-between text-[12px]">
                    <span style={{ color: c1 }}>
                      {d1.code}: {p[d1.code]} {p.unit}
                    </span>
                    <span style={{ color: c2 }}>
                      {d2.code}: {p[d2.code]} {p.unit}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Braking Zones Table */}
          {data.braking_table && data.braking_table.length > 0 && (
            <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
              <h4 className="text-[12px] font-mono uppercase font-bold text-[var(--text)] mb-2">
                Braking Zones Analysis
              </h4>
              <div className="overflow-x-auto max-h-64 overflow-y-auto">
                <table className="w-full text-[11px] font-mono border-collapse">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-[var(--text-3)] text-left">
                      <th className="py-1">Zone</th>
                      <th className="py-1">Entry</th>
                      <th className="py-1">Min</th>
                      <th className="py-1">Decel</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {data.braking_table.map((z) => (
                      <tr key={z.zone} className="hover:bg-[var(--surface-2)]">
                        <td className="py-1 text-[var(--text)] font-bold">Z{z.zone}</td>
                        <td className="py-1">{z.entry_speed_kmh}k</td>
                        <td className="py-1">{z.min_speed_kmh}k</td>
                        <td className="py-1 text-[var(--accent)] font-semibold">{z.decel_g}g</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
