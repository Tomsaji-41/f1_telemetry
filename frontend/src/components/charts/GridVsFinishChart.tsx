"use client";

import React, { useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { ChartShell } from "./ChartShell";
import { useInspector } from "../layouts/inspector-drawer";

interface GridFinishPair {
  driver: string;
  code?: string;
  team: string;
  grid: number;
  position: number;
  delta: number;
  status?: string;
  badge?: "DNF" | "DSQ" | null;
  is_dnf?: boolean;
  is_dsq?: boolean;
}

interface GridVsFinishProps {
  data: {
    status?: string;
    source?: string;
    coverage_note?: string;
    series?: GridFinishPair[];
    rows?: any[];
  };
  loading?: boolean;
}

export function GridVsFinishChart({ data, loading = false }: GridVsFinishProps) {
  const { inspectItem } = useInspector();
  const rawPairs = useMemo(() => {
    if (data?.series?.length) return data.series;
    if (data?.rows?.length) {
      return data.rows.map((r) => ({
        driver: r.name || r.code,
        code: r.code,
        team: r.team || "Unknown",
        grid: r.grid,
        position: r.finish,
        delta: r.delta,
        status: r.status,
        badge: r.badge,
        is_dnf: r.is_dnf,
        is_dsq: r.is_dsq,
      }));
    }
    return [];
  }, [data]);

  const width = 640;
  const height = 400;
  const margin = { top: 30, right: 90, bottom: 20, left: 90 };

  const validPairs = useMemo(
    () => rawPairs.filter((p) => p.grid != null && p.position != null),
    [rawPairs]
  );

  const maxPos = useMemo(
    () => Math.max(20, ...validPairs.map((p) => Math.max(p.grid, p.position))),
    [validPairs]
  );

  const yScale = useMemo(() => {
    return scaleLinear()
      .domain([1, maxPos])
      .range([margin.top, height - margin.bottom]);
  }, [height, maxPos]);

  const csvData = useMemo(() => {
    let csv = "Driver,Team,Grid,Finish,Delta,Status\n";
    validPairs.forEach((p) => {
      csv += `${p.driver},${p.team},${p.grid},${p.position},${p.delta ?? "DNF"},${p.status || "Finished"}\n`;
    });
    return csv;
  }, [validPairs]);

  const tableRows = useMemo(() => {
    return validPairs.map((p) => [
      p.driver,
      p.team,
      `P${p.grid}`,
      p.badge ? `DNF (P${p.position})` : `P${p.position}`,
      p.badge ? p.badge : p.delta > 0 ? `+${p.delta}` : p.delta === 0 ? "0" : String(p.delta),
    ]);
  }, [validPairs]);

  return (
    <ChartShell
      title="Grid versus Finish (Slope Chart)"
      subtitle="Positions gained or lost from starting grid to chequered flag"
      source={data?.source || "Jolpica"}
      coverageNote={data?.coverage_note}
      loading={loading}
      empty={!validPairs.length}
      csvData={csvData}
      csvFilename="grid_vs_finish.csv"
      tableHeaders={["Driver", "Team", "Grid", "Finish", "Delta"]}
      tableRows={tableRows}
    >
      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto select-none" role="img" aria-label="Grid vs finish comparison">
          {/* Column Headers */}
          <text
            x={margin.left}
            y={margin.top - 12}
            fontSize={11}
            fontWeight="600"
            fill="var(--text-3)"
            textAnchor="middle"
            className="font-mono uppercase"
          >
            STARTING GRID
          </text>
          <text
            x={width - margin.right}
            y={margin.top - 12}
            fontSize={11}
            fontWeight="600"
            fill="var(--text-3)"
            textAnchor="middle"
            className="font-mono uppercase"
          >
            FINISH
          </text>

          {/* Guide lines */}
          {Array.from({ length: maxPos }, (_, i) => i + 1).map((p) => (
            <line
              key={p}
              x1={margin.left}
              x2={width - margin.right}
              y1={yScale(p)}
              y2={yScale(p)}
              stroke="var(--border)"
              strokeWidth={0.5}
              strokeDasharray="2 3"
              opacity={0.5}
            />
          ))}

          {/* Lines for each driver */}
          {validPairs.map((p) => {
            const y1 = yScale(p.grid || 20);
            const y2 = yScale(p.position || 20);
            const isRetirement = p.is_dnf || p.is_dsq || p.badge === "DNF" || p.badge === "DSQ";
            const gained = !isRetirement && p.delta > 0;
            const lost = !isRetirement && p.delta < 0;
            const unchanged = !isRetirement && p.delta === 0;

            const strokeColor = isRetirement
              ? "#f43f5e"
              : gained
              ? "var(--positive, #10b981)"
              : lost
              ? "var(--negative, #ef4444)"
              : "var(--text-3)";

            const driverCode = p.code || p.driver.slice(0, 3).toUpperCase();

            return (
              <g
                key={`${p.driver}-${p.grid}`}
                className="group cursor-pointer"
                onClick={() => {
                  inspectItem({
                    type: "driver",
                    title: p.driver,
                    subtitle: p.team,
                    details: {
                      "Grid Position": `P${p.grid}`,
                      "Finish Position": isRetirement ? `DNF (${p.status || "Retired"})` : `P${p.position}`,
                      "Net Delta": isRetirement ? "Retired" : gained ? `+${p.delta} positions` : `${p.delta} positions`,
                    },
                    queryContext: `Analyze race performance for ${p.driver} from grid P${p.grid} to finish P${p.position}`,
                  });
                }}
              >
                {/* Connecting slope line */}
                <line
                  x1={margin.left}
                  y1={y1}
                  x2={width - margin.right}
                  y2={y2}
                  stroke={strokeColor}
                  strokeWidth={1.5}
                  strokeDasharray={isRetirement ? "4 3" : undefined}
                  strokeOpacity={0.8}
                  className="group-hover:stroke-[2.5px] group-hover:stroke-opacity-100 transition-all"
                />

                {/* Left Node (Driver code and grid on left end only) */}
                <circle cx={margin.left} cy={y1} r={3.5} fill={strokeColor} />
                <text
                  x={margin.left - 10}
                  y={y1 + 3}
                  fontSize={10}
                  fill="var(--text-2)"
                  textAnchor="end"
                  fontFamily="var(--font-mono, monospace)"
                  className="group-hover:fill-[var(--text)] font-medium"
                >
                  P{p.grid} {driverCode}
                </text>

                {/* Right Node (Position number and indicator on right end only) */}
                <circle cx={width - margin.right} cy={y2} r={3.5} fill={strokeColor} />
                <text
                  x={width - margin.right + 10}
                  y={y2 + 3}
                  fontSize={10}
                  fill={strokeColor}
                  textAnchor="start"
                  fontFamily="var(--font-mono, monospace)"
                  fontWeight="600"
                >
                  P{p.position}{" "}
                  {isRetirement ? (
                    <tspan fill="#f43f5e" fontSize="9" fontWeight="bold">
                      [{p.badge || "DNF"}]
                    </tspan>
                  ) : gained ? (
                    <tspan fontSize="9">▲ +{p.delta}</tspan>
                  ) : lost ? (
                    <tspan fontSize="9">▼ {p.delta}</tspan>
                  ) : (
                    <tspan fontSize="9" fill="var(--text-3)">— 0</tspan>
                  )}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </ChartShell>
  );
}
