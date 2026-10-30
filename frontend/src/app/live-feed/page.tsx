"use client";

import React, { useState, useEffect, useMemo, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  Radio,
  Play,
  Pause,
  SkipBack,
  SkipForward,
} from "lucide-react";
import { Panel, Stat } from "@/components/primitives/kit";
import { fetcher } from "@/lib/api";

interface ReplayLeaderboardRow {
  pos: number;
  driver: string;
  code: string;
  team: string;
  team_color: string;
  gap?: string;
  interval?: string;
  compound?: string;
  tyre_life?: number;
  last_lap?: string;
  is_pit?: boolean;
}

interface ReplayWeather {
  air_temp?: string;
  track_temp?: string;
  humidity?: string;
  wind_speed?: string;
  rainfall?: boolean;
  weather_note?: string;
}

interface LapData {
  lap: number;
  track_status: string;
  weather?: ReplayWeather | null;
  leaderboard: ReplayLeaderboardRow[];
}

interface ReplayBundle {
  status: string;
  source: string;
  coverage_note?: string;
  is_partial?: boolean;
  loaded_laps?: number;
  year: number;
  round: number;
  grand_prix: string;
  circuit_name: string;
  total_laps: number;
  drivers: Record<string, { code: string; name: string; team: string; team_color: string; number?: string; dash?: string }>;
  pit_events: Array<{ driver: string; code: string; lap: number; stop: number; duration: string }>;
  laps: Record<string | number, LapData>;
  chart_data: {
    laps: number[];
    positions: Record<string, number[]>;
    lap_times: Record<string, (number | null)[]>;
  };
}

