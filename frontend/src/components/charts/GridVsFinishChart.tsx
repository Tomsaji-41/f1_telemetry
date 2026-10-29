"use client";

/**
 * GridVsFinishChart.tsx — Unified Grid vs Finish Slope Chart (Phase 3.1 & 3.2).
 * - Sized dynamically with ResizeObserver and min-height
 * - Driver team colour from useIdentity() (teammates dashed per Phase 2.5)
 * - Gained positions thicker with up-arrow (▲), lost with down-arrow (▼), neutral dash (—)
 * - Direct labels like "VER P3 -> P1 (+2)" at finish end
 * - Pit-lane starts and DNFs/DSQs shown accurately without invented positions
 * - Legend, hover inspection, Table and CSV download toggles via ChartShell
 * - Rendered client-only to ensure zero SSR hydration mismatch
 */
import React, { useState, useEffect, useRef, useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { ChartShell } from "./ChartShell";
import { useIdentity } from "@/lib/useIdentity";
import { useInspector } from "../layouts/inspector-drawer";

export interface SlopeRow {
  code: string;
  driver?: string;
  name?: string;
  team?: string;
  grid: number | null;
  finish: number | null;
  delta: number | null;
  status?: string;
  badge?: "DNF" | "DSQ" | null;
  is_dnf?: boolean;
  is_dsq?: boolean;
}

export interface GridVsFinishProps {
  data?: {
    status?: string;
    source?: string;
    coverage_note?: string;
    rows?: SlopeRow[];
    series?: SlopeRow[];
  } | null;
  d?: {
    rows?: SlopeRow[];
    series?: SlopeRow[];
  } | null;
  loading?: boolean;
}

export function GridVsFinishChart({ data, d, loading = false }: GridVsFinishProps): React.JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(580);
  const { getDriver, getDriverColor } = useIdentity();
  const { inspectItem } = useInspector();

  // ResizeObserver for dynamic container responsiveness
  useEffect(() => {
    if (!containerRef.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setContainerWidth(Math.max(340, Math.min(840, entry.contentRect.width)));
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const rawRows: SlopeRow[] = useMemo(() => {
    const input = data || d;
    if (input?.rows && Array.isArray(input.rows)) return input.rows;
    if (input?.series && Array.isArray(input.series)) return input.series;
    return [];
  }, [data, d]);

  const validRows = useMemo(() => {
    return rawRows.filter(
      (r) =>
        r.grid != null &&
        Number.isFinite(r.grid) &&
        r.finish != null &&
        Number.isFinite(r.finish)
    );
  }, [rawRows]);

  const W = containerWidth;
  const m = { l: 85, r: 130, t: 28, b: 24 };
  const maxPos = useMemo(() => {
    if (!validRows.length) return 20;
    return Math.max(20, ...validRows.map((r) => Math.max(r.grid || 1, r.finish || 1)));
  }, [validRows]);

  const H = Math.max(380, m.t + maxPos * 22 + m.b);

  const ys = useMemo(() => {
    return scaleLinear()
      .domain([1, maxPos])
      .range([m.t, H - m.b]);
  }, [maxPos, H, m.t, m.b]);

  const xLeft = m.l;
  const xRight = W - m.r;

  // Table rows and CSV data
  const tableRows = useMemo(() => {
    return validRows.map((r) => {
      const code = r.code || r.name || "DRV";
      const team = r.team || "Unknown";
      const grid = r.grid != null ? `P${r.grid}` : "Pit Lane";
      const finish = r.badge ? `${r.badge} (P${r.finish})` : `P${r.finish}`;
      let deltaStr = "0";
      if (r.badge) {
        deltaStr = r.badge;
      } else if (r.delta != null) {
        deltaStr = r.delta > 0 ? `+${r.delta}` : r.delta < 0 ? String(r.delta) : "0";
      }
      return [code, team, grid, finish, deltaStr];
    });
  }, [validRows]);

  const csvData = useMemo(() => {
    let csv = "Driver,Team,Grid,Finish,Delta\n";
    tableRows.forEach((row) => {
      csv += `${row.join(",")}\n`;
    });
    return csv;
  }, [tableRows]);

  const activeSource = (data as any)?.source || (d as any)?.source || "Jolpica";
  const coverageNote = (data as any)?.coverage_note || (d as any)?.coverage_note;

  return (
    <ChartShell
      title="Grid versus Finish (Slope Chart)"
      subtitle="Track position changes and places gained/lost from starting grid to chequered flag"
      source={activeSource}
      coverageNote={coverageNote}
      loading={loading}
      empty={!validRows.length}
      csvData={csvData}
      csvFilename="grid_vs_finish.csv"
      tableHeaders={["Driver", "Team", "Grid", "Finish", "Delta"]}
      tableRows={tableRows}
    >
      <div ref={containerRef} className="w-full overflow-x-auto min-h-[360px]">
        {validRows.length > 0 && (
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="w-full h-auto select-none"
            role="img"
            aria-label="Grid versus finish comparison slope chart"
          >
            {/* Column Header: Grid */}
            <text
              x={xLeft}
              y={14}
              fill="var(--text-3)"
              fontSize="11"
              textAnchor="middle"
              className="font-mono uppercase font-bold tracking-wider"
            >
              Start Grid
            </text>

            {/* Column Header: Finish */}
            <text
              x={xRight}
              y={14}
              fill="var(--text-3)"
              fontSize="11"
              textAnchor="middle"
              className="font-mono uppercase font-bold tracking-wider"
            >
              Finish
            </text>

            {/* Position Guide Lines */}
            {Array.from({ length: maxPos }, (_, i) => i + 1).map((p) => {
              const y = ys(p);
              if (!Number.isFinite(y)) return null;
              return (
                <g key={p}>
                  <line
                    x1={xLeft - 6}
                    x2={xRight + 6}
                    y1={y}
                    y2={y}
                    stroke="var(--border)"
                    strokeWidth={0.5}
                    strokeDasharray="2 3"
                    opacity={0.5}
                  />
                  <text
                    x={xLeft - 10}
                    y={y + 3}
                    fontSize={9}
                    fill="var(--text-3)"
                    textAnchor="end"
                    className="font-num"
                  >
                    P{p}
                  </text>
                </g>
              );
            })}

            {/* Slope Lines */}
            {validRows.map((r) => {
              const y1 = ys(r.grid!);
              const y2 = ys(r.finish!);
              if (!Number.isFinite(y1) || !Number.isFinite(y2)) return null;
              const isRetirement = Boolean(r.is_dnf || r.is_dsq || r.badge === "DNF" || r.badge === "DSQ");
              const drvIdentity = getDriver(r.code);
              const teamColor = drvIdentity?.teamColor || getDriverColor(r.code) || "var(--accent)";
              const strokeDash = isRetirement ? "4 3" : (drvIdentity?.strokeDash || undefined);
              const displayName = drvIdentity?.name || r.name || r.code;
              const teamName = drvIdentity?.team || r.team || "Unknown";

              let strokeWidth = 1.6;
              let indicatorSymbol = "—";
              let indicatorLabel = "0";
              let badgeColor = "var(--text-3)";

              if (isRetirement) {
                indicatorSymbol = r.badge || "DNF";
                indicatorLabel = "";
                badgeColor = "#f43f5e";
              } else if (r.delta != null && r.delta > 0) {
                strokeWidth = 2.2;
                indicatorSymbol = "▲";
                indicatorLabel = `+${r.delta}`;
                badgeColor = "#10b981";
              } else if (r.delta != null && r.delta < 0) {
                indicatorSymbol = "▼";
                indicatorLabel = `${r.delta}`;
                badgeColor = "#ef4444";
              }

              const directLabel = `${r.code} P${r.grid} → P${r.finish} (${indicatorLabel || indicatorSymbol})`;

              return (
                <g
                  key={r.code}
                  className="group cursor-pointer"
                  onClick={() => {
                    inspectItem({
                      type: "driver",
                      title: displayName,
                      subtitle: `Grid P${r.grid} → Finish P${r.finish}`,
                      details: {
                        Driver: displayName,
                        Team: teamName,
                        "Grid Position": `P${r.grid}`,
                        "Finish Position": isRetirement ? `${r.badge || "DNF"} (P${r.finish})` : `P${r.finish}`,
                        Delta: indicatorLabel || indicatorSymbol,
                      },
                      queryContext: `Analyze race performance for ${r.code}`,
                    });
                  }}
                >
                  {/* Slope line */}
                  <line
                    x1={xLeft}
                    y1={y1}
                    x2={xRight}
                    y2={y2}
                    stroke={teamColor}
                    strokeWidth={strokeWidth}
                    strokeDasharray={strokeDash}
                    opacity={0.8}
                    className="group-hover:stroke-width-[3.5px] group-hover:opacity-100 transition-all"
                  />

                  {/* Left Node (Grid) */}
                  <circle cx={xLeft} cy={y1} r={3} fill={teamColor} />
                  <text
                    x={xLeft - 12}
                    y={y1 + 3}
                    fill="var(--text-2)"
                    fontSize="10"
                    textAnchor="end"
                    className="font-mono font-semibold group-hover:fill-[var(--text)]"
                  >
                    {r.code}
                  </text>

                  {/* Right Node (Finish) */}
                  <circle cx={xRight} cy={y2} r={3} fill={teamColor} />

                  {/* Direct Label at Finish end */}
                  <text
                    x={xRight + 12}
                    y={y2 + 3}
                    fill={badgeColor}
                    fontSize="10"
                    textAnchor="start"
                    className="font-mono font-bold group-hover:underline"
                  >
                    {r.code} P{r.finish}{" "}
                    <tspan fontSize="9" fill={badgeColor} fontWeight="normal">
                      {isRetirement ? `[${r.badge || "DNF"}]` : `${indicatorSymbol} ${indicatorLabel}`}
                    </tspan>
                  </text>
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </ChartShell>
  );
}

// Re-export as SlopeChart for backward compatibility
export const SlopeChart = GridVsFinishChart;
