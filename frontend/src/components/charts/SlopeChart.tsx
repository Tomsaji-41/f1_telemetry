"use client";

/**
 * SlopeChart — Grid vs Finish slope chart (V7-3 C spec).
 * - Code on left end, position number on right end (never duplicate driver codes).
 * - Neutral dash and "0" for unchanged positions, never a down arrow.
 * - DNF / DSQ badges for classified-out drivers, excluded from gained/lost arrows.
 * - Colour is not the only signal: arrows (▲ / ▼ / —), numbers, badges, and aria-labels.
 */
import React from "react";
import { scaleLinear } from "d3-scale";

interface SlopeRow {
  code: string;
  name?: string;
  team?: string;
  grid: number | null;
  finish: number | null;
  delta: number | null;
  status: string;
  badge?: "DNF" | "DSQ" | null;
  is_dnf?: boolean;
  is_dsq?: boolean;
}

interface SlopeChartProps {
  d: {
    rows: SlopeRow[];
  };
}

export function SlopeChart({ d }: SlopeChartProps) {
  const rows = d?.rows || [];
  const valid = rows.filter((r) => r.grid != null && r.finish != null);
  if (!valid.length) return null;

  const W = 480;
  const m = { l: 70, r: 80, t: 24, b: 20 };
  const maxPos = Math.max(...valid.map((r) => Math.max(r.grid!, r.finish!)));
  const H = m.t + maxPos * 24 + m.b;

  const ys = scaleLinear()
    .domain([1, maxPos])
    .range([m.t, H - m.b]);

  const xLeft = m.l;
  const xRight = W - m.r;

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", maxWidth: 540, height: "auto" }}
        role="img"
        aria-label="Grid versus finish comparison slope chart"
      >
        {/* Column headers */}
        <text
          x={xLeft}
          y={12}
          fill="var(--text-3)"
          fontSize="10"
          textAnchor="middle"
          className="font-mono uppercase font-semibold"
        >
          Grid
        </text>
        <text
          x={xRight}
          y={12}
          fill="var(--text-3)"
          fontSize="10"
          textAnchor="middle"
          className="font-mono uppercase font-semibold"
        >
          Finish
        </text>

        {/* Position guide lines */}
        {Array.from({ length: maxPos }, (_, i) => i + 1).map((p) => (
          <line
            key={p}
            x1={xLeft - 6}
            x2={xRight + 6}
            y1={ys(p)}
            y2={ys(p)}
            stroke="var(--border)"
            strokeWidth={0.5}
            strokeDasharray="2 3"
            opacity={0.6}
          />
        ))}

        {valid.map((r) => {
          const y1 = ys(r.grid!);
          const y2 = ys(r.finish!);
          const isRetirement = r.is_dnf || r.is_dsq || r.badge === "DNF" || r.badge === "DSQ";

          let color = "var(--text-3)";
          let indicatorSymbol = "—";
          let indicatorLabel = "0";
          let ariaText = `${r.code}: started P${r.grid}, finished P${r.finish}, position unchanged`;

          if (isRetirement) {
            color = "#f43f5e"; // Rose/red for DNF/DSQ
            indicatorSymbol = r.badge || "DNF";
            indicatorLabel = "";
            ariaText = `${r.code}: started P${r.grid}, retired (${r.status || r.badge})`;
          } else if (r.delta != null) {
            if (r.delta > 0) {
              color = "#10b981"; // Emerald green
              indicatorSymbol = "▲";
              indicatorLabel = `+${r.delta}`;
              ariaText = `${r.code}: started P${r.grid}, finished P${r.finish}, gained ${r.delta} positions`;
            } else if (r.delta < 0) {
              color = "#ef4444"; // Red
              indicatorSymbol = "▼";
              indicatorLabel = `${r.delta}`;
              ariaText = `${r.code}: started P${r.grid}, finished P${r.finish}, lost ${Math.abs(r.delta)} positions`;
            } else {
              // Delta is 0 -> unchanged: show neutral dash and "0", NEVER down arrow
              color = "var(--text-3)";
              indicatorSymbol = "—";
              indicatorLabel = "0";
              ariaText = `${r.code}: started P${r.grid}, finished P${r.finish}, unchanged`;
            }
          }

          return (
            <g
              key={r.code}
              role="graphics-symbol"
              aria-label={ariaText}
              className="group cursor-default"
            >
              {/* Slope line */}
              <line
                x1={xLeft}
                y1={y1}
                x2={xRight}
                y2={y2}
                stroke={color}
                strokeWidth={1.5}
                strokeDasharray={isRetirement ? "4 3" : undefined}
                opacity={0.75}
                className="group-hover:stroke-width-[2.5px] group-hover:opacity-100 transition-all"
              />

              {/* Left node (Grid) */}
              <circle cx={xLeft} cy={y1} r={3} fill={color} />
              {/* Code ONLY on left end */}
              <text
                x={xLeft - 10}
                y={y1}
                fill="var(--text-2)"
                fontSize="10"
                textAnchor="end"
                dominantBaseline="central"
                fontFamily="var(--font-mono, monospace)"
                className="group-hover:fill-[var(--text)] font-semibold"
              >
                P{r.grid} {r.code}
              </text>

              {/* Right node (Finish) */}
              <circle cx={xRight} cy={y2} r={3} fill={color} />
              {/* Position and indicator on right end (NO duplicate driver code) */}
              <text
                x={xRight + 10}
                y={y2}
                fill={color}
                fontSize="10"
                textAnchor="start"
                dominantBaseline="central"
                fontFamily="var(--font-mono, monospace)"
                fontWeight="600"
              >
                P{r.finish}{" "}
                {isRetirement ? (
                  <tspan
                    fill="#f43f5e"
                    fontSize="9"
                    fontWeight="bold"
                  >
                    [{r.badge || "DNF"}]
                  </tspan>
                ) : (
                  <tspan fontSize="9">
                    {indicatorSymbol} {indicatorLabel}
                  </tspan>
                )}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
