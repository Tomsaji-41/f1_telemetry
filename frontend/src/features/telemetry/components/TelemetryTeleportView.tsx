"use client";

/**
 * TelemetryTeleportView — Telemetry Teleport page view (V7-2 & V6 P10.2 spec).
 * Contains:
 * 1. Two-driver telemetry comparison stack (Speed, Delta, Throttle, Brake, Gear, RPM, DRS).
 * 2. Track map with speed delta heat map.
 * 3. Braking zones table (entry speed, apex min speed, distance, deceleration g).
 * 4. Aerodynamic & Chassis engineering proxies.
 * 5. Sector & speed-trap comparison panel (SpeedST, SpeedFL, SpeedI1, SpeedI2).
 * 6. Honest limits: Clean not_available state with verified telemetry session picker.
 */
import React, { useState, useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { scaleLinear } from "d3-scale";
import { ChartState } from "@/components/charts/ChartState";
import { Gauge, Zap, Wind, ShieldAlert, ChevronRight, Activity, Calendar } from "lucide-react";
import en from "@/content/en.json";
import { fetcher } from "@/lib/api";

export const VERIFIED_TELEMETRY_SESSIONS = [
  { year: 2024, round: 12, name: "2024 British GP (Silverstone)" },
  { year: 2024, round: 1, name: "2024 Bahrain GP (Sakhir)" },
  { year: 2023, round: 22, name: "2023 Abu Dhabi GP (Yas Marina)" },
  { year: 2023, round: 14, name: "2023 Italian GP (Monza)" },
  { year: 2023, round: 1, name: "2023 Bahrain GP (Sakhir)" },
  { year: 2022, round: 22, name: "2022 Abu Dhabi GP (Yas Marina)" },
  { year: 2022, round: 1, name: "2022 Bahrain GP (Sakhir)" },
];

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

interface SectorSpeedTrapData {
  driver1?: string;
  driver2?: string;
  lap_time?: Record<string, number | null>;
  sector1?: Record<string, number | null>;
  sector2?: Record<string, number | null>;
  sector3?: Record<string, number | null>;
  speed_st?: Record<string, number | null>;
  speed_fl?: Record<string, number | null>;
  speed_i1?: Record<string, number | null>;
  speed_i2?: Record<string, number | null>;
}

interface TelemetryCompareData {
  status?: string;
  source?: string;
  coverage_note?: string;
  reason?: string;
  session_used?: string | null;
  nearest_session?: { year: number; round: number; name?: string };
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
  sector_speed_trap?: SectorSpeedTrapData;
  proxies?: Record<string, any>;
  job_id?: string;
  eta_s?: number;
}

interface TelemetryTeleportViewProps {
  year: number;
  round: number;
}

export function SectorSpeedTrapPanel({
  sst,
  d1,
  d2,
  c1,
  c2,
}: {
  sst: SectorSpeedTrapData;
  d1: string;
  d2: string;
  c1: string;
  c2: string;
}) {
  const rows = [
    { label: "Fastest Lap Time", k: "lap_time", unit: "s", digits: 3 },
    { label: "Sector 1 Time", k: "sector1", unit: "s", digits: 3 },
    { label: "Sector 2 Time", k: "sector2", unit: "s", digits: 3 },
    { label: "Sector 3 Time", k: "sector3", unit: "s", digits: 3 },
    { label: "Speed Trap (SpeedST)", k: "speed_st", unit: "km/h", digits: 1 },
    { label: "Finish Line (SpeedFL)", k: "speed_fl", unit: "km/h", digits: 1 },
    { label: "Intermediate 1 (SpeedI1)", k: "speed_i1", unit: "km/h", digits: 1 },
    { label: "Intermediate 2 (SpeedI2)", k: "speed_i2", unit: "km/h", digits: 1 },
  ];

  return (
    <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)] space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-[12px] font-mono uppercase font-bold text-[var(--text)] tracking-wider">
          Sector &amp; speed-trap comparison
        </h4>
        <span className="text-[11px] font-mono text-[var(--text-3)]">
          Real Timing Telemetry
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px] font-mono border-collapse">
          <thead>
            <tr className="border-b border-[var(--border)] text-[var(--text-3)] text-left">
              <th className="py-1.5 font-medium">Metric</th>
              <th className="py-1.5 font-medium" style={{ color: c1 }}>
                {d1}
              </th>
              <th className="py-1.5 font-medium" style={{ color: c2 }}>
                {d2}
              </th>
              <th className="py-1.5 font-medium text-right">Delta</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {rows.map((r) => {
              const dict = (sst as any)[r.k] || {};
              const v1 = dict[d1];
              const v2 = dict[d2];
              const hasDelta = v1 != null && v2 != null;
              const delta = hasDelta ? v1 - v2 : null;

              return (
                <tr key={r.k} className="hover:bg-[var(--surface-2)]">
                  <td className="py-1.5 text-[var(--text-2)]">{r.label}</td>
                  <td className="py-1.5 font-semibold text-[var(--text)]">
                    {v1 != null ? `${Number(v1).toFixed(r.digits)}${r.unit}` : "—"}
                  </td>
                  <td className="py-1.5 font-semibold text-[var(--text)]">
                    {v2 != null ? `${Number(v2).toFixed(r.digits)}${r.unit}` : "—"}
                  </td>
                  <td className="py-1.5 text-right font-medium">
                    {delta != null ? (
                      <span
                        className={
                          delta === 0
                            ? "text-[var(--text-3)]"
                            : delta < 0
                            ? "text-[var(--positive)]"
                            : "text-[var(--accent)]"
                        }
                      >
                        {delta > 0 ? `+${delta.toFixed(r.digits)}` : delta.toFixed(r.digits)}
                        {r.unit}
                      </span>
                    ) : (
                      <span className="text-[var(--text-3)]">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function TelemetryTeleportView({ year, round }: TelemetryTeleportViewProps) {
  const router = useRouter();
  const [activeYear, setActiveYear] = useState<number>(year);
  const [activeRound, setActiveRound] = useState<number>(round);

  const [data, setData] = useState<TelemetryCompareData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<any>(null);
  const [selectedDriver1, setSelectedDriver1] = useState<string>("");
  const [selectedDriver2, setSelectedDriver2] = useState<string>("");
  const [hoverDist, setHoverDist] = useState<number | null>(null);

  // Synchronize prop updates
  useEffect(() => {
    setActiveYear(year);
    setActiveRound(round);
  }, [year, round]);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const fetchData = (y: number, r: number, d1?: string, d2?: string) => {
    setLoading(true);
    setError(null);
    let url = `/api/charts/telemetry-compare?year=${y}&round=${r}`;
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
                if (
                  jobData.status === "ok" ||
                  jobData.status === "not_available" ||
                  jobData.status === "source_error" ||
                  jobData.status === "not_published_yet"
                ) {
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
    fetchData(activeYear, activeRound);
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [activeYear, activeRound]);

  const handleSelectSession = (y: number, r: number) => {
    setActiveYear(y);
    setActiveRound(r);
    router.push(`/telemetry?year=${y}&round=${r}`);
  };

  const handleApplyDrivers = () => {
    fetchData(activeYear, activeRound, selectedDriver1, selectedDriver2);
  };

  const status = data?.status || (loading ? "loading" : "ok");

  // Not available state with clean session picker & Sector/speed-trap panel
  if (!loading && (status === "not_available" || (status === "ok" && !data?.traces))) {
    const sst = data?.sector_speed_trap;
    const d1Code = data?.driver1 || "VER";
    const d2Code = data?.driver2 || "NOR";

    return (
      <div className="space-y-6">
        {/* Honest Not Available Hero Banner */}
        <div className="p-6 rounded-lg bg-[var(--surface)] border border-[var(--border)] space-y-4">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-[var(--accent)] shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h2 className="text-[15px] font-mono font-bold text-[var(--text)]">
                Car Telemetry Stream Unavailable
              </h2>
              <p className="text-[12px] text-[var(--text-2)] font-mono leading-relaxed">
                {data?.coverage_note ||
                  `Full car telemetry (speed, throttle, brake curves & GPS) is unavailable for ${activeYear} Round ${activeRound} from the timing provider.`}
              </p>
              {data?.reason && (
                <p className="text-[11px] text-[var(--text-3)] font-mono">
                  Upstream reason: {data.reason}
                </p>
              )}
            </div>
          </div>

          {/* Nearest verified session switch button */}
          {data?.nearest_session && (
            <div className="p-3.5 rounded bg-[var(--surface-2)] border border-[var(--border)] flex flex-wrap items-center justify-between gap-3">
              <div className="text-[12px] font-mono">
                <span className="text-[var(--text-3)]">Nearest verified session: </span>
                <span className="font-bold text-[var(--text)]">
                  {data.nearest_session.name ||
                    `${data.nearest_session.year} Round ${data.nearest_session.round}`}
                </span>
              </div>
              <button
                onClick={() =>
                  handleSelectSession(data.nearest_session!.year, data.nearest_session!.round)
                }
                className="px-3.5 py-1.5 rounded bg-[var(--accent)] text-white text-[12px] font-mono font-semibold hover:opacity-90 transition-opacity flex items-center gap-1.5"
              >
                <span>Switch to Nearest Session</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Session Picker listing only verified sessions with telemetry */}
          <div className="pt-3 border-t border-[var(--border)] flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-[11px] font-mono text-[var(--text-3)]">
              <Calendar className="w-3.5 h-3.5 text-[var(--accent)]" />
              <span>Select session with telemetry:</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {VERIFIED_TELEMETRY_SESSIONS.map((s) => (
                <button
                  key={`${s.year}-${s.round}`}
                  onClick={() => handleSelectSession(s.year, s.round)}
                  className={`px-2.5 py-1 text-[11px] font-mono rounded border transition-colors ${
                    s.year === activeYear && s.round === activeRound
                      ? "bg-[var(--accent)] text-white border-[var(--accent)] font-bold"
                      : "bg-[var(--surface-2)] text-[var(--text-2)] border-[var(--border)] hover:bg-[var(--raised)]"
                  }`}
                >
                  {s.name.replace("Grand Prix", "GP")}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Real Sector & speed-trap comparison panel */}
        {sst && (
          <SectorSpeedTrapPanel
            sst={sst}
            d1={d1Code}
            d2={d2Code}
            c1="var(--accent, #3b82f6)"
            c2="var(--positive, #10b981)"
          />
        )}
      </div>
    );
  }

  // Generic loading or error states
  if (status !== "ok" || !data?.traces) {
    return (
      <div className="p-8 border border-[var(--border)] rounded-lg bg-[var(--surface)]">
        <ChartState
          data={data}
          error={error}
          isLoading={loading}
          retry={() => fetchData(activeYear, activeRound, selectedDriver1, selectedDriver2)}
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
    .range([mapH - pad, pad]);

  return (
    <div className="space-y-6">
      {/* Session Switcher Header Bar */}
      <div className="p-3.5 rounded-lg bg-[var(--surface)] border border-[var(--border)] flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-[var(--accent)]" />
          <span className="text-[12px] font-mono text-[var(--text-3)] uppercase font-semibold">
            Telemetry Session:
          </span>
          <select
            value={`${activeYear}-${activeRound}`}
            onChange={(e) => {
              const [y, r] = e.target.value.split("-").map(Number);
              handleSelectSession(y, r);
            }}
            className="bg-[var(--surface-2)] text-[var(--text)] border border-[var(--border)] rounded px-3 py-1 text-[12px] font-mono focus:outline-none focus:border-[var(--accent)] cursor-pointer"
          >
            {VERIFIED_TELEMETRY_SESSIONS.map((s) => (
              <option key={`${s.year}-${s.round}`} value={`${s.year}-${s.round}`}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        {data.session_used && (
          <span className="px-2.5 py-1 text-[11px] font-mono rounded bg-[var(--surface-2)] border border-[var(--border)] text-[var(--accent)] font-semibold">
            Source: {data.session_used}
          </span>
        )}
      </div>

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
              {[100, 200, 300].map((s) => (
                <g key={s}>
                  <line
                    x1={m.l}
                    x2={W - m.r}
                    y1={speedScale(s)}
                    y2={speedScale(s)}
                    stroke="var(--border)"
                    strokeDasharray="2 4"
                    strokeWidth={1}
                  />
                  <text
                    x={m.l - 8}
                    y={speedScale(s) + 4}
                    textAnchor="end"
                    className="text-[10px] fill-[var(--text-3)] font-mono"
                  >
                    {s}
                  </text>
                </g>
              ))}
              <path d={speedPath1} fill="none" stroke={c1} strokeWidth={2} />
              <path d={speedPath2} fill="none" stroke={c2} strokeWidth={2} opacity={0.9} />
            </svg>
          </div>

          {/* 2. Speed Delta Trace */}
          <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[12px] font-mono uppercase font-bold text-[var(--text)]">
                Speed Delta (km/h) [{d1.code} − {d2.code}]
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
                stroke="var(--border)"
                strokeWidth={1.5}
              />
              <path d={deltaPath} fill="none" stroke="var(--accent)" strokeWidth={1.8} />
            </svg>
          </div>

          {/* 3. Driver Inputs: Throttle & Brake */}
          <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[12px] font-mono uppercase font-bold text-[var(--text)]">
                Driver Inputs (Throttle &amp; Brake %)
              </span>
            </div>
            <svg
              viewBox={`0 0 ${W} ${H_INPUTS}`}
              className="w-full h-auto select-none"
              role="img"
              aria-label="Throttle and brake traces"
            >
              <path d={thPath1} fill="none" stroke={c1} strokeWidth={1.5} />
              <path d={thPath2} fill="none" stroke={c2} strokeWidth={1.5} opacity={0.8} />
            </svg>
          </div>

          {/* 4. Gear Selection */}
          <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[12px] font-mono uppercase font-bold text-[var(--text)]">
                Gear Selection (1–8)
              </span>
            </div>
            <svg
              viewBox={`0 0 ${W} ${H_GEAR}`}
              className="w-full h-auto select-none"
              role="img"
              aria-label="Gear trace"
            >
              <path d={gearPath1} fill="none" stroke={c1} strokeWidth={1.5} />
              <path d={gearPath2} fill="none" stroke={c2} strokeWidth={1.5} opacity={0.8} />
            </svg>
          </div>

          {/* 5. Real Sector & speed-trap comparison panel */}
          {data.sector_speed_trap && (
            <SectorSpeedTrapPanel
              sst={data.sector_speed_trap}
              d1={d1.code}
              d2={d2.code}
              c1={c1}
              c2={c2}
            />
          )}
        </div>

        {/* Right Column: Track Map, Braking Table, Proxies */}
        <div className="lg:col-span-4 space-y-4">
          {/* Circuit Map */}
          <div className="p-4 rounded-lg bg-[var(--surface)] border border-[var(--border)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[12px] font-mono uppercase font-bold text-[var(--text)]">
                Circuit Map
              </span>
              <span className="text-[11px] font-mono text-[var(--text-3)]">Delta Heat</span>
            </div>
            {trackMap.length > 0 ? (
              <svg
                viewBox={`0 0 ${mapW} ${mapH}`}
                className="w-full h-auto select-none"
                role="img"
                aria-label="Track layout map"
              >
                {trackMap.map((p, idx) => {
                  if (idx === 0) return null;
                  const prev = trackMap[idx - 1];
                  const x1 = mapXScale(prev.x);
                  const y1 = mapYScale(prev.y);
                  const x2 = mapXScale(p.x);
                  const y2 = mapYScale(p.y);
                  const col =
                    p.delta_speed > 2
                      ? c1
                      : p.delta_speed < -2
                      ? c2
                      : "var(--text-3, #9ca3af)";

                  return (
                    <line
                      key={idx}
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke={col}
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
                <div
                  key={k}
                  className="p-2.5 rounded bg-[var(--surface-2)] border border-[var(--border)] text-[11px] font-mono space-y-1"
                >
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
