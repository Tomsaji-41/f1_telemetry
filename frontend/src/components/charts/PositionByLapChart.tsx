"use client";

import React, { useState, useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { ChartShell } from "./ChartShell";
import { DriverChip } from "../primitives/kit";
import { useInspector } from "../layouts/inspector-drawer";

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
    series.forEach((s) => {
      s.x.forEach((lap) => {
        if (lap > m) m = lap;
      });
    });
    return m;
  }, [series]);

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
    let csv = "Driver,Lap,Position\n";
    series.forEach((s) => {
      s.x.forEach((lap, i) => {
        csv += `${s.driver},${lap},${s.y[i]}\n`;
      });
    });
    return csv;
  }, [series]);

  const tableRows = useMemo(() => {
    const rows: (string | number)[][] = [];
    series.forEach((s) => {
      s.x.forEach((lap, i) => {
        rows.push([s.driver, lap, `P${s.y[i]}`]);
      });
    });
    return rows;
  }, [series]);

  const getDriverColour = (code: string) => {
    const m = meta.find((d) => d.code === code);
    return m?.colour || "var(--accent)";
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
          {series.map((s) => (
            <DriverChip
              key={s.driver}
              code={s.driver}
              colour={getDriverColour(s.driver)}
              selected={isDriverVisible(s.driver)}
              onToggle={() => toggleDriver(s.driver)}
            />
          ))}
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
            {series.map((s, idx) => {
              if (!isDriverVisible(s.driver)) return null;
              const points = s.x
                .map((lap, i) => `${xScale(lap)},${yScale(s.y[i])}`)
                .join(" ");
              const color = getDriverColour(s.driver);

              return (
                <g key={s.driver} className="cursor-pointer group">
                  <polyline
                    points={points}
                    fill="none"
                    stroke={color}
                    strokeWidth={1.8}
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    className="transition-all hover:stroke-[3px]"
                    onClick={() => {
                      inspectItem({
                        type: "driver",
                        title: s.driver,
                        subtitle: "Lap Position History",
                        details: {
                          "Start Position": `P${s.y[0] || "-"}`,
                          "Finish Position": `P${s.y[s.y.length - 1] || "-"}`,
                          "Laps Charted": s.x.length,
                        },
                        queryContext: `Analyze position progression for ${s.driver}`,
                      });
                    }}
                  />
                  {/* End of series label */}
                  {s.x.length > 0 && (
                    <text
                      x={xScale(s.x[s.x.length - 1]) + 6}
                      y={yScale(s.y[s.y.length - 1]) + 3}
                      fontSize={10}
                      fontFamily="var(--font-num)"
                      fill={color}
                      fontWeight="bold"
                    >
                      {s.driver}
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
