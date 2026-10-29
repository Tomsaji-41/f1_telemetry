"use client";

/**
 * DegradationChart.tsx — Tyre degradation small multiples (B9).
 * One mini chart per stint. Dots from points, fitted line from slope.
 * Shows slope/R²/n caption and low-sample / fuel-corrected warnings.
 */
import React from "react";
import { scaleLinear } from "d3-scale";
import { t } from "@/lib/i18n";
import { useIdentity } from "@/lib/useIdentity";

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
  d?: {
    stints?: StintData[];
    driver?: string;
  };
}

function MiniStint({ stint }: { stint: StintData }) {
  const W = 200;
  const H = 140;
  const m = { l: 40, r: 8, t: 8, b: 24 };

  const color = COMPOUND_COLORS[stint.compound?.toUpperCase() || ""] || "#888";
  const pts = Array.isArray(stint.points) ? stint.points : [];

  if (!pts.length || stint.slope_s_per_lap == null || !Number.isFinite(stint.slope_s_per_lap)) {
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

  const xs = pts.map((p) => p.tyre_life).filter(Number.isFinite);
  const ys = pts.map((p) => p.t_s).filter(Number.isFinite);
  if (!xs.length || !ys.length) {
    return null;
  }

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

  // Fitted line endpoints
  const lineX1 = xMin;
  const lineX2 = xMax;
  const yMean = ys.reduce((a, b) => a + b, 0) / ys.length;
  const xMean = xs.reduce((a, b) => a + b, 0) / xs.length;
  const lineY1 = yMean + stint.slope_s_per_lap * (lineX1 - xMean);
  const lineY2 = yMean + stint.slope_s_per_lap * (lineX2 - xMean);

  const sx1 = xScale(lineX1);
  const sy1 = yScale(lineY1);
  const sx2 = xScale(lineX2);
  const sy2 = yScale(lineY2);

  return (
    <div
      className="border border-[var(--border)] rounded p-2 bg-[var(--surface-2)]"
      style={{ width: W }}
    >
      <svg width={W} height={H} className="overflow-visible">
        {/* Fitted line */}
        {Number.isFinite(sx1) && Number.isFinite(sy1) && Number.isFinite(sx2) && Number.isFinite(sy2) && (
          <line
            x1={sx1}
            y1={sy1}
            x2={sx2}
            y2={sy2}
            stroke={color}
            strokeWidth={1.5}
            strokeDasharray="4 2"
          />
        )}

        {/* Data points */}
        {pts.map((p, i) => {
          const cx = xScale(p.tyre_life);
          const cy = yScale(p.t_s);
          if (!Number.isFinite(cx) || !Number.isFinite(cy)) return null;
          return (
            <circle
              key={i}
              cx={cx}
              cy={cy}
              r={2.5}
              fill={color}
              opacity={0.7}
            />
          );
        })}
      </svg>

      <div className="text-[10px] font-mono text-[var(--text-3)] mt-1 px-1">
        <span style={{ color }}>Stint {stint.stint} · {stint.compound}</span>
        {" · "}slope {stint.slope_s_per_lap.toFixed(4)} s/lap
        {stint.r2 != null && Number.isFinite(stint.r2) && ` · R² ${stint.r2.toFixed(3)}`}
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
  const { getDriver, getDriverColor } = useIdentity();
  const stints = Array.isArray(d?.stints) ? d.stints : [];

  if (!stints.length) {
    return (
      <div className="text-center text-[var(--text-2)] text-[13px] py-8">
        {t("chart.empty")}
      </div>
    );
  }

  const drvMeta = d?.driver ? getDriver(d.driver) : undefined;
  const teamColor = drvMeta?.teamColor || (d?.driver ? getDriverColor(d.driver) : "var(--accent)");
  const displayName = drvMeta?.name ? `${drvMeta.name} (${d?.driver})` : d?.driver;

  return (
    <div>
      {displayName && (
        <div className="text-[12px] font-mono text-[var(--text-2)] mb-2 flex items-center gap-2">
          <span
            className="inline-block w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: teamColor }}
          />
          <span className="font-semibold text-[var(--text)]">{displayName}</span>
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        {stints.map((stint) => (
          <MiniStint key={stint.stint} stint={stint} />
        ))}
      </div>
    </div>
  );
}
