"use client";

/**
 * Gantt.tsx — Tyre strategy visualization (B7).
 * Rows ordered by d.order (finish position). Each stint is a coloured rect.
 * Compound mapped to CSS variables. Letter inside rect for colour-blind access.
 */
import React, { useState } from "react";
import { scaleLinear } from "d3-scale";

const COMPOUND_MAP: Record<string, { var: string; letter: string }> = {
  SOFT:         { var: "--tyre-soft",   letter: "S" },
  MEDIUM:       { var: "--tyre-medium", letter: "M" },
  HARD:         { var: "--tyre-hard",   letter: "H" },
  INTERMEDIATE: { var: "--tyre-inter",  letter: "I" },
  WET:          { var: "--tyre-wet",    letter: "W" },
};

const COMPOUND_COLORS: Record<string, string> = {
  SOFT:         "#ff3333",
  MEDIUM:       "#ffcc00",
  HARD:         "#cccccc",
  INTERMEDIATE: "#44bb44",
  WET:          "#3388ff",
};

function compoundColor(compound: string): string {
  return COMPOUND_COLORS[compound?.toUpperCase()] || "#888";
}

function compoundLetter(compound: string): string {
  return COMPOUND_MAP[compound?.toUpperCase()]?.letter || "?";
}

interface Stint {
  code: string;
  stint: number;
  compound: string;
  start_lap: number;
  end_lap: number;
  laps: number;
}

interface GanttProps {
  d: {
    stints: Stint[];
    order: string[];
    drivers?: { code: string; colour: string; name: string }[];
  };
}

export function Gantt({ d }: GanttProps) {
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    text: string;
  } | null>(null);

  const ROW_H = 22;
  const m = { l: 48, r: 16, t: 8, b: 24 };
  const maxLap = Math.max(1, ...d.stints.map((s) => s.end_lap));
  const W = 800;
  const H = m.t + d.order.length * ROW_H + m.b;

  const xs = scaleLinear()
    .domain([0, maxLap])
    .range([m.l, W - m.r]);

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "auto" }}
        role="img"
        aria-label="Tyre strategy chart"
      >
        {d.order.map((code, i) => {
          const y = m.t + i * ROW_H;
          const stints = d.stints.filter((s) => s.code === code);

          return (
            <g key={code}>
              <text
                x={m.l - 6}
                y={y + ROW_H / 2}
                fill="var(--text-2)"
                fontSize="10"
                textAnchor="end"
                dominantBaseline="middle"
                className="font-mono"
              >
                {code}
              </text>
              {stints.map((s) => {
                const x0 = xs(s.start_lap - 1);
                const x1 = xs(s.end_lap);
                const w = Math.max(2, x1 - x0);
                return (
                  <g key={s.stint}>
                    <rect
                      x={x0}
                      y={y + 2}
                      width={w}
                      height={ROW_H - 4}
                      rx={3}
                      fill={compoundColor(s.compound)}
                      opacity={0.85}
                      onMouseEnter={(e) =>
                        setTooltip({
                          x: e.clientX,
                          y: e.clientY,
                          text: `${code} · ${s.compound} · Laps ${s.start_lap}–${s.end_lap} (${s.laps})`,
                        })
                      }
                      onMouseLeave={() => setTooltip(null)}
                      style={{ cursor: "default" }}
                    />
                    {w > 16 && (
                      <text
                        x={x0 + w / 2}
                        y={y + ROW_H / 2}
                        fill="#000"
                        fontSize="9"
                        fontWeight="bold"
                        textAnchor="middle"
                        dominantBaseline="middle"
                        pointerEvents="none"
                      >
                        {compoundLetter(s.compound)}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}

        {/* X axis ticks */}
        {Array.from(
          { length: Math.min(maxLap, 20) },
          (_, i) => Math.round(((i + 1) / 20) * maxLap)
        )
          .filter((v, i, a) => a.indexOf(v) === i)
          .map((lap) => (
            <text
              key={lap}
              x={xs(lap)}
              y={H - 6}
              fill="var(--text-3)"
              fontSize="9"
              textAnchor="middle"
              className="font-mono"
            >
              {lap}
            </text>
          ))}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 px-2 py-1 text-[11px] font-mono bg-[var(--surface)] border border-[var(--border)] rounded shadow-lg text-[var(--text)]"
          style={{ left: tooltip.x + 12, top: tooltip.y - 20, pointerEvents: "none" }}
        >
          {tooltip.text}
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-2 mt-2 px-1">
        {Object.entries(COMPOUND_COLORS).map(([name, color]) => (
          <div
            key={name}
            className="flex items-center gap-1 text-[10px] font-mono text-[var(--text-3)]"
          >
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 2,
                backgroundColor: color,
                display: "inline-block",
              }}
            />
            {name}
          </div>
        ))}
      </div>
    </div>
  );
}
