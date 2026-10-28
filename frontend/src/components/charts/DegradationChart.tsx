"use client";

/**
 * DegradationChart.tsx — Tyre degradation small multiples (B9).
 * One mini chart per stint. Dots from points, fitted line from slope.
 * Shows slope/R²/n caption and low-sample / fuel-corrected warnings.
 */
import React from "react";
import { scaleLinear } from "d3-scale";
import { t } from "@/lib/i18n";

const COMPOUND_COLORS: Record<string, string> = {
  SOFT: "#ff3333",
  MEDIUM: "#ffcc00",
  HARD: "#cccccc",
  INTERMEDIATE: "#44bb44",
  WET: "#3388ff",
};

interface StintData {
  stint: number;
  compound?: string;
  n: number;
  slope_s_per_lap: number | null;
  r2: number | null;
  points: { tyre_life: number; t_s: number }[];
  fuel_corrected?: boolean;
  low_sample?: boolean;
}

interface DegradationChartProps {
  d: {
    stints: StintData[];
    driver?: string;
  };
}

function MiniStint({ stint }: { stint: StintData }) {
  const W = 200;
  const H = 140;
  const m = { l: 40, r: 8, t: 8, b: 24 };

  const color = COMPOUND_COLORS[stint.compound?.toUpperCase() || ""] || "#888";
  const pts = stint.points || [];

  if (!pts.length || stint.slope_s_per_lap == null) {
    return (
      <div
        className="border border-[var(--border)] rounded p-3 flex flex-col items-center justify-center"
        style={{ width: W, minHeight: H }}
      >
        <div className="text-[10px] font-mono text-[var(--text-3)] mb-1">
          Stint {stint.stint} · {stint.compound || "?"} · n={stint.n}
        </div>
        <div className="text-[11px] text-[var(--text-2)]">
          {t("chart.degradation.noSlope")}
        </div>
      </div>
    );
  }

  const xs = pts.map((p) => p.tyre_life);
  const ys = pts.map((p) => p.t_s);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const yPad = (yMax - yMin) * 0.1 || 1;

  const xScale = scaleLinear()
    .domain([xMin, xMax])
    .range([m.l, W - m.r]);
  const yScale = scaleLinear()
    .domain([yMin - yPad, yMax + yPad])
    .range([H - m.b, m.t]);

  // Fitted line: y = slope * x + intercept
  const xMean = xs.reduce((a, b) => a + b, 0) / xs.length;
  const yMean = ys.reduce((a, b) => a + b, 0) / ys.length;
  const intercept = yMean - stint.slope_s_per_lap * xMean;
  const lineY0 = stint.slope_s_per_lap * xMin + intercept;
  const lineY1 = stint.slope_s_per_lap * xMax + intercept;

  return (
    <div className="border border-[var(--border)] rounded p-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "auto" }}
      >
        {/* Fitted line */}
        <line
          x1={xScale(xMin)}
          y1={yScale(lineY0)}
          x2={xScale(xMax)}
          y2={yScale(lineY1)}
          stroke={color}
          strokeWidth={1.5}
          strokeDasharray="4 3"
          opacity={0.7}
        />

        {/* Data points */}
        {pts.map((p, i) => (
          <circle
            key={i}
            cx={xScale(p.tyre_life)}
            cy={yScale(p.t_s)}
            r={3}
            fill={color}
            opacity={0.8}
          />
        ))}

        {/* Axes */}
        <line
          x1={m.l}
          y1={H - m.b}
          x2={W - m.r}
          y2={H - m.b}
          stroke="var(--border)"
        />
        <line
          x1={m.l}
          y1={m.t}
          x2={m.l}
          y2={H - m.b}
          stroke="var(--border)"
        />
      </svg>

      <div className="text-[10px] font-mono text-[var(--text-3)] mt-1 px-1">
        <span style={{ color }}>Stint {stint.stint} · {stint.compound}</span>
        {" · "}slope {stint.slope_s_per_lap.toFixed(4)} s/lap
        {stint.r2 != null && ` · R² ${stint.r2.toFixed(3)}`}
        {" · n="}
        {stint.n}
      </div>

      {stint.low_sample && (
        <div className="text-[10px] text-amber-500 mt-0.5 px-1">
          ⚠ {t("chart.degradation.lowSample")}
        </div>
      )}

      {stint.fuel_corrected && (
        <div className="text-[9px] text-[var(--text-3)] mt-0.5 px-1 italic">
          {t("chart.degradation.fuelNote")}
        </div>
      )}
    </div>
  );
}

export function DegradationChart({ d }: DegradationChartProps) {
  if (!d.stints?.length) {
    return (
      <div className="text-center text-[var(--text-2)] text-[13px] py-8">
        {t("chart.empty")}
      </div>
    );
  }

  return (
    <div>
      {d.driver && (
        <div className="text-[12px] font-mono text-[var(--text-2)] mb-2">
          {d.driver}
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        {d.stints.map((stint) => (
          <MiniStint key={stint.stint} stint={stint} />
        ))}
      </div>
    </div>
  );
}
