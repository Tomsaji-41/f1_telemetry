"use client";

/**
 * TelemetryStack — Main race analysis page (B5).
 * Stacks all chart components for a given year/round.
 * Uses useChart for each endpoint, ChartState for status resolution,
 * and ChartPanel for consistent framing.
 */
import React, { useState, useMemo } from "react";
import { useChart } from "@/lib/useChart";
import { ChartState } from "./ChartState";
import { ChartPanel } from "./ChartPanel";
import { BumpChart } from "./BumpChart";
import { Gantt } from "./Gantt";
import { Heatmap } from "./Heatmap";
import { DegradationChart } from "./DegradationChart";
import { SlopeChart } from "./SlopeChart";
import { ProgressionChart } from "./ProgressionChart";
import { QualiGap } from "./QualiGap";
import { PitChart } from "./PitChart";
import Plot from "./Plot";

interface TelemetryStackProps {
  year: number;
  round: number;
  drivers?: string[];
}

export function TelemetryStack({ year, round, drivers }: TelemetryStackProps) {
  const [degDriver, setDegDriver] = useState<string | null>(null);

  // ── Data hooks ──────────────────────────────────────────────────────────
  const position = useChart<any>("position-by-lap", { year, round, drivers });
  const gap = useChart<any>("gap-evolution", { year, round, drivers });
  const scatter = useChart<any>("lap-scatter", { year, round, drivers });
  const stints = useChart<any>("stints", { year, round });
  const sectors = useChart<any>("sector-heatmap", { year, round });
  const weather = useChart<any>("weather", { year, round });
  const gridFinish = useChart<any>("grid-vs-finish", { year, round });
  const qualiGap = useChart<any>("quali-gap", { year, round });
  const pitStops = useChart<any>("pit-stops", { year, round });

  // Degradation: pick first driver from position data if none selected
  const defaultDegDriver = useMemo(() => {
    if (degDriver) return degDriver;
    const d = position.data?.drivers;
    return d?.[0]?.code || null;
  }, [degDriver, position.data]);

  const degradation = useChart<any>(
    defaultDegDriver ? "degradation" : null,
    { year, round, driver: defaultDegDriver }
  );

  // ── Scatter chart data transform ─────────────────────────────────────
  const scatterPlotData = useMemo(() => {
    if (!scatter.data?.points?.length) return null;
    const pts = scatter.data.points;
    const codes: string[] = Array.from(new Set(pts.map((p: any) => String(p.code))));
    const driverMeta = scatter.data.drivers || [];

    return {
      codes,
      drivers: driverMeta,
      byDriver: codes.map((code: string) => {
        const dp = pts.filter((p: any) => p.code === code);
        return {
          code,
          x: dp.map((p: any) => p.lap),
          y: dp.map((p: any) => p.t_s),
        };
      }),
    };
  }, [scatter.data]);

  // ── Gap chart data transform ─────────────────────────────────────────
  const gapPlotData = useMemo(() => {
    if (!gap.data?.series?.length || !gap.data?.x?.length) return null;
    const meta = gap.data.drivers || [];
    return {
      x: gap.data.x,
      ys: gap.data.series.map((s: any) => s.y),
      series: gap.data.series.map((s: any) => {
        const m = meta.find((d: any) => d.code === s.code);
        return {
          label: s.code,
          colour: m?.colour || "#A9A9BC",
          dash: m?.dash || false,
        };
      }),
    };
  }, [gap.data]);

  // ── Weather chart data transform ────────────────────────────────────
  const weatherPlotData = useMemo(() => {
    if (!weather.data?.rows?.length) return null;
    const rows = weather.data.rows;
    return {
      x: rows.map((r: any) => r.lap),
      airY: rows.map((r: any) => r.air_c),
      trackY: rows.map((r: any) => r.track_c),
      rainBits: rows.map((r: any) => (r.rain ? 1 : 0)),
    };
  }, [weather.data]);

  return (
    <div className="space-y-4">
      {/* ── Position by Lap ──────────────────────────────────────────── */}
      <ChartPanel
        title="Position by Lap"
        source={position.data?.source}
        fetchedAt={position.data?.fetched_at}
        coverageNote={position.data?.coverage_note}
      >
        <ChartState
          data={position.data}
          error={position.error}
          isLoading={position.isLoading}
          retry={position.retry}
        >
          {position.data?.status === "ok" && (
            <BumpChart d={position.data} />
          )}
        </ChartState>
      </ChartPanel>

      {/* ── Gap Evolution ────────────────────────────────────────────── */}
      <ChartPanel
        title="Gap to Leader"
        source={gap.data?.source}
        fetchedAt={gap.data?.fetched_at}
      >
        <ChartState
          data={gap.data}
          error={gap.error}
          isLoading={gap.isLoading}
          retry={gap.retry}
        >
          {gapPlotData && (
            <Plot
              x={gapPlotData.x}
              ys={gapPlotData.ys}
              series={gapPlotData.series}
              height={200}
              xLabel="Lap"
              yLabel="Gap (s)"
              invertY
              syncKey="race"
            />
          )}
        </ChartState>
      </ChartPanel>

      {/* ── Lap Scatter ──────────────────────────────────────────────── */}
      <ChartPanel
        title="Lap Times"
        source={scatter.data?.source}
        fetchedAt={scatter.data?.fetched_at}
      >
        <ChartState
          data={scatter.data}
          error={scatter.error}
          isLoading={scatter.isLoading}
          retry={scatter.retry}
        >
          {scatterPlotData && (
            <div className="space-y-1">
              {scatterPlotData.byDriver.map((drv: any) => {
                const meta = scatterPlotData.drivers.find(
                  (m: any) => m.code === drv.code
                );
                return (
                  <Plot
                    key={drv.code}
                    x={drv.x}
                    ys={[drv.y]}
                    series={[
                      {
                        label: drv.code,
                        colour: meta?.colour || "#A9A9BC",
                      },
                    ]}
                    height={80}
                    syncKey="race"
                  />
                );
              })}
            </div>
          )}
        </ChartState>
      </ChartPanel>

      {/* ── Tyre Stints ──────────────────────────────────────────────── */}
      <ChartPanel
        title="Tyre Strategy"
        source={stints.data?.source}
        fetchedAt={stints.data?.fetched_at}
      >
        <ChartState
          data={stints.data}
          error={stints.error}
          isLoading={stints.isLoading}
          retry={stints.retry}
        >
          {stints.data?.status === "ok" && <Gantt d={stints.data} />}
        </ChartState>
      </ChartPanel>

      {/* ── Degradation ──────────────────────────────────────────────── */}
      <ChartPanel
        title="Tyre Degradation"
        source={degradation.data?.source}
        fetchedAt={degradation.data?.fetched_at}
      >
        <div className="mb-2">
          {position.data?.drivers && (
            <div className="flex flex-wrap gap-1">
              {position.data.drivers.map((drv: any) => (
                <button
                  key={drv.code}
                  type="button"
                  onClick={() => setDegDriver(drv.code)}
                  className="px-2 py-0.5 text-[11px] font-mono rounded border hover:bg-[var(--raised)]"
                  style={{
                    borderColor:
                      defaultDegDriver === drv.code
                        ? drv.colour
                        : "var(--border)",
                    backgroundColor:
                      defaultDegDriver === drv.code
                        ? `${drv.colour}22`
                        : undefined,
                    color:
                      defaultDegDriver === drv.code
                        ? drv.colour
                        : "var(--text-2)",
                  }}
                >
                  {drv.code}
                </button>
              ))}
            </div>
          )}
        </div>
        <ChartState
          data={degradation.data}
          error={degradation.error}
          isLoading={degradation.isLoading}
          retry={degradation.retry}
        >
          {degradation.data?.status === "ok" && (
            <DegradationChart d={degradation.data} />
          )}
        </ChartState>
      </ChartPanel>

      {/* ── Sector Heatmap ───────────────────────────────────────────── */}
      <ChartPanel
        title="Sector Analysis"
        source={sectors.data?.source}
        fetchedAt={sectors.data?.fetched_at}
      >
        <ChartState
          data={sectors.data}
          error={sectors.error}
          isLoading={sectors.isLoading}
          retry={sectors.retry}
        >
          {sectors.data?.status === "ok" && <Heatmap d={sectors.data} />}
        </ChartState>
      </ChartPanel>

      {/* ── Weather ──────────────────────────────────────────────────── */}
      <ChartPanel
        title="Weather"
        source={weather.data?.source}
        fetchedAt={weather.data?.fetched_at}
      >
        <ChartState
          data={weather.data}
          error={weather.error}
          isLoading={weather.isLoading}
          retry={weather.retry}
        >
          {weatherPlotData && (
            <Plot
              x={weatherPlotData.x}
              ys={[weatherPlotData.airY, weatherPlotData.trackY]}
              series={[
                { label: "Air °C", colour: "#3b82f6" },
                { label: "Track °C", colour: "#ef4444" },
              ]}
              height={140}
              xLabel="Lap"
              yLabel="°C"
              syncKey="race"
              bands={[
                {
                  bits: weatherPlotData.rainBits,
                  colour: "rgba(59,130,246,0.08)",
                },
              ]}
            />
          )}
        </ChartState>
      </ChartPanel>

      {/* ── Grid vs Finish ───────────────────────────────────────────── */}
      <ChartPanel
        title="Grid vs Finish"
        source={gridFinish.data?.source}
        fetchedAt={gridFinish.data?.fetched_at}
      >
        <ChartState
          data={gridFinish.data}
          error={gridFinish.error}
          isLoading={gridFinish.isLoading}
          retry={gridFinish.retry}
        >
          {gridFinish.data?.status === "ok" && (
            <SlopeChart d={gridFinish.data} />
          )}
        </ChartState>
      </ChartPanel>

      {/* ── Qualifying Gap ───────────────────────────────────────────── */}
      <ChartPanel
        title="Qualifying Gaps"
        source={qualiGap.data?.source}
        fetchedAt={qualiGap.data?.fetched_at}
      >
        <ChartState
          data={qualiGap.data}
          error={qualiGap.error}
          isLoading={qualiGap.isLoading}
          retry={qualiGap.retry}
        >
          {qualiGap.data?.status === "ok" && <QualiGap d={qualiGap.data} />}
        </ChartState>
      </ChartPanel>

      {/* ── Pit Stops ────────────────────────────────────────────────── */}
      <ChartPanel
        title="Pit Stops"
        source={pitStops.data?.source}
        fetchedAt={pitStops.data?.fetched_at}
      >
        <ChartState
          data={pitStops.data}
          error={pitStops.error}
          isLoading={pitStops.isLoading}
          retry={pitStops.retry}
        >
          {pitStops.data?.status === "ok" && <PitChart d={pitStops.data} />}
        </ChartState>
      </ChartPanel>
    </div>
  );
}
