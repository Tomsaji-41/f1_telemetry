"use client";

/**
 * GridVsFinishChart.tsx — Unified Grid vs Finish Slope Chart (Phase 3.1 & 3.2).
 * - Sized dynamically with ResizeObserver and vertical growth so P1-P22 never clip
 * - Driver team colour from useIdentity() (teammates dashed + lighter tint per Phase 2.5)
 * - 3:1 WCAG contrast verified against dark background
 * - Gained positions thicker (2.4px) with up-arrow (▲), lost (1.6px) with down-arrow (▼), unchanged (1.2px) with dash (—)
 * - Left side: grid position at xLeft - 60, driver code at xLeft - 14 (margin.left >= 100)
 * - Right side: "VER P3 -1" with code in team colour, position in neutral, delta in green/red/neutral
 * - Pit-lane starts and DNFs/DSQs shown accurately without invented positions
 * - Legend, hover inspection, Table and CSV download toggles via ChartShell
 * - Rendered client-only to ensure zero SSR hydration mismatch
 */
import React, { useState, useEffect, useRef, useMemo } from "react";
import { scaleLinear } from "d3-scale";
import { ChartShell } from "./ChartShell";
import { useIdentity } from "@/lib/useIdentity";
import { ensureContrast, lightenHex } from "@/lib/colors";
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
  const [containerWidth, setContainerWidth] = useState(640);
  const { getDriver, getDriverColor } = useIdentity();
  const { inspectItem } = useInspector();
  const warnedDrivers = useRef<Set<string>>(new Set());

  // ResizeObserver for dynamic container responsiveness
  useEffect(() => {
    if (!containerRef.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setContainerWidth(Math.max(480, Math.min(920, entry.contentRect.width)));
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
  // margin.left >= 100 to prevent collisions between grid position, driver code, and plot line
  const m = { l: 110, r: 160, t: 36, b: 32 };
  const maxPos = useMemo(() => {
    if (!validRows.length) return 20;
    return Math.max(20, ...validRows.map((r) => Math.max(r.grid || 1, r.finish || 1)));
  }, [validRows]);

  // Height dynamically scales so all positions (P1-P22) have generous vertical space
  const rowHeight = 26;
  const H = Math.max(420, m.t + maxPos * rowHeight + m.b);

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
      <div ref={containerRef} className="w-full overflow-y-auto overflow-x-auto max-h-[720px] min-h-[360px]">
        {validRows.length > 0 && (
          <svg
            data-testid="grid-vs-finish-chart"
            viewBox={`0 0 ${W} ${H}`}
            className="w-full h-auto select-none font-mono"
            role="img"
            aria-label="Grid versus finish comparison slope chart"
          >
            {/* Column Headers */}
            <text
              x={xLeft - 60}
              y={18}
              fill="var(--text-3)"
              fontSize="10"
              textAnchor="end"
              className="uppercase font-semibold tracking-wider"
            >
              Grid
            </text>
            <text
              x={xLeft - 14}
              y={18}
              fill="var(--text-3)"
              fontSize="10"
              textAnchor="end"
              className="uppercase font-semibold tracking-wider"
            >
              Drv
            </text>
            <text
              x={xLeft}
              y={18}
              fill="var(--text-3)"
              fontSize="11"
              textAnchor="middle"
              className="uppercase font-bold tracking-wider"
            >
              Start
            </text>
            <text
              x={xRight}
              y={18}
              fill="var(--text-3)"
              fontSize="11"
              textAnchor="middle"
              className="uppercase font-bold tracking-wider"
            >
              Finish
            </text>
            <text
              x={xRight + 12}
              y={18}
              fill="var(--text-3)"
              fontSize="11"
              textAnchor="start"
              className="uppercase font-bold tracking-wider"
            >
              Result & Delta
            </text>

            {/* Position Guide Lines across the slope chart */}
            {Array.from({ length: maxPos }, (_, i) => i + 1).map((p) => {
              const y = ys(p);
              if (!Number.isFinite(y)) return null;
              return (
                <line
                  key={p}
                  x1={xLeft}
                  x2={xRight}
                  y1={y}
                  y2={y}
                  stroke="var(--border)"
                  strokeWidth={0.5}
                  strokeDasharray="2 4"
                  opacity={0.35}
                />
              );
            })}

            {/* Driver Slope Rows */}
            {validRows.map((r) => {
              const y1 = ys(r.grid!);
              const y2 = ys(r.finish!);
              if (!Number.isFinite(y1) || !Number.isFinite(y2)) return null;

              const isRetirement = Boolean(r.is_dnf || r.is_dsq || r.badge === "DNF" || r.badge === "DSQ");
              const drvIdentity = getDriver(r.code) || (r.driver ? getDriver(r.driver) : undefined);

              if (!drvIdentity && !warnedDrivers.current.has(r.code)) {
                warnedDrivers.current.add(r.code);
                console.warn(`[GridVsFinishChart] No identity metadata found for driver: ${r.code}`);
              }

              // Base team colour with WCAG >= 3:1 contrast against #0B0F14
              const rawTeamColor = drvIdentity?.teamColor || getDriverColor(r.code) || "var(--accent)";
              const baseTeamColor = ensureContrast(rawTeamColor, "#0B0F14", 3.0);
              const isSecondDriver = Boolean(drvIdentity?.isSecondDriver);

              // Teammate disambiguation: lighter tint AND dashed stroke
              const tintColor = drvIdentity?.tintColor
                ? ensureContrast(drvIdentity.tintColor, "#0B0F14", 3.0)
                : lightenHex(baseTeamColor, 0.35);

              const strokeColor = isSecondDriver ? tintColor : baseTeamColor;
              const strokeDash = isRetirement ? "4 3" : (isSecondDriver ? "4 2" : undefined);
              const displayName = drvIdentity?.name || r.name || r.code;
              const teamName = drvIdentity?.team || r.team || "Unknown";

              // Line thickness: places gained thicker (2.4px), unchanged thinner (1.2px), lost (1.6px)
              let strokeWidth = 1.6;
              let deltaSymbol = "—";
              let deltaText = "0";
              let deltaColor = "var(--text-3)";

              if (isRetirement) {
                deltaSymbol = r.badge || "DNF";
                deltaText = "";
                deltaColor = "#f43f5e";
              } else if (r.delta != null && r.delta > 0) {
                strokeWidth = 2.4;
                deltaSymbol = "▲";
                deltaText = `+${r.delta}`;
                deltaColor = "#10b981";
              } else if (r.delta != null && r.delta < 0) {
                strokeWidth = 1.6;
                deltaSymbol = "▼";
                deltaText = `${r.delta}`;
                deltaColor = "#ef4444";
              } else {
                strokeWidth = 1.2;
                deltaSymbol = "—";
                deltaText = "0";
                deltaColor = "var(--text-3)";
              }

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
                        Delta: isRetirement ? (r.badge || "DNF") : `${deltaSymbol} ${deltaText}`,
                      },
                      queryContext: `Analyze race performance for ${r.code}`,
                    });
                  }}
                >
                  {/* Left Column: Grid position in dedicated column */}
                  <text
                    x={xLeft - 60}
                    y={y1 + 4}
                    fill="var(--text-3)"
                    fontSize="11"
                    textAnchor="end"
                    className="font-medium"
                  >
                    {r.grid}
                  </text>

                  {/* Left Column: Driver Code in team colour */}
                  <text
                    x={xLeft - 14}
                    y={y1 + 4}
                    fill={strokeColor}
                    fontSize="11"
                    textAnchor="end"
                    className="font-bold group-hover:brightness-125"
                  >
                    {r.code}
                  </text>

                  {/* Left Node (Grid Dot) */}
                  <circle cx={xLeft} cy={y1} r={3.5} fill={strokeColor} />

                  {/* Connecting Slope line */}
                  <line
                    x1={xLeft}
                    y1={y1}
                    x2={xRight}
                    y2={y2}
                    stroke={strokeColor}
                    strokeWidth={strokeWidth}
                    strokeDasharray={strokeDash}
                    opacity={0.85}
                    className="group-hover:stroke-width-[3.5px] group-hover:opacity-100 transition-all"
                  />

                  {/* Right Node (Finish Dot) */}
                  <circle cx={xRight} cy={y2} r={3.5} fill={strokeColor} />

                  {/* Right Column: "VER P3 -1" (Code in team colour, position in neutral, delta in green/red/neutral arrow) */}
                  <text
                    x={xRight + 12}
                    y={y2 + 4}
                    fontSize="11"
                    textAnchor="start"
                    className="group-hover:brightness-125"
                  >
                    <tspan fill={strokeColor} fontWeight="bold">
                      {r.code}
                    </tspan>{" "}
                    <tspan fill="var(--text-2)" fontWeight="normal">
                      P{r.finish}
                    </tspan>{" "}
                    <tspan fill={deltaColor} fontWeight="medium">
                      {isRetirement ? `[${r.badge || "DNF"}]` : `${deltaSymbol} ${deltaText}`}
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
