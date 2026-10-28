"use client";

/**
 * BumpChart — SVG position-by-lap chart (B6).
 * P1 on top (inverted y axis). Smooth bump lines with d3 helpers.
 * Hover dims other lines, click legend to toggle visibility.
 */
import React, { useState, useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { line, curveMonotoneX } from "d3-shape";
import { t } from "@/lib/i18n";

interface BumpChartProps {
  d: {
    x: number[];
    series: { code: string; y: (number | null)[] }[];
    drivers: { code: string; name: string; team: string | null; colour: string; dash: boolean }[];
    annotations?: { type: string; lap_start: number; lap_end: number; label: string }[];
  };
  height?: number;
}

function lastValue(arr: (number | null)[]): number {
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i] != null) return arr[i]!;
  }
  return 1;
}

export function BumpChart({ d, height = 420 }: BumpChartProps) {
  const [hover, setHover] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const W = 960;
  const m = { l: 44, r: 52, t: 16, b: 32 };

  const n = useMemo(
    () =>
      Math.max(
        1,
        ...d.series.flatMap((s) =>
          s.y.filter((v): v is number => v != null)
        )
      ),
    [d.series]
  );

  const xs = scaleLinear()
    .domain([d.x[0], d.x[d.x.length - 1]])
    .range([m.l, W - m.r]);

  const ys = scaleLinear()
    .domain([1, n])
    .range([m.t, height - m.b]);

  const pathGen = line<number | null>()
    .defined((v) => v != null)
    .curve(curveMonotoneX);

  const toggleHidden = (code: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${height}`}
        role="img"
        aria-label={t("chart.bump.aria")}
        style={{ width: "100%", height: "auto" }}
      >
        {/* Annotation bands */}
        {d.annotations
          ?.filter((a) => a.type !== "pit")
          .map((a, i) => (
            <rect
              key={i}
              x={xs(a.lap_start)}
              width={Math.max(2, xs(a.lap_end + 1) - xs(a.lap_start))}
              y={m.t}
              height={height - m.t - m.b}
              fill={
                a.type === "red"
                  ? "rgba(239,68,68,0.12)"
                  : "rgba(128,128,128,0.07)"
              }
              rx={2}
            >
              <title>{a.label}</title>
            </rect>
          ))}

        {/* Gridlines */}
        {Array.from({ length: n }, (_, i) => i + 1).map((p) => (
          <line
            key={p}
            x1={m.l}
            x2={W - m.r}
            y1={ys(p)}
            y2={ys(p)}
            stroke="var(--border)"
            strokeWidth={0.5}
          />
        ))}

        {/* Driver lines */}
        {d.series
          .filter((s) => !hidden.has(s.code))
          .map((s) => {
            const meta = d.drivers.find((x) => x.code === s.code);
            if (!meta) return null;
            const dim = hover && hover !== s.code;

            const pathData =
              pathGen
                .x((_, i) => xs(d.x[i]))
                .y((v) => ys(v as number))(s.y) || "";

            return (
              <g
                key={s.code}
                onMouseEnter={() => setHover(s.code)}
                onMouseLeave={() => setHover(null)}
                opacity={dim ? 0.18 : 1}
                style={{ transition: "opacity 0.15s" }}
              >
                <path
                  d={pathData}
                  fill="none"
                  stroke={meta.colour}
                  strokeWidth={hover === s.code ? 3 : 1.6}
                  strokeDasharray={meta.dash ? "6 4" : undefined}
                />
                <text
                  x={W - m.r + 6}
                  y={ys(lastValue(s.y))}
                  fill={meta.colour}
                  fontSize="11"
                  dominantBaseline="middle"
                  className="font-mono"
                >
                  {s.code}
                </text>
              </g>
            );
          })}

        {/* X axis labels */}
        {d.x
          .filter((_, i) => i % Math.ceil(d.x.length / 15) === 0 || i === d.x.length - 1)
          .map((v) => (
            <text
              key={v}
              x={xs(v)}
              y={height - 8}
              fill="var(--text-3)"
              fontSize="10"
              textAnchor="middle"
              className="font-mono"
            >
              {v}
            </text>
          ))}

        {/* Y axis labels */}
        {Array.from({ length: Math.min(n, 20) }, (_, i) => i + 1).map((p) => (
          <text
            key={p}
            x={m.l - 8}
            y={ys(p)}
            fill="var(--text-3)"
            fontSize="10"
            textAnchor="end"
            dominantBaseline="middle"
            className="font-mono"
          >
            {p}
          </text>
        ))}
      </svg>

      {/* Legend chips */}
      <div className="flex flex-wrap gap-1.5 mt-2 px-1">
        {d.drivers.map((drv) => (
          <button
            key={drv.code}
            type="button"
            onClick={() => toggleHidden(drv.code)}
            className="flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono rounded border border-[var(--border)] hover:bg-[var(--raised)]"
            style={{
              opacity: hidden.has(drv.code) ? 0.35 : 1,
              borderColor: drv.colour,
            }}
          >
            <span
              style={{
                width: 12,
                height: 3,
                backgroundColor: drv.colour,
                borderRadius: 1,
                display: "inline-block",
                borderTop: drv.dash ? `2px dashed ${drv.colour}` : undefined,
              }}
            />
            {drv.code}
          </button>
        ))}
      </div>
    </div>
  );
}
