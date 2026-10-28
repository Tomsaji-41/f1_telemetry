"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  Radio,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Flag,
  AlertTriangle,
  Info,
  Clock,
  Layers,
} from "lucide-react";
import { Panel, Stat } from "@/components/primitives/kit";
import {
  DEMO_MODE,
  DEMO_LABEL,
  DEMO_RACE,
  DRIVERS,
  teamById,
  driverByCode,
  getRace,
  weatherAt,
  fmtLap,
  COMPOUND_COLOR,
  COMPOUND_NAME,
} from "@/demo/demoData";

export default function LiveFeedPage(): React.JSX.Element {
  const [currentLap, setCurrentLap] = useState<number>(1);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  const race = useMemo(() => getRace(), []);
  const currentWeather = useMemo(() => weatherAt(currentLap), [currentLap]);

  // Scrubber playback
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setCurrentLap((prev) => {
        if (prev >= DEMO_RACE.laps) {
          setIsPlaying(false);
          return DEMO_RACE.laps;
        }
        return prev + 1;
      });
    }, 1200);
    return () => clearInterval(interval);
  }, [isPlaying]);

  // Leaderboard data for currentLap
  const leaderboard = useMemo(() => {
    const posRow = race.positionsByLap[currentLap - 1] || {};
    const gapRow = race.gapByLap[currentLap - 1] || {};

    const rows = DRIVERS.map((d) => {
      const pos = posRow[d.code];
      const gap = gapRow[d.code];
      const team = teamById(d.team);
      const lapsForDriver = race.laps[d.code] || [];
      const currentLapData = lapsForDriver.find((l) => l.lap === currentLap);
      const isRetired = d.retire !== undefined && currentLap > d.retire;

      // Current stint & tyre
      const currentStint = race.stints.find(
        (s) => s.driver === d.code && currentLap >= s.startLap && currentLap <= s.endLap
      );
      const pitCount = race.pits.filter(
        (p) => p.driver === d.code && p.lap <= currentLap
      ).length;

      return {
        driver: d,
        team,
        pos: isRetired ? null : pos,
        gapVal: gap,
        isRetired,
        retireLap: d.retire,
        compound: currentStint?.compound ?? "M",
        tyreAge: currentLapData?.tyreAge ?? 1,
        lastLapTime: currentLapData?.time ? fmtLap(currentLapData.time) : "IN PIT",
        s1: currentLapData?.s1 ? currentLapData.s1.toFixed(3) : "-",
        s2: currentLapData?.s2 ? currentLapData.s2.toFixed(3) : "-",
        s3: currentLapData?.s3 ? currentLapData.s3.toFixed(3) : "-",
        pitCount,
      };
    });

    // Sort: active drivers first by position, then retired
    rows.sort((a, b) => {
      if (a.isRetired && !b.isRetired) return 1;
      if (!a.isRetired && b.isRetired) return -1;
      if (a.pos !== null && b.pos !== null) return a.pos - b.pos;
      return 0;
    });

    return rows.map((row, idx, arr) => {
      let gapText = "";
      let intervalText = "";

      if (row.isRetired) {
        gapText = `DNF (Lap ${row.retireLap})`;
        intervalText = "OUT";
      } else if (row.pos === 1) {
        gapText = "LEADER";
        intervalText = "LEADER";
      } else if (row.gapVal !== null && row.gapVal !== undefined) {
        gapText = `+${row.gapVal.toFixed(3)}s`;
        const prevRow = arr[idx - 1];
        if (prevRow && !prevRow.isRetired && prevRow.gapVal !== null && prevRow.gapVal !== undefined) {
          const diff = row.gapVal - prevRow.gapVal;
          intervalText = `+${Math.max(0, diff).toFixed(3)}s`;
        } else {
          intervalText = gapText;
        }
      } else {
        gapText = "DNF";
        intervalText = "OUT";
      }

      return {
        ...row,
        displayPos: row.isRetired ? "DNF" : `P${row.pos ?? idx + 1}`,
        gapText,
        intervalText,
      };
    });
  }, [race, currentLap]);

  // Race control messages up to current lap
  const rcMessages = useMemo(() => {
    return race.raceControl.filter((m) => m.lap <= currentLap);
  }, [race, currentLap]);

  return (
    <div className="space-y-6">
      {/* Demo banner */}
      {DEMO_MODE && (
        <div className="px-3 py-1.5 rounded text-xs font-mono bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center justify-between">
          <span>{DEMO_LABEL}</span>
          <span className="text-[11px] uppercase tracking-wider font-semibold">Simulated Session</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[11px] font-mono uppercase text-[var(--accent)] font-semibold flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 animate-pulse text-[var(--accent)]" />
              Telemetry Feed Replay
            </span>
            <span className="text-[var(--text-3)] text-xs">•</span>
            <span className="px-2 py-0.5 text-[11px] font-mono font-bold text-[var(--text-2)] bg-[var(--raised)] border border-[var(--border)] rounded">
              REPLAY
            </span>
          </div>
          <h1 className="text-[28px] font-semibold text-[var(--text)] tracking-tight">
            Live Telemetry Feed
          </h1>
          <p className="text-[13px] text-[var(--text-3)] mt-0.5">
            Replay: {DEMO_RACE.name}, {DEMO_RACE.session} ({DEMO_RACE.circuit})
          </p>
        </div>

        {/* Lap scrubber controls */}
        <div className="flex flex-col sm:items-end gap-2">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setCurrentLap((p) => Math.max(1, p - 1))}
              disabled={currentLap <= 1}
              className="p-1.5 text-[var(--text-2)] hover:text-[var(--text)] bg-[var(--raised)] border border-[var(--border)] rounded disabled:opacity-40"
              title="Previous lap"
            >
              <SkipBack className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setIsPlaying(!isPlaying)}
              className="px-3 py-1.5 flex items-center gap-1.5 text-xs font-mono font-bold bg-[var(--accent)] text-white rounded hover:opacity-90 transition-opacity"
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              {isPlaying ? "PAUSE" : "PLAY"}
            </button>
            <button
              type="button"
              onClick={() => setCurrentLap((p) => Math.min(DEMO_RACE.laps, p + 1))}
              disabled={currentLap >= DEMO_RACE.laps}
              className="p-1.5 text-[var(--text-2)] hover:text-[var(--text)] bg-[var(--raised)] border border-[var(--border)] rounded disabled:opacity-40"
              title="Next lap"
            >
              <SkipForward className="w-4 h-4" />
            </button>
            <span className="text-sm font-mono font-bold px-3 py-1 bg-[var(--surface)] border border-[var(--border)] rounded text-[var(--accent)]">
              Lap {currentLap} / {DEMO_RACE.laps}
            </span>
          </div>
          <div className="w-full sm:w-64 flex items-center gap-2">
            <input
              type="range"
              min={1}
              max={DEMO_RACE.laps}
              value={currentLap}
              onChange={(e) => setCurrentLap(Number(e.target.value))}
              className="w-full accent-[var(--accent)] cursor-pointer"
              aria-label="Lap scrubber"
            />
          </div>
        </div>
      </div>

      {/* Weather Strip */}
      <section className="p-4 border border-[var(--border)] rounded-lg bg-[var(--surface)]">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[12px] font-semibold text-[var(--text-3)] uppercase tracking-wider">
            Trackside Meteorological Strip (Lap {currentWeather.lap})
          </h2>
          <span className="text-[11px] font-mono text-[var(--text-3)]">
            {currentWeather.rain ? "Wet track conditions" : "Dry track surface"}
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          <Stat label="Air Temperature" value={`${currentWeather.airC}°C`} unit="Ambient" />
          <Stat label="Track Temperature" value={`${currentWeather.trackC}°C`} unit="Surface" />
          <Stat label="Relative Humidity" value={`${currentWeather.humidity}%`} unit="RH" />
          <Stat label="Wind Velocity" value={`${currentWeather.windMs} m/s`} unit="Vector" />
          <Stat label="Rainfall Probability" value={currentWeather.rain ? "100%" : "0%"} unit="Precip" />
        </div>
      </section>

      {/* Live Stream Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Leaderboard / Trace (2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          <Panel
            title={`Telemetry Leaderboard (Lap ${currentLap} of ${DEMO_RACE.laps})`}
            subtitle="Real-time order, gaps, tyre compound and sector intervals"
          >
            <div className="overflow-x-auto p-1">
              <table className="w-full text-[12px]">
                <thead className="border-b border-[var(--border)]">
                  <tr>
                    <th className="py-2 px-3 text-left text-[var(--text-3)]">Pos</th>
                    <th className="py-2 px-3 text-left text-[var(--text-3)]">Driver</th>
                    <th className="py-2 px-3 text-left text-[var(--text-3)]">Tyre</th>
                    <th className="py-2 px-3 text-right text-[var(--text-3)]">Gap</th>
                    <th className="py-2 px-3 text-right text-[var(--text-3)]">Interval</th>
                    <th className="py-2 px-3 text-right text-[var(--text-3)]">Last Lap</th>
                    <th className="py-2 px-3 text-right text-[var(--text-3)]">S1 / S2 / S3</th>
                    <th className="py-2 px-3 text-center text-[var(--text-3)]">Pits</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)] font-mono">
                  {leaderboard.map((r) => (
                    <tr
                      key={r.driver.code}
                      className={`hover:bg-[var(--raised)] transition-colors ${
                        r.isRetired ? "opacity-60" : ""
                      }`}
                    >
                      <td className="py-2 px-3 font-bold text-[var(--text)]">{r.displayPos}</td>
                      <td className="py-2 px-3 font-sans">
                        <div className="flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{ backgroundColor: r.team.color }}
                          />
                          <span className="font-bold text-[var(--text)]">{r.driver.code}</span>
                          <span className="text-[var(--text-3)] hidden md:inline text-[11px] truncate max-w-[100px]">
                            {r.driver.name}
                          </span>
                        </div>
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                          style={{
                            backgroundColor: `${COMPOUND_COLOR[r.compound]}22`,
                            color: COMPOUND_COLOR[r.compound],
                            border: `1px solid ${COMPOUND_COLOR[r.compound]}55`,
                          }}
                        >
                          {COMPOUND_NAME[r.compound][0]} ({r.tyreAge}L)
                        </span>
                      </td>
                      <td className="py-2 px-3 text-right text-[var(--accent)] font-semibold">
                        {r.gapText}
                      </td>
                      <td className="py-2 px-3 text-right text-[var(--text-2)]">{r.intervalText}</td>
                      <td className="py-2 px-3 text-right text-[var(--text)]">{r.lastLapTime}</td>
                      <td className="py-2 px-3 text-right text-[var(--text-3)] text-[11px]">
                        {r.s1} / {r.s2} / {r.s3}
                      </td>
                      <td className="py-2 px-3 text-center text-[var(--text-2)]">{r.pitCount}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>

        {/* Race Control Feed (1 col) */}
        <div className="lg:col-span-1">
          <Panel
            title="Race Control Telemetry Feed"
            subtitle={`Messages up to lap ${currentLap}`}
          >
            <div className="space-y-3 p-1 max-h-[500px] overflow-y-auto">
              {rcMessages.length === 0 ? (
                <div className="p-4 text-center text-xs text-[var(--text-3)]">
                  No race control messages recorded up to lap {currentLap}.
                </div>
              ) : (
                rcMessages.map((ev, i) => (
                  <div
                    key={i}
                    className="p-2.5 border border-[var(--border)] rounded bg-[var(--raised)] text-[12px] space-y-1"
                  >
                    <div className="flex items-center justify-between text-[10px] font-mono text-[var(--text-3)]">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {ev.time}
                      </span>
                      <span className="px-1.5 py-0.2 bg-[var(--surface)] border border-[var(--border)] rounded font-semibold text-[var(--text-2)]">
                        Lap {ev.lap}
                      </span>
                    </div>
                    <div className="flex items-start gap-2 pt-0.5">
                      {ev.category === "SafetyCar" ? (
                        <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                      ) : (
                        <Flag className="w-4 h-4 text-[var(--accent)] shrink-0 mt-0.5" />
                      )}
                      <p className="text-[var(--text)] font-sans text-[12px] leading-tight">
                        {ev.message}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
