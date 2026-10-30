"use client";

import React, { useState, useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { line } from "d3-shape";
import { ChartShell } from "./ChartShell";
import { DriverChip } from "../primitives/kit";
import { useInspector } from "../layouts/inspector-drawer";
import { useIdentity } from "@/lib/useIdentity";

interface SeriesData {
  driver: string;
  x: number[]; // laps
  y: Array<number | null | undefined>; // positions
}

interface PositionByLapProps {
  data: {
    status?: string;
    source?: string;
    coverage_note?: string;
    x?: number[];
    series?: SeriesData[];
    annotations?: { lap: number; type: string; text: string }[];
    driver_meta?: { code: string; name: string; team: string; colour: string }[];
  };
  loading?: boolean;
}

export const firstValidIndex = (vals: Array<number | null | undefined>): number => {
  if (!vals || !Array.isArray(vals)) return -1;
  for (let i = 0; i < vals.length; i++) {
    const v = vals[i];
    if (typeof v === "number" && Number.isFinite(v)) return i;
  }
  return -1;
};

export const lastValidIndex = (vals: Array<number | null | undefined>): number => {
  if (!vals || !Array.isArray(vals)) return -1;
  for (let i = vals.length - 1; i >= 0; i--) {
    const v = vals[i];
    if (typeof v === "number" && Number.isFinite(v)) return i;
  }
  return -1;
};

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
        if (typeof lap === "number" && Number.isFinite(lap) && lap > m) m = lap;
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

  // D3 line generator with strict .defined() check for finite positions & laps
  const lineGenerator = useMemo(() => {
    return line<{ lap: number; pos: number | null | undefined }>()
      .defined(
        (d) =>
          typeof d.pos === "number" &&
          Number.isFinite(d.pos) &&
          typeof d.lap === "number" &&
          Number.isFinite(d.lap)
      )
      .x((d) => xScale(d.lap))
      .y((d) => yScale(d.pos as number));
  }, [xScale, yScale]);

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
        rows.push([code, lap, yVals[i] != null ? `P${yVals[i]}` : "DNF"]);
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
            {[1, 5, 10, 15, 20].map((pos) => {
              const y = yScale(pos);
              if (!Number.isFinite(y)) return null;
              return (
                <g key={pos}>
                  <line
                    x1={margin.left}
                    y1={y}
                    x2={width - margin.right}
                    y2={y}
                    stroke="var(--border)"
                    strokeWidth={0.8}
                    strokeDasharray="2 2"
                  />
                  <text
                    x={margin.left - 8}
                    y={y + 3}
                    fontSize={10}
                    fill="var(--text-3)"
                    textAnchor="end"
                    fontFamily="var(--font-num)"
                  >
                    P{pos}
                  </text>
                </g>
              );
            })}

            {/* X-axis Laps */}
            {Array.from({ length: 6 }, (_, i) => Math.round((maxLap / 5) * i) || 1).map((lap) => {
              const x = xScale(lap);
              if (!Number.isFinite(x)) return null;
              return (
                <g key={lap}>
                  <text
                    x={x}
                    y={height - margin.bottom + 18}
                    fontSize={10}
                    fill="var(--text-3)"
                    textAnchor="middle"
                    fontFamily="var(--font-num)"
                  >
                    L{lap}
                  </text>
                </g>
              );
            })}

            {/* Series Lines with draw-on animation */}
            {series.map((s) => {
              const code = s.driver || (s as any).code || "DRV";
              if (!isDriverVisible(code)) return null;
              const rootX = (data as any)?.x || [];
              const laps = s.x || rootX;
              const yVals = s.y || [];

              const drvMeta = getDriver(code);
              const color = drvMeta?.teamColor || getDriverColour(code);
              const strokeDash = drvMeta?.strokeDash || undefined;

              // Generate path using D3 line with .defined() so retired drivers stop cleanly
              const pointsData = laps.map((lap: number, i: number) => ({
                lap,
                pos: yVals[i],
              }));
              const pathData = lineGenerator(pointsData) || "";

              const fi = firstValidIndex(yVals);
              const li = lastValidIndex(yVals);

              return (
                <g key={code} className="cursor-pointer group">
                  {pathData ? (
                    <path
                      d={pathData}
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
                          title: drvMeta?.name || code,
                          subtitle: "Lap Position History",
                          details: {
                            Driver: drvMeta?.name || code,
                            Team: drvMeta?.team || "Unknown",
                            "Start Position": fi >= 0 && yVals[fi] != null ? `P${yVals[fi]}` : "-",
                            "Finish Position": li >= 0 && yVals[li] != null ? `P${yVals[li]}` : "DNF",
                            "Laps Charted": laps.length,
                          },
                          queryContext: `Analyze position progression for ${code}`,
                        });
                      }}
                    />
                  ) : null}

                  {/* Start of series label (left end) */}
                  {(() => {
                    if (fi < 0) return null;
                    const x = xScale(laps[fi]);
                    const y = yScale(yVals[fi] as number);
                    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
                    return (
                      <text
                        x={x - 6}
                        y={y + 3}
                        fontSize={9}
                        fontFamily="var(--font-num)"
                        fill="var(--text-3)"
                        textAnchor="end"
                        className="group-hover:fill-[var(--text)] font-semibold"
                      >
                        {code}
                      </text>
                    );
                  })()}

                  {/* End of series label (right end) */}
                  {(() => {
                    if (li < 0) return null; // driver has no valid positions: skip label
                    const x = xScale(laps[li]);
                    const y = yScale(yVals[li] as number);
                    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
                    return (
                      <text
                        x={x + 6}
                        y={y + 3}
                        fontSize={10}
                        fontFamily="var(--font-num)"
                        fill={color}
                        fontWeight="bold"
                      >
                        {code}
                      </text>
                    );
                  })()}
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </ChartShell>
  );
}
