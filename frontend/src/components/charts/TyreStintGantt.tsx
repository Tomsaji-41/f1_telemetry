"use client";

import React, { useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { ChartShell } from "./ChartShell";
import { TyreBadge } from "../primitives/kit";
import { useInspector } from "../layouts/inspector-drawer";

interface StintData {
  driver: string;
  stint: number;
  compound: string;
  start_lap: number;
  end_lap: number;
  length?: number;
}

interface TyreStintGanttProps {
  data: {
    status?: string;
    source?: string;
    coverage_note?: string;
    series?: StintData[];
  };
  loading?: boolean;
}

export function TyreStintGantt({ data, loading = false }: TyreStintGanttProps) {
  const { inspectItem } = useInspector();
  const rawStints = data?.series || [];

  // Group by driver
  const driverStints = useMemo(() => {
    const map: Record<string, StintData[]> = {};
    rawStints.forEach((s) => {
      if (!map[s.driver]) map[s.driver] = [];
      map[s.driver].push(s);
    });
    return map;
  }, [rawStints]);

  const drivers = Object.keys(driverStints);

  const maxLap = useMemo(() => {
    let m = 50;
    rawStints.forEach((s) => {
      if (s.end_lap > m) m = s.end_lap;
    });
    return m;
  }, [rawStints]);

  const width = 800;
  const rowHeight = 28;
  const height = Math.max(220, drivers.length * rowHeight + 50);
  const margin = { top: 20, right: 30, bottom: 30, left: 60 };

  const xScale = useMemo(() => {
    return scaleLinear()
      .domain([1, maxLap])
      .range([margin.left, width - margin.right]);
  }, [maxLap, width]);

  const getCompoundColor = (compound: string) => {
    const norm = compound.toUpperCase();
    if (norm.includes("SOFT") || norm === "S") return "var(--tyre-soft)";
    if (norm.includes("MEDIUM") || norm === "M") return "var(--tyre-medium)";
    if (norm.includes("HARD") || norm === "H") return "var(--tyre-hard)";
    if (norm.includes("INTER") || norm === "I") return "var(--tyre-inter)";
    return "var(--tyre-wet)";
  };

  const csvData = useMemo(() => {
    let csv = "Driver,Stint,Compound,StartLap,EndLap,Length\n";
    rawStints.forEach((s) => {
      csv += `${s.driver},${s.stint},${s.compound},${s.start_lap},${s.end_lap},${s.end_lap - s.start_lap + 1}\n`;
    });
    return csv;
  }, [rawStints]);

  const tableRows = useMemo(() => {
    return rawStints.map((s) => [
      s.driver,
      s.stint,
      s.compound,
      `${s.start_lap} - ${s.end_lap}`,
      s.end_lap - s.start_lap + 1,
    ]);
  }, [rawStints]);

  return (
    <ChartShell
      title="Tyre Strategy Gantt Sequence"
      subtitle="Compound stints and pit stop windows across the field"
      source={data?.source || "FastF1"}
      coverageNote={data?.coverage_note}
      loading={loading}
      empty={!drivers.length}
      emptyReason={data?.status === "outside_coverage" ? data.coverage_note : undefined}
      csvData={csvData}
      csvFilename="tyre_stints.csv"
      tableHeaders={["Driver", "Stint", "Compound", "Laps", "Length"]}
      tableRows={tableRows}
    >
      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto select-none">
          {/* Laps Grid */}
          {Array.from({ length: 6 }, (_, i) => Math.round((maxLap / 5) * i) || 1).map((lap) => (
            <g key={lap}>
              <line
                x1={xScale(lap)}
                y1={margin.top}
                x2={xScale(lap)}
                y2={height - margin.bottom}
                stroke="var(--border)"
                strokeWidth={0.8}
                strokeDasharray="2 2"
              />
              <text
                x={xScale(lap)}
                y={height - margin.bottom + 16}
                fontSize={10}
                fill="var(--text-3)"
                textAnchor="middle"
                fontFamily="var(--font-num)"
              >
                L{lap}
              </text>
            </g>
          ))}

          {/* Stint Bars per Driver */}
          {drivers.map((drv, drvIdx) => {
            const y = margin.top + drvIdx * rowHeight;
            const stints = driverStints[drv] || [];

            return (
              <g key={drv} className="group cursor-pointer">
                {/* Driver Code Label */}
                <text
                  x={margin.left - 12}
                  y={y + 14}
                  fontSize={11}
                  fontWeight="600"
                  fill="var(--text)"
                  textAnchor="end"
                  fontFamily="var(--font-num)"
                >
                  {drv}
                </text>

                {/* Stint segments */}
                {stints.map((st, sIdx) => {
                  const x1 = xScale(st.start_lap);
                  const x2 = xScale(st.end_lap);
                  const barWidth = Math.max(4, x2 - x1);
                  const color = getCompoundColor(st.compound);

                  return (
                    <g
                      key={sIdx}
                      onClick={() => {
                        inspectItem({
                          type: "point",
                          title: `${drv} — Stint ${st.stint}`,
                          subtitle: `${st.compound.toUpperCase()} Compound`,
                          details: {
                            Compound: st.compound,
                            "Start Lap": st.start_lap,
                            "End Lap": st.end_lap,
                            "Stint Length": `${st.end_lap - st.start_lap + 1} laps`,
                          },
                          queryContext: `Analyze ${drv} stint ${st.stint} tyre degradation`,
                        });
                      }}
                    >
                      <rect
                        x={x1}
                        y={y + 2}
                        width={barWidth}
                        height={16}
                        fill={color}
                        rx={2}
                        className="hover:opacity-85 transition-opacity"
                        stroke="rgba(0,0,0,0.3)"
                        strokeWidth={0.5}
                      />
                      {barWidth > 18 && (
                        <text
                          x={x1 + barWidth / 2}
                          y={y + 14}
                          fontSize={9}
                          fontWeight="bold"
                          fill={st.compound.toUpperCase().includes("HARD") ? "#0B0F14" : "#FFFFFF"}
                          textAnchor="middle"
                          fontFamily="var(--font-num)"
                        >
                          {st.compound[0].toUpperCase()}
                        </text>
                      )}
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>
    </ChartShell>
  );
}
