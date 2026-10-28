"use client";

import React, { useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { ChartShell } from "./ChartShell";
import { useInspector } from "../layouts/inspector-drawer";

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
  }, [parsedGaps, width]);

  // Inverted Y so 0s (leader) is at the top
  const yScale = useMemo(() => {
    return scaleLinear()
      .domain([0, maxGap])
      .range([margin.top, height - margin.bottom]);
  }, [maxGap, height]);

  const csvData = useMemo(() => {
    let csv = "Driver,Position,Gap\n";
    rawSeries.forEach((s) => {
      csv += `${s.driver},${s.position},${s.gap}\n`;
    });
    return csv;
  }, [rawSeries]);

  const tableRows = useMemo(() => {
    return rawSeries.map((s) => [s.driver, `P${s.position}`, s.gap]);
  }, [rawSeries]);

  return (
    <ChartShell
      title="Gap to Leader Evolution"
      subtitle="Inverted delta time to winner (0.000s leader at top)"
      source={data?.source || "Jolpica"}
      coverageNote={data?.coverage_note}
      loading={loading}
      empty={!parsedGaps.length}
      csvData={csvData}
      csvFilename="gap_evolution.csv"
      tableHeaders={["Driver", "Position", "Gap to Leader"]}
      tableRows={tableRows}
    >
      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto select-none">
          {/* Y-axis grid lines (0s, 10s, 20s, ...) */}
          {[0, maxGap * 0.25, maxGap * 0.5, maxGap * 0.75, maxGap].map((gSec) => (
            <g key={gSec}>
              <line
                x1={margin.left}
                y1={yScale(gSec)}
                x2={width - margin.right}
                y2={yScale(gSec)}
                stroke="var(--border)"
                strokeWidth={0.8}
                strokeDasharray="2 2"
              />
              <text
                x={margin.left - 8}
                y={yScale(gSec) + 3}
                fontSize={10}
                fill="var(--text-3)"
                textAnchor="end"
                fontFamily="var(--font-num)"
              >
                {gSec === 0 ? "LEADER" : `+${gSec.toFixed(1)}s`}
              </text>
            </g>
          ))}

          {/* Stepped gap bars or line */}
          {parsedGaps.map((item, idx) => {
            const x = xScale(idx + 1);
            const y = yScale(item.gapSec);

            return (
              <g
                key={item.driver}
                className="group cursor-pointer"
                onClick={() => {
                  inspectItem({
                    type: "driver",
                    title: item.driver,
                    subtitle: `Position P${item.position}`,
                    details: {
                      Classification: `P${item.position}`,
                      "Gap to Winner": item.gap,
                    },
                    queryContext: `Explain the gap between the leader and ${item.driver}`,
                  });
                }}
              >
                {/* Vertical drop line to baseline */}
                <line
                  x1={x}
                  y1={yScale(0)}
                  x2={x}
                  y2={y}
                  stroke="var(--accent)"
                  strokeWidth={1.5}
                  strokeOpacity={0.7}
                />
                {/* Node point */}
                <circle
                  cx={x}
                  cy={y}
                  r={4}
                  fill="var(--accent)"
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
