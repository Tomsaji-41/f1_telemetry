"use client";

/**
 * PitChart — Pit stop analysis (V7-3 B spec).
 * - Driver 3-letter code, full name, team colour rule (never raw ids).
 * - FastF1 pit-lane delta or 'n/a (FastF1 not loaded)'.
 * - Flagged durations 'as reported' with race control context in tooltip.
 * - Scales clipped at 95th percentile of non-suspect stops with off-scale arrow.
 * - Chronological order with sortable columns.
 * - Grouped per driver with total pit time (sum of non-suspect stops).
 * - Team summary: median and best stop per team.
 */
import React, { useState, useMemo } from "react";
import { t } from "@/lib/i18n";
import { AlertCircle, ChevronDown, ChevronRight, Info } from "lucide-react";
import { useIdentity } from "@/lib/useIdentity";

interface PitStop {
  driver_id: string;
  code: string;
  name: string;
  team: string;
  color?: string;
  stop: number;
  lap: number;
  duration_s: number | null;
  suspect?: boolean;
  suspect_label?: string;
  context?: string | null;
  pit_lane_s?: number | null;
  pit_lane_note?: string | null;
  source?: string;
}

interface TeamSummaryItem {
  team: string;
  best_stop_s: number;
  median_stop_s: number;
  count: number;
  color?: string;
}

interface PitChartProps {
  d: {
    stops: PitStop[];
    p95_duration_s?: number;
    team_summary?: Record<string, TeamSummaryItem>;
    driver_summary?: any[];
  };
}

type SortField = "lap" | "stop" | "code" | "duration" | "pit_lane";

