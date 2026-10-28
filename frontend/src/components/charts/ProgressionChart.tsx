"use client";

/**
 * ProgressionChart — Championship points progression over rounds (B11).
 * uPlot line chart with end labels and driver toggle chips.
 */
import React, { useMemo, useState } from "react";
import Plot, { type PlotSeries } from "./Plot";

interface ProgressionChartProps {
  d: {
    x: number[];
    series: { id: string; y: (number | null)[] }[];
    rounds?: string[];
    axes?: { x?: { label?: string }; y?: { label?: string } };
  };
}

const COLORS = [
  "#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#a855f7",
  "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16",
  "#06b6d4", "#e11d48", "#8b5cf6", "#0ea5e9", "#d946ef",
];

export function ProgressionChart({ d }: ProgressionChartProps) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const visibleSeries = useMemo(
    () => d.series.filter((s) => !hidden.has(s.id)),
    [d.series, hidden]
  );

  const plotSeries: PlotSeries[] = useMemo(
    () =>
      visibleSeries.map((s, i) => ({
        label: s.id,
        colour: COLORS[i % COLORS.length],
      })),
    [visibleSeries]
  );

  const ys = useMemo(
    () =>
      visibleSeries.map((s) =>
        s.y.map((v) => (v == null ? null : v))
      ),
    [visibleSeries]
  );

  const toggle = (id: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div>
      <Plot
        x={d.x}
        ys={ys}
        series={plotSeries}
        height={280}
        xLabel={d.axes?.x?.label || "Round"}
        yLabel={d.axes?.y?.label || "Points"}
        syncKey="champ"
      />
      <div className="flex flex-wrap gap-1.5 mt-2">
        {d.series.map((s, i) => (
          <button
            key={s.id}
            type="button"
            onClick={() => toggle(s.id)}
            className="flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono rounded border border-[var(--border)] hover:bg-[var(--raised)]"
            style={{
              opacity: hidden.has(s.id) ? 0.35 : 1,
              borderColor: COLORS[i % COLORS.length],
            }}
          >
            <span
              style={{
                width: 10,
                height: 3,
                backgroundColor: COLORS[i % COLORS.length],
                display: "inline-block",
                borderRadius: 1,
              }}
            />
            {s.id}
          </button>
        ))}
      </div>
    </div>
  );
}
