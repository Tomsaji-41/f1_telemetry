"use client";

import React, { useState, useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { ChartShell } from "./ChartShell";
import { DriverChip } from "../primitives/kit";
import { useInspector } from "../layouts/inspector-drawer";
import { useIdentity } from "@/lib/useIdentity";

interface SeriesData {
  driver: string;
  x: number[]; // laps
  y: number[]; // positions
}

interface PositionByLapProps {
  data: {
    status?: string;
    source?: string;
    coverage_note?: string;
    series?: SeriesData[];
    annotations?: { lap: number; type: string; text: string }[];
    driver_meta?: { code: string; name: string; team: string; colour: string }[];
  };
  loading?: boolean;
}

export function PositionByLapChart({ data, loading = false }: PositionByLapProps) {
  const { inspectItem } = useInspector();
  const { getDriver, getDriverColor } = useIdentity();
  const series = data?.series || [];
  const meta = data?.driver_meta || [];

  // Active driver toggles
  const [selectedDrivers, setSelectedDrivers] = useState<Record<string, boolean>>({});

  const isDriverVisible = (code: string) => {
    if (Object.keys(selectedDrivers).length === 0) return true;
    return !!selectedDrivers[code];
  };

  const toggleDriver = (code: string) => {
    setSelectedDrivers((prev) => ({
      ...prev,
      [code]: prev[code] === undefined ? false : !prev[code],
    }));
  };

  // Dimensions
  const width = 800;
  const height = 340;
  const margin = { top: 20, right: 40, bottom: 30, left: 40 };

  const maxLap = useMemo(() => {
    let m = 50;
    const rootX = (data as any)?.x || [];
    series.forEach((s) => {
      const laps = s.x || rootX;
      laps.forEach((lap: number) => {
        if (lap > m) m = lap;
      });
    });
    return m;
  }, [series, data]);

  const xScale = useMemo(() => {
    return scaleLinear()
      .domain([1, maxLap])
      .range([margin.left, width - margin.right]);
  }, [maxLap, width]);

  const yScale = useMemo(() => {
    return scaleLinear()
      .domain([1, 20])
      .range([margin.top, height - margin.bottom]);
  }, [height]);

  // CSV generation
  const csvData = useMemo(() => {
    if (!series.length) return "";
    const rootX = (data as any)?.x || [];
    let csv = "Driver,Lap,Position\n";
    series.forEach((s) => {
      const code = s.driver || (s as any).code || "DRV";
      const laps = s.x || rootX;
      const yVals = s.y || [];
      laps.forEach((lap: number, i: number) => {
        csv += `${code},${lap},${yVals[i] ?? ""}\n`;
      });
    });
    return csv;
  }, [series, data]);

  const tableRows = useMemo(() => {
    const rows: (string | number)[][] = [];
    const rootX = (data as any)?.x || [];
    series.forEach((s) => {
      const code = s.driver || (s as any).code || "DRV";
      const laps = s.x || rootX;
      const yVals = s.y || [];
      laps.forEach((lap: number, i: number) => {
        rows.push([code, lap, `P${yVals[i] ?? "-"}`]);
      });
    });
    return rows;
  }, [series, data]);

  const getDriverColour = (code: string) => {
    const drv = getDriver(code);
    if (drv?.teamColor) return drv.teamColor;
    const m = meta.find((d) => d.code === code);
    return m?.colour || getDriverColor(code) || "var(--accent)";
  };

  return (
    <ChartShell
      title="Lap-by-Lap Position (Bump Chart)"
      subtitle="Track position changes and overtakes throughout the race"
      source={data?.source || "FastF1 & Jolpica"}
      coverageNote={data?.coverage_note}
      loading={loading}
      empty={!series.length}
      emptyReason={data?.status === "outside_coverage" ? data.coverage_note : undefined}
      csvData={csvData}
      csvFilename="lap_positions.csv"
      tableHeaders={["Driver", "Lap", "Position"]}
      tableRows={tableRows}
    >
      <div className="flex flex-col space-y-3">
        {/* Driver Toggle Legend */}
        <div className="flex flex-wrap gap-1.5 pb-2">
          {series.map((s) => {
            const code = s.driver || (s as any).code || "DRV";
            return (
              <DriverChip
                key={code}
                code={code}
                colour={getDriverColour(code)}
                selected={isDriverVisible(code)}
                onToggle={() => toggleDriver(code)}
              />
            );
          })}
        </div>

        {/* SVG Bump Chart */}
        <div className="w-full overflow-x-auto">
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto select-none">
            {/* Grid Lines */}
            {[1, 5, 10, 15, 20].map((pos) => (
              <g key={pos}>
                <line
                  x1={margin.left}
                  y1={yScale(pos)}
                  x2={width - margin.right}
                  y2={yScale(pos)}
                  stroke="var(--border)"
                  strokeWidth={0.8}
                  strokeDasharray="2 2"
                />
                <text
                  x={margin.left - 8}
                  y={yScale(pos) + 3}
                  fontSize={10}
                  fill="var(--text-3)"
                  textAnchor="end"
                  fontFamily="var(--font-num)"
                >
                  P{pos}
                </text>
              </g>
            ))}

            {/* X-axis Laps */}
            {Array.from({ length: 6 }, (_, i) => Math.round((maxLap / 5) * i) || 1).map((lap) => (
              <g key={lap}>
                <text
                  x={xScale(lap)}
                  y={height - margin.bottom + 18}
                  fontSize={10}
                  fill="var(--text-3)"
                  textAnchor="middle"
                  fontFamily="var(--font-num)"
                >
                  L{lap}
                </text>
              </g>
            ))}

            {/* Series Lines with draw-on animation */}
            {series.map((s) => {
              const code = s.driver || (s as any).code || "DRV";
              if (!isDriverVisible(code)) return null;
              const rootX = (data as any)?.x || [];
              const laps = s.x || rootX;
              const yVals = s.y || [];
              const points = laps
                .map((lap: number, i: number) => `${xScale(lap)},${yScale(yVals[i])}`)
                .join(" ");
              const drvMeta = getDriver(code);
              const color = drvMeta?.teamColor || getDriverColour(code);
              const strokeDash = drvMeta?.strokeDash || undefined;

              return (
                <g key={code} className="cursor-pointer group">
                  <polyline
                    points={points}
                    fill="none"
                    stroke={color}
                    strokeWidth={1.8}
                    strokeDasharray={strokeDash}
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    className="transition-all hover:stroke-[3px]"
                    onClick={() => {
                      inspectItem({
                        type: "driver",
                        title: code,
                        subtitle: "Lap Position History",
                        details: {
                          "Start Position": `P${yVals[0] || "-"}`,
                          "Finish Position": `P${yVals[yVals.length - 1] || "-"}`,
                          "Laps Charted": laps.length,
                        },
                        queryContext: `Analyze position progression for ${code}`,
                      });
                    }}
                  />
                  {/* Start of series label (left end) */}
                  {laps.length > 0 && (
                    <text
                      x={xScale(laps[0]) - 6}
                      y={yScale(yVals[0]) + 3}
                      fontSize={9}
                      fontFamily="var(--font-num)"
                      fill="var(--text-3)"
                      textAnchor="end"
                      className="group-hover:fill-[var(--text)] font-semibold"
                    >
                      {code}
                    </text>
                  )}
                  {/* End of series label (right end) */}
                  {laps.length > 0 && (
                    <text
                      x={xScale(laps[laps.length - 1]) + 6}
                      y={yScale(yVals[yVals.length - 1]) + 3}
                      fontSize={10}
                      fontFamily="var(--font-num)"
                      fill={color}
                      fontWeight="bold"
                    >
                      {code}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </ChartShell>
  );
}