export function PitChart({ d }: PitChartProps) {
  const { getDriver, getTeam, getDriverColor } = useIdentity();
  const [sortField, setSortField] = useState<SortField>("lap");
  const [sortAsc, setSortAsc] = useState(true);
  const [viewMode, setViewMode] = useState<"chronological" | "driver_grouped" | "teams">("chronological");
  const [expandedDrivers, setExpandedDrivers] = useState<Set<string>>(new Set());

  const stops = d?.stops || [];
  const p95Dur = d?.p95_duration_s || 30.0;
  const teamSummary = d?.team_summary ? Object.values(d.team_summary) : [];

  const toggleDriver = (code: string) => {
    setExpandedDrivers((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const sortedStops = useMemo(() => {
    const list = [...stops];
    list.sort((a, b) => {
      let valA: any = 0;
      let valB: any = 0;
      if (sortField === "lap") {
        valA = a.lap;
        valB = b.lap;
      } else if (sortField === "stop") {
        valA = a.stop;
        valB = b.stop;
      } else if (sortField === "code") {
        valA = a.code;
        valB = b.code;
      } else if (sortField === "duration") {
        valA = a.duration_s ?? 9999;
        valB = b.duration_s ?? 9999;
      } else if (sortField === "pit_lane") {
        valA = a.pit_lane_s ?? 9999;
        valB = b.pit_lane_s ?? 9999;
      }
      if (valA < valB) return sortAsc ? -1 : 1;
      if (valA > valB) return sortAsc ? 1 : -1;
      return 0;
    });
    return list;
  }, [stops, sortField, sortAsc]);

  // Grouped by driver
  const driverGroups = useMemo(() => {
    const map = new Map<string, { driver: PitStop; stops: PitStop[]; total_s: number; has_suspect: boolean }>();
    for (const s of stops) {
      if (!map.has(s.code)) {
        map.set(s.code, { driver: s, stops: [], total_s: 0, has_suspect: false });
      }
      const entry = map.get(s.code)!;
      entry.stops.push(s);
      if (s.duration_s != null && !s.suspect) {
        entry.total_s = Math.round((entry.total_s + s.duration_s) * 1000) / 1000;
      }
      if (s.suspect) entry.has_suspect = true;
    }
    return [...map.values()].sort((a, b) => a.total_s - b.total_s);
  }, [stops]);

  if (!stops.length) {
    return (
      <div className="text-center text-[var(--text-2)] text-[13px] py-8">
        {t("chart.empty")}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* View Switcher */}
      <div className="flex items-center justify-between pb-2 border-b border-[var(--border)]">
        <div className="flex items-center gap-1.5 bg-[var(--surface-2)] p-1 rounded border border-[var(--border)] text-[11px]">
          <button
            type="button"
            onClick={() => setViewMode("chronological")}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              viewMode === "chronological"
                ? "bg-[var(--accent)] text-white shadow-xs"
                : "text-[var(--text-2)] hover:text-[var(--text)]"
            }`}
          >
            Chronological ({stops.length})
          </button>
          <button
            type="button"
            onClick={() => setViewMode("driver_grouped")}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              viewMode === "driver_grouped"
                ? "bg-[var(--accent)] text-white shadow-xs"
                : "text-[var(--text-2)] hover:text-[var(--text)]"
            }`}
          >
            Driver Totals ({driverGroups.length})
          </button>
          {teamSummary.length > 0 && (
            <button
              type="button"
              onClick={() => setViewMode("teams")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                viewMode === "teams"
                  ? "bg-[var(--accent)] text-white shadow-xs"
                  : "text-[var(--text-2)] hover:text-[var(--text)]"
              }`}
            >
              Team Benchmark ({teamSummary.length})
            </button>
          )}
        </div>

        <span className="text-[11px] text-[var(--text-3)] font-mono">
          Axis clipped at P95: {p95Dur.toFixed(1)}s
        </span>
      </div>

      {/* 1. CHRONOLOGICAL TABLE */}
      {viewMode === "chronological" && (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px] border-collapse">
            <thead>
              <tr className="border-b border-[var(--border)] text-[11px] uppercase font-mono tracking-wider">
                <th
                  onClick={() => handleSort("lap")}
                  className="py-2 px-3 text-left font-medium text-[var(--text-3)] cursor-pointer hover:text-[var(--text)]"
                >
                  Lap {sortField === "lap" && (sortAsc ? "▲" : "▼")}
                </th>
                <th
                  onClick={() => handleSort("code")}
                  className="py-2 px-3 text-left font-medium text-[var(--text-3)] cursor-pointer hover:text-[var(--text)]"
                >
                  Driver {sortField === "code" && (sortAsc ? "▲" : "▼")}
                </th>
                <th
                  onClick={() => handleSort("stop")}
                  className="py-2 px-3 text-left font-medium text-[var(--text-3)] cursor-pointer hover:text-[var(--text)]"
                >
                  Stop {sortField === "stop" && (sortAsc ? "▲" : "▼")}
                </th>
                <th
                  onClick={() => handleSort("duration")}
                  className="py-2 px-3 text-left font-medium text-[var(--text-3)] w-2/5 cursor-pointer hover:text-[var(--text)]"
                >
                  Duration (Stop) {sortField === "duration" && (sortAsc ? "▲" : "▼")}
                </th>
                <th
                  onClick={() => handleSort("pit_lane")}
                  className="py-2 px-3 text-right font-medium text-[var(--text-3)] cursor-pointer hover:text-[var(--text)]"
                >
                  Pit Lane Delta {sortField === "pit_lane" && (sortAsc ? "▲" : "▼")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {sortedStops.map((s, idx) => {
                const dur = s.duration_s;
                const isOffScale = dur != null && dur > p95Dur;
                const barPct = dur != null ? Math.min(100, (Math.min(dur, p95Dur) / p95Dur) * 100) : 0;
                const drvMeta = getDriver(s.code);
                const teamColor = drvMeta?.teamColor || s.color || getDriverColor(s.code) || "#A9A9BC";
                const driverName = drvMeta?.name || s.name || s.code;

                return (
                  <tr key={`${s.code}-${s.lap}-${s.stop}-${idx}`} className="hover:bg-[var(--raised)]">
                    <td className="py-2 px-3 font-mono text-[var(--text-2)]">
                      L{s.lap}
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex items-center gap-2">
                        <span
                          className="w-1.5 h-4 rounded-full"
                          style={{ backgroundColor: teamColor }}
                        />
                        <span className="font-mono font-bold text-[var(--text)]">
                          {s.code}
                        </span>
                        <span className="text-[var(--text-3)] text-[11px] truncate max-w-[120px]">
                          {driverName}
                        </span>
                      </div>
                    </td>
                    <td className="py-2 px-3 font-mono text-[var(--text-2)]">
                      #{s.stop}
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-4 rounded relative"
                          style={{
                            width: `${barPct}%`,
                            minWidth: 4,
                            backgroundColor: s.suspect ? "rgba(245,158,11,0.6)" : "var(--accent)",
                            border: s.suspect ? "1px solid rgba(245,158,11,0.9)" : undefined,
                          }}
                        />
                        {isOffScale && (
                          <span
                            className="text-amber-500 font-mono text-[11px] font-bold"
                            title="Exceeds P95 scale limit (clipped)"
                          >
                            ▶
                          </span>
                        )}
                        <span className="font-mono text-[var(--text)] text-[11px] shrink-0">
                          {dur != null ? `${dur.toFixed(3)}s` : "—"}
                          {s.suspect && (
                            <span
                              className="ml-1 px-1 py-0.5 text-[9px] font-sans font-medium rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 cursor-help"
                              title={s.context ? `${s.suspect_label || "as reported"} — ${s.context}` : (s.suspect_label || "as reported")}
                            >
                              ⚠ as reported
                            </span>
                          )}
                        </span>
                      </div>
                      {s.context && (
                        <div className="text-[10px] text-amber-400/90 flex items-center gap-1 mt-0.5">
                          <Info className="w-3 h-3" />
                          <span>{s.context}</span>
                        </div>
                      )}
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-[11px]">
                      {s.pit_lane_s != null ? (
                        <span className="text-[var(--text)]">{s.pit_lane_s.toFixed(1)}s</span>
                      ) : (
                        <span className="text-[var(--text-3)] italic">
                          {s.pit_lane_note || "n/a (FastF1 not loaded)"}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 2. DRIVER GROUPED VIEW */}
      {viewMode === "driver_grouped" && (
        <div className="space-y-2">
          {driverGroups.map(({ driver, stops: dStops, total_s, has_suspect }) => {
            const isExpanded = expandedDrivers.has(driver.code);
            const drvMeta = getDriver(driver.code);
            const teamColor = drvMeta?.teamColor || driver.color || getDriverColor(driver.code) || "#A9A9BC";
            const driverName = drvMeta?.name || driver.name || driver.code;
            const teamName = drvMeta?.team || driver.team || "Unknown";

            return (
              <div
                key={driver.code}
                className="border border-[var(--border)] rounded bg-[var(--surface)] overflow-hidden"
              >
                <div
                  onClick={() => toggleDriver(driver.code)}
                  className="flex items-center justify-between p-3 cursor-pointer hover:bg-[var(--raised)] select-none"
                >
                  <div className="flex items-center gap-3">
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-[var(--text-3)]" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-[var(--text-3)]" />
                    )}
                    <span
                      className="w-2 h-4 rounded-full"
                      style={{ backgroundColor: teamColor }}
                    />
                    <span className="font-mono font-bold text-[var(--text)]">
                      {driver.code}
                    </span>
                    <span className="text-[var(--text-2)] text-[12px]">
                      {driverName}
                    </span>
                    <span className="text-[11px] text-[var(--text-3)]">
                      ({teamName})
                    </span>
                  </div>

                  <div className="flex items-center gap-4 font-mono text-[12px]">
                    <span className="text-[var(--text-2)]">
                      {dStops.length} {dStops.length === 1 ? "stop" : "stops"}
                    </span>
                    <span className="font-bold text-[var(--text)]">
                      Total: {total_s.toFixed(3)}s
                      {has_suspect && (
                        <span className="text-[10px] text-amber-400 font-sans font-normal ml-1">
                          (excl. flagged)
                        </span>
                      )}
                    </span>
                  </div>
                </div>

                {isExpanded && (
                  <div className="p-3 bg-[var(--surface-2)] border-t border-[var(--border)]">
                    <table className="w-full text-[11px] font-mono">
                      <thead>
                        <tr className="text-[var(--text-3)] border-b border-[var(--border)]">
                          <th className="py-1 text-left">Stop</th>
                          <th className="py-1 text-left">Lap</th>
                          <th className="py-1 text-left">Duration</th>
                          <th className="py-1 text-right">Pit Lane</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border)]">
                        {dStops.map((st, i) => (
                          <tr key={i}>
                            <td className="py-1.5">#{st.stop}</td>
                            <td className="py-1.5">L{st.lap}</td>
                            <td className="py-1.5">
                              {st.duration_s != null ? `${st.duration_s.toFixed(3)}s` : "—"}
                              {st.suspect && (
                                <span className="ml-1 text-amber-400">
                                  ⚠ {st.suspect_label || "as reported"}
                                </span>
                              )}
                            </td>
                            <td className="py-1.5 text-right">
                              {st.pit_lane_s != null
                                ? `${st.pit_lane_s.toFixed(1)}s`
                                : st.pit_lane_note || "n/a"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 3. TEAM SUMMARY VIEW */}
      {viewMode === "teams" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {teamSummary.map((tm) => {
            const teamMeta = getTeam(tm.team);
            const teamColor = teamMeta?.teamColor || tm.color || "#A9A9BC";
            const teamName = teamMeta?.name || tm.team;

            return (
              <div
                key={tm.team}
                className="p-3.5 border border-[var(--border)] rounded bg-[var(--surface)] space-y-2"
              >
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-4 rounded-full"
                    style={{ backgroundColor: teamColor }}
                  />
                  <span className="font-semibold text-[13px] text-[var(--text)]">
                    {teamName}
                  </span>
                  <span className="text-[11px] text-[var(--text-3)] font-mono ml-auto">
                    {tm.count} stops
                  </span>
                </div>
              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[var(--border)] font-mono text-[12px]">
                <div>
                  <span className="text-[10px] uppercase text-[var(--text-3)] block font-sans">
                    Best Stop
                  </span>
                  <span className="font-bold text-[var(--positive)]">
                    {tm.best_stop_s.toFixed(3)}s
                  </span>
                </div>
                <div>
                  <span className="text-[10px] uppercase text-[var(--text-3)] block font-sans">
                    Median Stop
                  </span>
                  <span className="text-[var(--text)]">
                    {tm.median_stop_s.toFixed(3)}s
                  </span>
                </div>
              </div>
            </div>
          );
        })}
        </div>
      )}
    </div>
  );
}
