"use client";

/**
 * Heatmap.tsx — Sector gap heatmap (B8).
 * Columns: S1, S2, S3, Ideal. Cell gap formatted as +0.123.
 * Background alpha scales with gap. Session best gets outline.
 */
import React, { useMemo } from "react";
import { scaleLinear } from "d3-scale";

interface SectorRow {
  code: string;
  s1_best_ms: number | null;
  s1_mean_ms: number | null;
  s1_gap_ms: number | null;
  s1_session_best: boolean;
  s2_best_ms: number | null;
  s2_mean_ms: number | null;
  s2_gap_ms: number | null;
  s2_session_best: boolean;
  s3_best_ms: number | null;
  s3_mean_ms: number | null;
  s3_gap_ms: number | null;
  s3_session_best: boolean;
  ideal_ms: number | null;
}

interface HeatmapProps {
  d: {
    rows: SectorRow[];
    drivers?: { code: string; colour: string; name: string }[];
  };
}

function formatGap(ms: number | null): string {
  if (ms == null) return "—";
  if (ms === 0) return "±0.000";
  return `+${(ms / 1000).toFixed(3)}`;
}

function formatMs(ms: number | null): string {
  if (ms == null) return "—";
  return (ms / 1000).toFixed(3);
}

export function Heatmap({ d }: HeatmapProps) {
  // Sort by ideal_ms ascending
  const sorted = useMemo(
    () =>
      [...d.rows].sort((a, b) => {
        if (a.ideal_ms == null && b.ideal_ms == null) return 0;
        if (a.ideal_ms == null) return 1;
        if (b.ideal_ms == null) return -1;
        return a.ideal_ms - b.ideal_ms;
      }),
    [d.rows]
  );

  // p90 of gaps for alpha scaling
  const allGaps = sorted.flatMap((r) =>
    [r.s1_gap_ms, r.s2_gap_ms, r.s3_gap_ms].filter(
      (v): v is number => v != null && v > 0
    )
  );
  const p90 = useMemo(() => {
    if (!allGaps.length) return 500;
    const s = [...allGaps].sort((a, b) => a - b);
    return s[Math.floor(s.length * 0.9)] || 500;
  }, [allGaps]);

  const alphaScale = scaleLinear()
    .domain([0, p90])
    .range([0, 0.6])
    .clamp(true);

  const sectors = [1, 2, 3] as const;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12px] border-collapse">
        <thead>
          <tr className="border-b border-[var(--border)]">
            <th className="py-2 px-3 text-left font-medium text-[var(--text-3)]">
              Driver
            </th>
            {sectors.map((s) => (
              <th
                key={s}
                className="py-2 px-3 text-center font-medium text-[var(--text-3)]"
              >
                S{s}
              </th>
            ))}
            <th className="py-2 px-3 text-center font-medium text-[var(--text-3)]">
              Ideal
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {sorted.map((row) => {
            const meta = d.drivers?.find((x) => x.code === row.code);
            return (
              <tr key={row.code} className="hover:bg-[var(--raised)]">
                <td className="py-1.5 px-3 font-mono text-[var(--text)]">
                  <span
                    className="inline-block w-2 h-2 rounded-full mr-1.5"
                    style={{
                      backgroundColor: meta?.colour || "var(--text-3)",
                    }}
                  />
                  {row.code}
                </td>
                {sectors.map((s) => {
                  const gap = row[`s${s}_gap_ms` as keyof SectorRow] as number | null;
                  const isBest = row[`s${s}_session_best` as keyof SectorRow] as boolean;
                  const alpha = gap != null && gap > 0 ? alphaScale(gap) : 0;

                  return (
                    <td
                      key={s}
                      className="py-1.5 px-3 text-center font-mono"
                      style={{
                        backgroundColor: isBest
                          ? "rgba(168,85,247,0.15)"
                          : `rgba(239,68,68,${alpha})`,
                        outline: isBest
                          ? "1.5px solid rgba(168,85,247,0.5)"
                          : undefined,
                        outlineOffset: -1,
                        color: isBest ? "rgb(168,85,247)" : "var(--text)",
                        fontWeight: isBest ? 600 : 400,
                      }}
                    >
                      {isBest ? formatMs(row[`s${s}_best_ms` as keyof SectorRow] as number | null) : formatGap(gap)}
                    </td>
                  );
                })}
                <td className="py-1.5 px-3 text-center font-mono text-[var(--text-2)]">
                  {row.ideal_ms != null ? formatMs(row.ideal_ms) : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
