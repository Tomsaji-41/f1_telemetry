"use client";

import React, { useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { ChartShell } from "./ChartShell";
import { useInspector } from "../layouts/inspector-drawer";

interface StandingProgressionItem {
  name: string;
  code: string;
  points: number;
  position: number;
}

interface ChampionshipProgressionProps {
  data: {
    status?: string;
    source?: string;
    coverage_note?: string;
    series?: StandingProgressionItem[];
  };
  loading?: boolean;
}

export function ChampionshipProgressionChart({
  data,
  loading = false,
}: ChampionshipProgressionProps) {
  const { inspectItem } = useInspector();
  const rawSeries = (data?.series || (data as any)?.standings || []) as StandingProgressionItem[];

  const width = 800;
  const height = 320;
  const margin = { top: 30, right: 40, bottom: 40, left: 60 };

  const maxPoints = useMemo(() => {
    let m = 100;
    rawSeries.forEach((s) => {
      const pts = Number(s.points) || 0;
      if (pts > m) m = pts;
    });
    return Math.ceil(m / 50) * 50;
  }, [rawSeries]);

  const xScale = useMemo(() => {
    return scaleLinear()
      .domain([0, Math.max(10, rawSeries.length)])
      .range([margin.left, width - margin.right]);
  }, [rawSeries, width]);

  const yScale = useMemo(() => {
    return scaleLinear()
      .domain([0, maxPoints])
      .range([height - margin.bottom, margin.top]);
  }, [maxPoints, height]);

  const csvData = useMemo(() => {
    let csv = "Driver,Code,Points,Position\n";
    rawSeries.forEach((s) => {
      const code = s.code || (s as any).id || "DRV";
      const name = s.name || code;
      const pts = Number(s.points) || 0;
      csv += `${name},${code},${pts},${s.position ?? ""}\n`;
    });
    return csv;
  }, [rawSeries]);

  const tableRows = useMemo(() => {
    return rawSeries.map((s) => {
      const code = s.code || (s as any).id || "DRV";
      const name = s.name || code;
      const pts = Number(s.points) || 0;
      return [name, code, `${pts} pts`, `P${s.position ?? "-"}`];
    });
  }, [rawSeries]);

  return (
    <ChartShell
      title="Championship Standings Progression"
      subtitle="Championship points total and rankings"
      source={data?.source || "Jolpica"}
      coverageNote={data?.coverage_note}
      loading={loading}
      empty={!rawSeries.length}
      csvData={csvData}
      csvFilename="championship_standings.csv"
      tableHeaders={["Driver", "Code", "Points", "Position"]}
      tableRows={tableRows}
    >
      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto select-none">
          {/* Y-axis Grid */}
          {[0, maxPoints * 0.25, maxPoints * 0.5, maxPoints * 0.75, maxPoints].map((pts) => {
            const y = yScale(pts);
            if (!Number.isFinite(y)) return null;
            return (
              <g key={pts}>
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
                  {Math.round(pts)}
                </text>
              </g>
            );
          })}

          {/* Points Bars for Top Competitors */}
          {rawSeries.map((s, idx) => {
            const code = s.code || (s as any).id || `D${idx + 1}`;
            const name = s.name || code;
            const pts = Number(s.points) || 0;
            const x = xScale(idx + 0.5);
            const y = yScale(pts);
            if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
            const barHeight = Math.max(2, height - margin.bottom - y);

            return (
              <g
                key={code}
                className="group cursor-pointer"
                onClick={() => {
                  inspectItem({
                    type: "driver",
                    title: name,
                    subtitle: `Championship P${s.position ?? idx + 1}`,
                    details: {
                      Championship: `P${s.position ?? idx + 1}`,
                      "Total Points": `${pts} pts`,
                    },
                    queryContext: `Summarize ${name}'s championship campaign`,
                  });
                }}
              >
                {/* Bar */}
                <rect
                  x={x - 14}
                  y={y}
                  width={28}
                  height={barHeight}
                  fill={idx === 0 ? "var(--d2)" : "var(--accent)"}
                  rx={2}
                  className="hover:opacity-85 transition-opacity"
                />
                {/* Points label */}
                <text
                  x={x}
                  y={y - 6}
                  fontSize={10}
                  fill="var(--text)"
                  textAnchor="middle"
                  fontFamily="var(--font-num)"
                  fontWeight="600"
                >
                  {pts}
                </text>
                {/* Code label */}
                <text
                  x={x}
                  y={height - margin.bottom + 16}
                  fontSize={10}
                  fill="var(--text-2)"
                  textAnchor="middle"
                  fontFamily="var(--font-num)"
                  fontWeight="bold"
                >
                  {code}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </ChartShell>
  );
}