function LiveFeedContent(): React.JSX.Element {
  const searchParams = useSearchParams();
  const yearParam = searchParams.get("year");
  const roundParam = searchParams.get("round");
  const sessionParam = searchParams.get("session") || "R";
  const year = yearParam ? parseInt(yearParam, 10) : undefined;
  const round = roundParam ? parseInt(roundParam, 10) : undefined;

  const [isLive, setIsLive] = useState<boolean>(false);
  const [currentLap, setCurrentLap] = useState<number>(1);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [bundle, setBundle] = useState<ReplayBundle | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [chartMetric, setChartMetric] = useState<"positions" | "lap_times">("positions");

  // Chart container ref for responsive sizing
  const chartSvgRef = useRef<SVGSVGElement>(null);
  const [chartWidth, setChartWidth] = useState<number>(800);

  useEffect(() => {
    function handleResize() {
      if (chartSvgRef.current) {
        setChartWidth(chartSvgRef.current.clientWidth || 800);
      }
    }
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [bundle]);

  // Session fetch: abort in-flight on change, reset scrubbing
  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function initFeed() {
      setLoading(true);
      setError(null);
      setBundle(null);
      setCurrentLap(1);
      setIsPlaying(false);

      try {
        const statusRes = await fetcher<{ status: string; is_live: boolean; mode: string }>("/api/live/status").catch(() => null);
        if (!mounted || controller.signal.aborted) return;

        if (!year && !round && statusRes && statusRes.is_live) {
          setIsLive(true);
          setLoading(false);
        } else {
          setIsLive(false);
          const q = new URLSearchParams();
          if (year) q.set("year", String(year));
          if (round) q.set("round", String(round));
          if (sessionParam) q.set("session", sessionParam);
          const qs = q.toString();
          const bundleUrl = qs ? `/api/replay/bundle?${qs}` : "/api/replay/bundle";

          const replayRes = await fetcher<ReplayBundle>(bundleUrl).catch((err) => {
            throw new Error(`Failed to load session replay: ${err.message || err}`);
          });

          if (!mounted || controller.signal.aborted) return;

          if (replayRes && (replayRes.status === "ok" || replayRes.status === "partial")) {
            setBundle(replayRes);
            setCurrentLap(1);
          } else {
            setError((replayRes as any)?.reason || "Replay telemetry data not available for this session.");
          }
          setLoading(false);
        }
      } catch (err: any) {
        if (mounted && !controller.signal.aborted) {
          setError(err?.message || "Failed to initialize telemetry feed.");
          setLoading(false);
        }
      }
    }

    initFeed();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [year, round, sessionParam]);

  const totalLaps = bundle?.total_laps || 1;
  const isPartial = Boolean(bundle?.is_partial || bundle?.status === "partial");
  const maxAvailableLap = useMemo(() => {
    if (!bundle) return 1;
    if (bundle.loaded_laps && bundle.loaded_laps > 0) return bundle.loaded_laps;
    const lapKeys = Object.keys(bundle.laps || {}).map(Number).filter((n) => !isNaN(n));
    return lapKeys.length > 0 ? Math.max(...lapKeys) : totalLaps;
  }, [bundle, totalLaps]);

  // Playback loop in memory (zero network requests)
  useEffect(() => {
    if (!isPlaying || isLive || !bundle) return;
    const maxLap = isPartial ? maxAvailableLap : totalLaps;
    const interval = setInterval(() => {
      setCurrentLap((prev) => {
        if (prev >= maxLap) {
          setIsPlaying(false);
          return maxLap;
        }
        return prev + 1;
      });
    }, 1200);
    return () => clearInterval(interval);
  }, [isPlaying, isLive, bundle, isPartial, maxAvailableLap, totalLaps]);

  const currentLapData = useMemo(() => {
    if (!bundle || !bundle.laps) return null;
    return bundle.laps[currentLap] || bundle.laps[String(currentLap)] || null;
  }, [bundle, currentLap]);

  const leaderboard = currentLapData?.leaderboard || [];
  const rawTrackStatus = currentLapData?.track_status || (isLive ? "GREEN" : (isPartial || currentLap < totalLaps ? "GREEN" : "CHEQUERED"));
  const trackStatus = (rawTrackStatus === "CHEQUERED" && (isPartial || currentLap < totalLaps)) ? "GREEN" : rawTrackStatus;
  const weather = currentLapData?.weather || null;

  // Track status badges
  const trackStatusDisplay = useMemo(() => {
    switch (trackStatus) {
      case "GREEN":
        return { label: "GREEN FLAG", color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" };
      case "YELLOW":
        return { label: "YELLOW FLAG", color: "bg-amber-500/15 text-amber-400 border-amber-500/30" };
      case "SC":
        return { label: "SAFETY CAR", color: "bg-amber-500/25 text-amber-300 border-amber-500/50" };
      case "VSC":
        return { label: "VIRTUAL SC", color: "bg-indigo-500/20 text-indigo-300 border-indigo-500/40" };
      case "RED":
        return { label: "RED FLAG", color: "bg-red-500/25 text-red-400 border-red-500/50" };
      case "CHEQUERED":
        return { label: "CHEQUERED FLAG", color: "bg-zinc-500/20 text-zinc-200 border-zinc-500/40" };
      default:
        return { label: trackStatus, color: "bg-zinc-500/20 text-zinc-300 border-zinc-500/30" };
    }
  }, [trackStatus]);

  // Tyre compound styling
  function getCompoundBadge(compound?: string) {
    const comp = (compound || "MEDIUM").toUpperCase();
    let bg = "bg-yellow-500/20 text-yellow-400 border-yellow-500/40";
    let letter = "M";
    if (comp.includes("SOFT")) {
      bg = "bg-red-500/20 text-red-400 border-red-500/40";
      letter = "S";
    } else if (comp.includes("HARD")) {
      bg = "bg-zinc-200/20 text-zinc-100 border-zinc-200/40";
      letter = "H";
    } else if (comp.includes("INTER")) {
      bg = "bg-emerald-500/20 text-emerald-400 border-emerald-500/40";
      letter = "I";
    } else if (comp.includes("WET")) {
      bg = "bg-blue-500/20 text-blue-400 border-blue-500/40";
      letter = "W";
    }
    return { bg, letter, full: comp };
  }

  // Scrub via clicking chart
  const handleChartClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!bundle || totalLaps <= 1) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const paddingLeft = 45;
    const paddingRight = 45;
    const chartAreaWidth = Math.max(1, rect.width - paddingLeft - paddingRight);
    const relX = Math.max(0, Math.min(chartAreaWidth, clickX - paddingLeft));
    const targetLap = Math.max(1, Math.min(totalLaps, Math.round(1 + (relX / chartAreaWidth) * (totalLaps - 1))));
    setCurrentLap(targetLap);
    setIsPlaying(false);
  };

  const raceTitle = bundle ? `${bundle.grand_prix} ${bundle.year}` : "Grand Prix Session";

  return (
    <div className="space-y-6">
      {/* Top Session Control Banner */}
      <section className="p-5 border border-[var(--border)] rounded-lg bg-[var(--surface)]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span
                className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-mono font-bold uppercase tracking-wider ${
                  isLive
                    ? "bg-red-500/15 text-red-400 border border-red-500/30 animate-pulse"
                    : "bg-blue-500/15 text-blue-400 border border-blue-500/30"
                }`}
              >
                <Radio className="w-3 h-3" />
                <span>{isLive ? "LIVE SESSION" : "REPLAY MODE"}</span>
              </span>
              <span className="text-[var(--text-3)] text-xs">•</span>
              <span className="text-[12px] font-mono text-[var(--text-3)]">
                {raceTitle}
              </span>
              {bundle?.circuit_name && (
                <>
                  <span className="text-[var(--text-3)] text-xs">•</span>
                  <span className="text-[12px] font-mono text-[var(--text-2)]">{bundle.circuit_name}</span>
                </>
              )}
            </div>
            <h1 className="text-[24px] font-semibold text-[var(--text)] tracking-tight mt-1">
              {isLive
                ? "OpenF1 Live Timing Feed"
                : isPartial
                ? `Session Replay: Lap ${currentLap} of ${maxAvailableLap} (Partial • Official: ${totalLaps} Laps)`
                : `Session Replay: Lap ${currentLap} of ${totalLaps}`}
            </h1>
          </div>

          {/* Interactive Lap Scrubber Controls (in Replay Mode) */}
          {!isLive && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setCurrentLap(1);
                  setIsPlaying(false);
                }}
                className="p-2 border border-[var(--border)] rounded bg-[var(--raised)] text-[var(--text-2)] hover:text-[var(--text)] transition-colors"
                title="Restart from Lap 1"
              >
                <SkipBack className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setIsPlaying(!isPlaying)}
                className="flex items-center gap-1.5 px-3 py-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-xs font-mono font-bold rounded transition-colors"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                <span>{isPlaying ? "PAUSE" : "PLAY"}</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setCurrentLap(maxAvailableLap);
                  setIsPlaying(false);
                }}
                className="p-2 border border-[var(--border)] rounded bg-[var(--raised)] text-[var(--text-2)] hover:text-[var(--text)] transition-colors"
                title="Jump to Latest Recorded Lap"
              >
                <SkipForward className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* Scrubber slider */}
        {!isLive && (
          <div className="mt-4 pt-3 border-t border-[var(--border)]">
            <div className="flex justify-between items-center text-[11px] font-mono text-[var(--text-3)] mb-1">
              <span>Lap 1</span>
              <span className="font-bold text-[var(--accent)]">
                Selected: Lap {currentLap} ({Math.round((currentLap / maxAvailableLap) * 100)}%)
              </span>
              <span>Lap {maxAvailableLap} {isPartial ? `(Latest Recorded — Official: ${totalLaps})` : "(Finish)"}</span>
            </div>
            <input
              type="range"
              min={1}
              max={maxAvailableLap}
              value={currentLap}
              onChange={(e) => {
                setCurrentLap(parseInt(e.target.value, 10));
                setIsPlaying(false);
              }}
              className="w-full accent-[var(--accent)] cursor-pointer"
            />
          </div>
        )}
      </section>

      {/* Partial Session Banner */}
      {isPartial && (
        <div className="p-3 border border-amber-500/30 rounded-lg bg-amber-500/10 text-amber-300 text-xs font-mono flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-bold">⚠ PARTIAL DATA:</span>
            <span>{bundle?.coverage_note || `Partial data: ${bundle?.loaded_laps || Object.keys(bundle?.laps || {}).length} of ${totalLaps} laps`}</span>
          </div>
          <span className="text-[11px] text-amber-400/80">Race in progress or timing discontinued</span>
        </div>
      )}

      {/* Environmental Strip (Honest real data, no fake placeholders) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Stat
          label="Track Air Temp"
          value={weather?.air_temp || "N/A"}
          delta={weather?.air_temp ? "Ambient Air" : (weather?.weather_note || "Weather not recorded for this session")}
          deltaType="neutral"
        />
        <Stat
          label="Track Surface"
          value={weather?.track_temp || "N/A"}
          delta={weather?.track_temp ? "Asphalt Temp" : (weather?.weather_note || "Weather not recorded for this session")}
          deltaType="neutral"
        />
        <Stat
          label="Humidity / Wind"
          value={weather?.humidity ? `${weather.humidity} • ${weather.wind_speed || ""}` : "N/A"}
          delta={weather?.rainfall ? "Rain Active" : (weather?.weather_note ? "Condition Unrecorded" : "Track Condition")}
          deltaType={weather?.rainfall ? "negative" : "neutral"}
        />
        <Stat
          label="Session Status"
          value={trackStatusDisplay.label}
          delta={isLive ? "Live Session" : `Lap ${currentLap}`}
          deltaType={trackStatus === "GREEN" ? "positive" : trackStatus === "RED" ? "negative" : "neutral"}
        />
      </div>

      {loading && (
        <div className="p-8 text-center text-sm font-mono text-[var(--text-3)] border border-[var(--border)] rounded-lg bg-[var(--surface)]">
          Loading verified session telemetry bundle...
        </div>
      )}

      {error && (
        <div className="p-4 border border-red-500/30 rounded-lg bg-red-500/10 text-red-400 text-xs font-mono">
          {error}
        </div>
      )}

      {/* Timing Leaderboard */}
      {!loading && !error && (
        <section>
          <Panel
            title="Session Classification"
            subtitle={
              isPartial
                ? `Driver intervals at recorded Lap ${currentLap} of ${maxAvailableLap} (Official race distance: ${totalLaps} laps)`
                : `Verified driver intervals and tyre stint pace at Lap ${currentLap} of ${totalLaps}`
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead className="border-b border-[var(--border)] text-[var(--text-3)]">
                  <tr>
                    <th className="py-2.5 px-3 text-left">Pos</th>
                    <th className="py-2.5 px-3 text-left">Driver</th>
                    <th className="py-2.5 px-3 text-left">Constructor</th>
                    <th className="py-2.5 px-3 text-right">Gap to Leader</th>
                    <th className="py-2.5 px-3 text-right">Interval</th>
                    <th className="py-2.5 px-3 text-center">Tyre Compound</th>
                    <th className="py-2.5 px-3 text-right">Tyre Age</th>
                    <th className="py-2.5 px-3 text-right">Last Lap</th>
                    <th className="py-2.5 px-3 text-center">Pit</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {leaderboard.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="py-6 text-center text-[var(--text-3)]">
                        No telemetry timing recorded for Lap {currentLap}.
                      </td>
                    </tr>
                  ) : (
                    leaderboard.map((row) => {
                      const compBadge = getCompoundBadge(row.compound);
                      return (
                        <tr
                          key={row.code}
                          className="hover:bg-[var(--raised)]/50 transition-colors"
                        >
                          <td className="py-2 px-3 font-bold text-[var(--text)]">
                            P{row.pos}
                          </td>
                          <td className="py-2 px-3 font-sans font-semibold text-[var(--text)]">
                            <div className="flex items-center gap-2">
                              <span
                                className="w-1.5 h-4 rounded-full shrink-0"
                                style={{ backgroundColor: row.team_color }}
                              />
                              <span className="font-mono text-xs font-bold px-1 rounded bg-[var(--raised)] text-[var(--text)]">
                                {row.code}
                              </span>
                              <span className="truncate">{row.driver}</span>
                            </div>
                          </td>
                          <td className="py-2 px-3 font-sans text-[var(--text-2)]">
                            {row.team}
                          </td>
                          <td className="py-2 px-3 text-right text-[var(--accent)] font-semibold">
                            {row.gap || (row.pos === 1 ? "LEADER" : "-")}
                          </td>
                          <td className="py-2 px-3 text-right text-[var(--text-2)]">
                            {row.interval || "-"}
                          </td>
                          <td className="py-2 px-3 text-center">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border ${compBadge.bg}`}>
                              <span className="w-2 h-2 rounded-full bg-current" />
                              {compBadge.full}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right text-[var(--text-3)]">
                            {row.tyre_life ? `${row.tyre_life} L` : "-"}
                          </td>
                          <td className="py-2 px-3 text-right text-[var(--text-2)] font-mono">
                            {row.last_lap || "-"}
                          </td>
                          <td className="py-2 px-3 text-center">
                            {row.is_pit ? (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
                                PIT
                              </span>
                            ) : (
                              <span className="text-[var(--text-3)]">-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </Panel>
        </section>
      )}

      {/* 5.5 Lap-by-Lap Synchronized Chart Panel */}
      {bundle && bundle.chart_data && (
        <section>
          <Panel
            title="Synchronized Race Progression"
            subtitle="Click or drag anywhere on the chart to scrub the session in real-time"
          >
            <div className="flex items-center justify-between gap-4 mb-3 pb-2 border-b border-[var(--border)]">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setChartMetric("positions")}
                  className={`px-3 py-1 rounded text-xs font-mono font-semibold border transition-colors ${
                    chartMetric === "positions"
                      ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                      : "bg-[var(--raised)] text-[var(--text-2)] border-[var(--border)] hover:text-[var(--text)]"
                  }`}
                >
                  Position Progression
                </button>
                <button
                  type="button"
                  onClick={() => setChartMetric("lap_times")}
                  className={`px-3 py-1 rounded text-xs font-mono font-semibold border transition-colors ${
                    chartMetric === "lap_times"
                      ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                      : "bg-[var(--raised)] text-[var(--text-2)] border-[var(--border)] hover:text-[var(--text)]"
                  }`}
                >
                  Lap Times (Pace)
                </button>
              </div>
              <span className="text-[11px] font-mono text-[var(--text-3)]">
                Active Cursor: Lap {currentLap}
              </span>
            </div>

            {/* Interactive SVG Chart */}
            <div className="relative w-full h-[280px]">
              <svg
                ref={chartSvgRef}
                className="w-full h-full cursor-crosshair select-none"
                onClick={handleChartClick}
                aria-label="Synchronized session progression chart"
              >
                {/* Background grid */}
                <rect x="45" y="15" width={Math.max(10, chartWidth - 90)} height="230" fill="transparent" />

                {/* Vertical Cursor for Current Lap */}
                {(() => {
                  const paddingLeft = 45;
                  const paddingRight = 45;
                  const innerWidth = Math.max(1, chartWidth - paddingLeft - paddingRight);
                  const cursorX = totalLaps > 1 ? paddingLeft + ((currentLap - 1) / (totalLaps - 1)) * innerWidth : paddingLeft;
                  return (
                    <g>
                      <line
                        x1={cursorX}
                        y1="15"
                        x2={cursorX}
                        y2="245"
                        stroke="var(--accent)"
                        strokeWidth="2"
                        strokeDasharray="4 2"
                      />
                      <rect
                        x={cursorX - 25}
                        y="2"
                        width="50"
                        height="14"
                        rx="3"
                        fill="var(--accent)"
                      />
                      <text
                        x={cursorX}
                        y="12"
                        textAnchor="middle"
                        fill="#FFFFFF"
                        fontSize="9"
                        fontFamily="monospace"
                        fontWeight="bold"
                      >
                        L{currentLap}
                      </text>
                    </g>
                  );
                })()}

                {/* Chart series */}
                {(() => {
                  const paddingLeft = 45;
                  const paddingRight = 45;
                  const paddingTop = 25;
                  const chartHeight = 220;
                  const innerWidth = Math.max(1, chartWidth - paddingLeft - paddingRight);

                  // Extract top 10 driver codes to keep visualization readable
                  const driverCodes = Object.keys(bundle.chart_data.positions).slice(0, 10);

                  return driverCodes.map((code) => {
                    const dInfo = bundle.drivers[code] || {};
                    const color = dInfo.team_color || "#71717A";
                    const dash = dInfo.dash || "";

                    const points: string[] = [];

                    if (chartMetric === "positions") {
                      const posList = bundle.chart_data.positions[code] || [];
                      posList.forEach((pos, idx) => {
                        const lapNum = idx + 1;
                        const x = totalLaps > 1 ? paddingLeft + ((lapNum - 1) / (totalLaps - 1)) * innerWidth : paddingLeft;
                        // P1 at top, P20 at bottom
                        const y = paddingTop + ((Math.max(1, Math.min(20, pos)) - 1) / 19) * chartHeight;
                        points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
                      });
                    } else {
                      const ltList = bundle.chart_data.lap_times[code] || [];
                      // Find min & max lap times among valid entries
                      const validTimes = ltList.filter((t): t is number => typeof t === "number" && t > 50 && t < 150);
                      const minT = validTimes.length > 0 ? Math.min(...validTimes) : 80;
                      const maxT = validTimes.length > 0 ? Math.max(...validTimes) : 110;
                      const rangeT = Math.max(1, maxT - minT);

                      ltList.forEach((t, idx) => {
                        if (typeof t === "number" && t > 0) {
                          const lapNum = idx + 1;
                          const x = totalLaps > 1 ? paddingLeft + ((lapNum - 1) / (totalLaps - 1)) * innerWidth : paddingLeft;
                          const clampedT = Math.max(minT, Math.min(maxT, t));
                          // Faster lap (lower seconds) at top
                          const y = paddingTop + ((clampedT - minT) / rangeT) * chartHeight;
                          points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
                        }
                      });
                    }

                    if (points.length < 2) return null;

                    return (
                      <g key={code}>
                        <polyline
                          points={points.join(" ")}
                          fill="none"
                          stroke={color}
                          strokeWidth="2"
                          strokeDasharray={dash}
                          opacity="0.85"
                        />
                      </g>
                    );
                  });
                })()}

                {/* Y Axis labels */}
                {chartMetric === "positions" ? (
                  <g fontSize="10" fontFamily="monospace" fill="var(--text-3)">
                    <text x="10" y="32">P1</text>
                    <text x="10" y="142">P10</text>
                    <text x="10" y="245">P20</text>
                  </g>
                ) : (
                  <g fontSize="10" fontFamily="monospace" fill="var(--text-3)">
                    <text x="10" y="32">Fast</text>
                    <text x="10" y="245">Slow</text>
                  </g>
                )}
              </svg>
            </div>
          </Panel>
        </section>
      )}
    </div>
  );
}

export default function LiveFeedPage(): React.JSX.Element {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-[12px] font-mono text-[var(--text-3)]">
          Loading live telemetry feed...
        </div>
      }
    >
      <LiveFeedContent />
    </Suspense>
  );
}
