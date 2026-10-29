"use client";

import React, { useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { ChartShell } from "./ChartShell";
import { useInspector } from "../layouts/inspector-drawer";
import { useIdentity } from "@/lib/useIdentity";

interface GapItem {
  driver: string;
  position: number;
  gap: string;
}

interface GapEvolutionProps {
  data: {
    status?: string;
    source?: string;
    coverage_note?: string;
    series?: GapItem[];
  };
  loading?: boolean;
}

export function GapEvolutionChart({ data, loading = false }: GapEvolutionProps) {
  const { inspectItem } = useInspector();
  const { getDriver, getDriverColor } = useIdentity();
  const rawSeries = data?.series || [];

  const width = 800;
  const height = 300;
  const margin = { top: 25, right: 30, bottom: 40, left: 60 };

  const parsedGaps = useMemo(() => {
    return rawSeries.map((s) => {
      let num = 0;
      if (s.gap && s.gap.startsWith("+")) {
        const clean = s.gap.replace("+", "").replace("s", "").trim();
        num = parseFloat(clean) || 0;
      }
      return {
        ...s,
        gapSec: num,
      };
    });
  }, [rawSeries]);

  const maxGap = useMemo(() => {
    let m = 30;
    parsedGaps.forEach((g) => {
      if (g.gapSec > m) m = g.gapSec;
    });
    return Math.ceil(m / 10) * 10;
  }, [parsedGaps]);

  const xScale = useMemo(() => {
    return scaleLinear()
      .domain([1, Math.max(10, parsedGaps.length)])
      .range([margin.left, width - margin.right]);
  }, [parsedGaps, width, margin.left, margin.right]);

  // Inverted Y so 0s (leader) is at the top
  const yScale = useMemo(() => {
    return scaleLinear()
      .domain([0, maxGap])
      .range([margin.top, height - margin.bottom]);
  }, [maxGap, height, margin.top, margin.bottom]);

  const csvData = useMemo(() => {
    let csv = "Driver,DriverName,Position,Gap\n";
    rawSeries.forEach((s) => {
      const drv = getDriver(s.driver);
      const name = drv?.name || s.driver;
      csv += `${s.driver},"${name}",${s.position},${s.gap}\n`;
    });
    return csv;
  }, [rawSeries, getDriver]);

  const tableRows = useMemo(() => {
    return rawSeries.map((s) => {
      const drv = getDriver(s.driver);
      const name = drv?.name || s.driver;
      return [s.driver, name, `P${s.position}`, s.gap];
    });
  }, [rawSeries, getDriver]);

  return (
    <ChartShell
      title="Race Gap Evolution (Finish Interval)"
      subtitle="Gap to race leader across all classified finishers"
      source={data?.source || "Jolpica"}
      coverageNote={data?.coverage_note}
      loading={loading}
      empty={!parsedGaps.length}
      csvData={csvData}
      csvFilename="gap_evolution.csv"
      tableHeaders={["Code", "Driver", "Position", "Gap to Winner"]}
      tableRows={tableRows}
    >
      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto select-none">
          {/* Y-axis Grid */}
          {[0, maxGap * 0.25, maxGap * 0.5, maxGap * 0.75, maxGap].map((gap) => {
            const y = yScale(gap);
            if (!Number.isFinite(y)) return null;
            return (
              <g key={gap}>
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
                  {gap === 0 ? "Leader" : `+${Math.round(gap)}s`}
                </text>
              </g>
            );
          })}

          {/* Stems & points */}
          {parsedGaps.map((item, idx) => {
            const x = xScale(idx + 1);
            const y = yScale(item.gapSec);
            if (!Number.isFinite(x) || !Number.isFinite(y)) return null;

            const drvMeta = getDriver(item.driver);
            const color = drvMeta?.teamColor || getDriverColor(item.driver) || "var(--accent)";
            const displayName = drvMeta?.name || item.driver;

            return (
              <g
                key={item.driver}
                className="group cursor-pointer"
                onClick={() => {
                  inspectItem({
                    type: "driver",
                    title: displayName,
                    subtitle: `Position P${item.position}`,
                    details: {
                      Driver: displayName,
                      Team: drvMeta?.team || "Unknown",
                      Classification: `P${item.position}`,
                      "Gap to Winner": item.gap,
                    },
                    queryContext: `Explain the gap between the leader and ${displayName}`,
                  });
                }}
              >
                {/* Vertical drop line to baseline */}
                <line
                  x1={x}
                  y1={yScale(0)}
                  x2={x}
                  y2={y}
                  stroke={color}
                  strokeWidth={1.5}
                  strokeOpacity={0.7}
                />
                {/* Node point */}
                <circle
                  cx={x}
                  cy={y}
                  r={4}
                  fill={color}
                  stroke="var(--surface)"
                  strokeWidth={1.5}
                  className="group-hover:r-6 transition-all"
                />
                {/* Driver code label */}
                <text
                  x={x}
                  y={height - margin.bottom + 16}
                  fontSize={10}
                  fontWeight="600"
                  fill="var(--text-2)"
                  textAnchor="middle"
                  fontFamily="var(--font-num)"
                >
                  {item.driver}
                </text>
                {/* Gap value badge */}
                <text
                  x={x}
                  y={y - 8}
                  fontSize={9}
                  fill="var(--text-3)"
                  textAnchor="middle"
                  fontFamily="var(--font-num)"
                >
                  {item.gap}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </ChartShell>
  );
}
