"use client";

/**
 * QualiGap — Qualifying gaps with stage segmentation (V7-3 D spec).
 * - Segmented control Q1 | Q2 | Q3 (default Q3).
 * - In each stage, compare only drivers who set a time in that stage to fastest.
 * - Sort bars by time, show gap as +0.000 mono.
 * - Explanatory note: drivers eliminated earlier appear only in their last stage.
 * - "Final grid order" table beside the stage comparison.
 */
import React, { useState, useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { useIdentity } from "@/lib/useIdentity";

export interface StageDriver {
  code: string;
  name?: string;
  team?: string;
  time_s?: number | null;
  gap_s?: number | null;
  gap_str?: string;
}

export interface FinalGridEntry {
  position: number;
  code: string;
  name?: string;
  team?: string;
  best_time_s?: number | null;
  eliminated_in?: string;
}

interface QualiGapProps {
  d: {
    rows?: any[];
    stages?: Record<string, StageDriver[]>;
    final_grid?: FinalGridEntry[];
  };
}

export function QualiGap({ d }: QualiGapProps) {
  const { getDriver, getDriverColor } = useIdentity();
  const [selectedStage, setSelectedStage] = useState<"Q1" | "Q2" | "Q3">("Q3");

  // Derive stages if not directly provided
  const stagesData = useMemo(() => {
    if (d?.stages && Object.keys(d.stages).length > 0) {
      return d.stages;
    }
    const rows = d?.rows || [];
    const res: Record<string, StageDriver[]> = { Q1: [], Q2: [], Q3: [] };
    for (const st of ["Q1", "Q2", "Q3"] as const) {
      const stageRows: StageDriver[] = [];
      for (const r of rows) {
        const tVal = r[st] ?? (r.stage === st ? r.t_s : null);
        if (tVal != null && tVal > 0) {
          stageRows.push({
            code: r.code,
            name: r.name,
            team: r.team,
            time_s: tVal,
          });
        }
      }
      stageRows.sort((a, b) => (a.time_s ?? 999) - (b.time_s ?? 999));
      if (stageRows.length > 0) {
        const fastest = stageRows[0].time_s!;
        for (const sr of stageRows) {
          const gap = Math.round((sr.time_s! - fastest) * 1000) / 1000;
          sr.gap_s = gap;
          sr.gap_str = gap > 0 ? `+${gap.toFixed(3)}` : "+0.000";
        }
      }
      res[st] = stageRows;
    }
    return res;
  }, [d]);

  const finalGrid = useMemo(() => {
    if (d?.final_grid && d.final_grid.length > 0) {
      return d.final_grid;
    }
    const rows = d?.rows || [];
    return rows.map((r, i) => ({
      position: r.position || i + 1,
      code: r.code,
      name: r.name,
      team: r.team,
      best_time_s: r.t_s,
      eliminated_in: r.stage || "Q1",
    }));
  }, [d]);

  const activeDrivers = stagesData[selectedStage] || [];
  const maxGap = useMemo(() => {
    if (!activeDrivers.length) return 1.0;
    const gaps = activeDrivers.map((d) => d.gap_s ?? 0);
    return Math.max(0.2, ...gaps) * 1.15;
  }, [activeDrivers]);

  const ROW_H = 28;
  const W = 380;
  const m = { l: 55, r: 65, t: 10, b: 10 };
  const H = m.t + Math.max(1, activeDrivers.length) * ROW_H + m.b;

  const xs = scaleLinear().domain([0, maxGap]).range([m.l, W - m.r]);

  return (
    <div className="space-y-4">
      {/* Header controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-[var(--border)]">
        <div className="flex items-center gap-1.5 bg-[var(--surface-2)] p-1 rounded border border-[var(--border)] text-[12px]">
          <span className="text-[11px] font-mono text-[var(--text-3)] px-2">STAGE:</span>
          {(["Q1", "Q2", "Q3"] as const).map((stage) => {
            const count = (stagesData[stage] || []).length;
            const isSelected = selectedStage === stage;
            return (
              <button
                key={stage}
                type="button"
                onClick={() => setSelectedStage(stage)}
                className={`px-3 py-1 rounded font-mono font-semibold transition-colors ${
                  isSelected
                    ? "bg-[var(--accent)] text-white shadow-xs"
                    : "text-[var(--text-2)] hover:text-[var(--text)]"
                }`}
              >
                {stage} ({count})
              </button>
            );
          })}
        </div>

        <p className="text-[11px] text-[var(--text-3)] italic">
          Drivers eliminated earlier appear only in their last stage.
        </p>
      </div>

      {/* Two-column layout: Stage Comparison + Final Grid Order */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Stage Gap Chart */}
        <div className="lg:col-span-7 bg-[var(--surface)] p-4 rounded-lg border border-[var(--border)]">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-[12px] font-mono uppercase font-bold text-[var(--text)]">
              {selectedStage} Gaps to Fastest ({activeDrivers.length} drivers)
            </h4>
            <span className="text-[11px] font-mono text-[var(--text-3)]">
              Fastest: {activeDrivers[0]?.time_s ? `${activeDrivers[0].time_s.toFixed(3)}s` : "-"}
            </span>
          </div>

          {activeDrivers.length === 0 ? (
            <div className="text-center py-8 text-[12px] text-[var(--text-3)]">
              No lap times recorded in {selectedStage}.
            </div>
          ) : (
            <svg
              viewBox={`0 0 ${W} ${H}`}
              style={{ width: "100%", height: "auto" }}
              role="img"
              aria-label={`Qualifying gaps in ${selectedStage}`}
            >
              {activeDrivers.map((r, i) => {
                const y = m.t + i * ROW_H;
                const gap = r.gap_s ?? 0;
                const barW = Math.max(2, xs(gap) - m.l);
                const isFastest = gap === 0;
                const drvMeta = getDriver(r.code);
                const teamColor = drvMeta?.teamColor || getDriverColor(r.code) || "var(--accent, #6366f1)";
                const barColor = isFastest ? "var(--positive, #10b981)" : teamColor;

                return (
                  <g key={r.code} className="group">
                    {/* Driver Code */}
                    <text
                      x={m.l - 8}
                      y={y + ROW_H / 2}
                      fill="var(--text-2)"
                      fontSize="11"
                      textAnchor="end"
                      dominantBaseline="central"
                      fontFamily="var(--font-mono, monospace)"
                      className="group-hover:fill-[var(--text)] font-semibold"
                    >
                      {r.code}
                    </text>

                    {/* Background track */}
                    <rect
                      x={m.l}
                      y={y + 5}
                      width={W - m.l - m.r}
                      height={ROW_H - 10}
                      rx={3}
                      fill="var(--surface-2)"
                      opacity={0.5}
                    />

                    {/* Gap bar */}
                    <rect
                      x={m.l}
                      y={y + 5}
                      width={barW}
                      height={ROW_H - 10}
                      rx={3}
                      fill={barColor}
                      opacity={0.85}
                    />

                    {/* Gap mono label */}
                    <text
                      x={m.l + barW + 6}
                      y={y + ROW_H / 2}
                      fill={isFastest ? "var(--positive, #10b981)" : "var(--text)"}
                      fontSize="11"
                      textAnchor="start"
                      dominantBaseline="central"
                      fontFamily="var(--font-mono, monospace)"
                      fontWeight="600"
                    >
                      {r.gap_str || `+${gap.toFixed(3)}`}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </div>

        {/* Right: Final Grid Order Table */}
        <div className="lg:col-span-5 bg-[var(--surface)] p-4 rounded-lg border border-[var(--border)] overflow-hidden">
          <h4 className="text-[12px] font-mono uppercase font-bold text-[var(--text)] mb-2">
            Final Grid Order
          </h4>
          <div className="overflow-x-auto max-h-[460px] overflow-y-auto">
            <table className="w-full text-[11px] border-collapse font-mono">
              <thead>
                <tr className="border-b border-[var(--border)] text-[var(--text-3)] uppercase tracking-wider text-left">
                  <th className="py-1.5 px-2">Pos</th>
                  <th className="py-1.5 px-2">Driver</th>
                  <th className="py-1.5 px-2">Team</th>
                  <th className="py-1.5 px-2 text-right">Stage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {finalGrid.map((entry) => {
                  const drvMeta = getDriver(entry.code);
                  const teamColor = drvMeta?.teamColor || getDriverColor(entry.code) || "var(--accent)";
                  const displayName = drvMeta?.name || entry.name || entry.code;
                  const teamName = drvMeta?.team || entry.team || "-";

                  return (
                    <tr key={entry.code} className="hover:bg-[var(--surface-2)]">
                      <td className="py-1 px-2 font-bold text-[var(--text)]">P{entry.position}</td>
                      <td className="py-1 px-2 font-bold text-[var(--text)]">
                        <span
                          className="inline-block w-2 h-2 rounded-full mr-1.5 align-middle"
                          style={{ backgroundColor: teamColor }}
                        />
                        <span title={displayName}>{entry.code}</span>
                      </td>
                      <td className="py-1 px-2 text-[var(--text-3)] truncate max-w-[110px]" title={teamName}>
                        {teamName}
                      </td>
                      <td className="py-1 px-2 text-right">
                        <span className="px-1.5 py-0.5 rounded bg-[var(--surface-2)] text-[var(--text-2)] text-[10px]">
                          {entry.eliminated_in || "Q1"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
