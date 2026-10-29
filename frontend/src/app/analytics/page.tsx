"use client";

import React, { useState, useEffect, Suspense, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { Segmented } from "@/components/primitives/kit";
import { ChartPanel } from "@/components/charts/ChartPanel";
import { ChartState } from "@/components/charts/ChartState";
import { PositionByLapChart } from "@/components/charts/PositionByLapChart";
import { SlopeChart } from "@/components/charts/SlopeChart";
import { GapEvolutionChart } from "@/components/charts/GapEvolutionChart";
import { TyreStintGantt } from "@/components/charts/TyreStintGantt";
import { DegradationChart } from "@/components/charts/DegradationChart";
import { PitChart } from "@/components/charts/PitChart";
import { QualiGap } from "@/components/charts/QualiGap";
import { Heatmap } from "@/components/charts/Heatmap";
import { ChampionshipProgressionChart } from "@/components/charts/ChampionshipProgressionChart";
import { ChartErrorBoundary } from "@/components/charts/ChartErrorBoundary";
import Plot from "@/components/charts/Plot";
import en from "@/content/en.json";
import { fetcher } from "@/lib/api";

type AnalyticsTab =
  | "positions"
  | "pace"
  | "tyres"
  | "pitstops"
  | "sectors"
  | "qualifying"
  | "season"
  | "weather";

function AnalyticsStudio(): React.JSX.Element {
  const searchParams = useSearchParams();
  const yearParam = searchParams.get("year");
  const roundParam = searchParams.get("round");
  const year = yearParam ? parseInt(yearParam, 10) : undefined;
  const round = roundParam ? parseInt(roundParam, 10) : undefined;

  const [activeTab, setActiveTab] = useState<AnalyticsTab>("positions");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<any>(null);

  // Secondary data for tabs with two charts
  const [gridData, setGridData] = useState<any>(null);
  const [gridLoading, setGridLoading] = useState(false);
  const [gridError, setGridError] = useState<any>(null);

  // For tyres tab: driver selection for degradation
  const [degDriver, setDegDriver] = useState<string>("VER");
  const [degData, setDegData] = useState<any>(null);
  const [degLoading, setDegLoading] = useState(false);

  const pollTimerRef = useRef<any>(null);
  const pollCountRef = useRef<number>(0);
  const maxPolls = 22; // ~45-50s

  const buildQuery = useCallback(
    (extra?: Record<string, any>) => {
      const q = new URLSearchParams();
      if (year) q.set("year", String(year));
      if (round) q.set("round", String(round));
      if (extra) {
        Object.entries(extra).forEach(([k, v]) => {
          if (v !== undefined && v !== null) q.set(k, String(v));
        });
      }
      const qs = q.toString();
      return qs ? `?${qs}` : "";
    },
    [year, round]
  );

  const getPrimaryEndpoint = useCallback(() => {
    switch (activeTab) {
      case "positions":
        return `/api/charts/position-by-lap${buildQuery()}`;
      case "pace":
        return `/api/charts/gap-evolution${buildQuery()}`;
      case "tyres":
        return `/api/charts/stints${buildQuery()}`;
      case "pitstops":
        return `/api/charts/pit-stops${buildQuery()}`;
      case "sectors":
        return `/api/charts/sector-heatmap${buildQuery()}`;
      case "qualifying":
        return `/api/charts/quali-gap${buildQuery()}`;
      case "season":
        return `/api/charts/championship-progression${buildQuery({ kind: "drivers" })}`;
      case "weather":
        return `/api/charts/weather${buildQuery()}`;
      default:
        return `/api/charts/position-by-lap${buildQuery()}`;
    }
  }, [activeTab, buildQuery]);

  const fetchData = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
    }
    pollCountRef.current = 0;
    setLoading(true);
    setError(null);

    const poll = async () => {
      try {
        const endpoint = getPrimaryEndpoint();
        const resData = await fetcher(endpoint);
        setData(resData);

        if (resData?.status === "preparing" && pollCountRef.current < maxPolls) {
          pollCountRef.current += 1;
          pollTimerRef.current = setTimeout(poll, 2200);
        } else {
          if (resData?.status === "preparing" && pollCountRef.current >= maxPolls) {
            setData({
              ...resData,
              status: "source_error",
              coverage_note: "Session data loading timed out after 45s. Please retry.",
            });
          }
          setLoading(false);
        }
      } catch (err) {
        setError(err);
        setLoading(false);
      }
    };

    poll();
  }, [getPrimaryEndpoint]);

  // Primary data fetch on tab/session change
  useEffect(() => {
    fetchData();
    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, [fetchData]);

  // Fetch Grid vs Finish for positions tab
  const fetchGridData = useCallback(() => {
    if (activeTab !== "positions") return;
    setGridLoading(true);
    setGridError(null);

    fetcher(`/api/charts/grid-vs-finish${buildQuery()}`)
      .then((res) => {
        setGridData(res);
        setGridLoading(false);
      })
      .catch((err) => {
        setGridError(err);
        setGridLoading(false);
      });
  }, [activeTab, buildQuery]);

  useEffect(() => {
    if (activeTab === "positions") {
      fetchGridData();
    }
  }, [activeTab, fetchGridData]);

  // Fetch degradation when on tyres tab
  const fetchDegradation = useCallback(() => {
    if (activeTab !== "tyres") return;
    setDegLoading(true);
    fetcher(`/api/charts/degradation${buildQuery({ driver: degDriver })}`)
      .then((d) => {
        setDegData(d);
        setDegLoading(false);
      })
      .catch(() => {
        setDegData(null);
        setDegLoading(false);
      });
  }, [activeTab, buildQuery, degDriver]);

  useEffect(() => {
    if (activeTab === "tyres") {
      fetchDegradation();
    }
  }, [activeTab, fetchDegradation]);

  const tabs = [
    { label: en.analytics.tabPositions, value: "positions" as AnalyticsTab },
    { label: en.analytics.tabPace, value: "pace" as AnalyticsTab },
    { label: en.analytics.tabTyres, value: "tyres" as AnalyticsTab },
    { label: en.analytics.tabPitStops, value: "pitstops" as AnalyticsTab },
    { label: en.analytics.tabSectors, value: "sectors" as AnalyticsTab },
    { label: en.analytics.tabQualifying, value: "qualifying" as AnalyticsTab },
    { label: en.analytics.tabSeason, value: "season" as AnalyticsTab },
    { label: "Weather", value: "weather" as AnalyticsTab },
  ];

  return (
    <div className="space-y-6">
      {/* Studio Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
        <div>
          <h1 className="text-[28px] font-semibold text-[var(--text)] tracking-tight">
            {en.analytics.title}
          </h1>
          <p className="text-[13px] text-[var(--text-3)] mt-0.5">
            Cross-session telemetry distribution, strategy Gantts, and sector benchmarks
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="overflow-x-auto pb-1 sm:pb-0">
          <Segmented
            options={tabs}
            value={activeTab}
            onChange={(tab) => setActiveTab(tab)}
          />
        </div>
      </div>

      {/* Tab Panels with ChartState & Smooth Fade-in */}
      <div key={activeTab} className="space-y-6 tab-panel-enter reveal">
        {activeTab === "positions" && (
          <div className="space-y-6">
            <ChartErrorBoundary chartName="Position By Lap">
              <PositionByLapChart data={data} loading={loading} />
            </ChartErrorBoundary>

            <ChartErrorBoundary chartName="Grid vs Finish">
              <ChartPanel
                title="Grid vs Finish (Position Changes)"
                source={gridData?.source || "Jolpica"}
                coverageNote={gridData?.coverage_note}
                fetchedAt={gridData?.fetched_at}
              >
                <ChartState
                  data={gridData}
                  error={gridError}
                  isLoading={gridLoading}
                  retry={fetchGridData}
                >
                  <SlopeChart d={gridData || { rows: [] }} />
                </ChartState>
              </ChartPanel>
            </ChartErrorBoundary>
          </div>
        )}

        {activeTab === "pace" && (
          <ChartErrorBoundary chartName="Gap Evolution">
            <GapEvolutionChart data={data} loading={loading} />
          </ChartErrorBoundary>
        )}

        {activeTab === "tyres" && (
          <div className="space-y-6">
            <ChartErrorBoundary chartName="Tyre Stint Gantt">
              <TyreStintGantt data={data} loading={loading} />
            </ChartErrorBoundary>

            {/* Tyre Degradation Panel */}
            <ChartErrorBoundary chartName="Tyre Degradation">
              <ChartPanel
                title="Tyre Degradation Analysis"
                source={degData?.source || "FastF1"}
                coverageNote={degData?.coverage_note}
                fetchedAt={degData?.fetched_at}
              >
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-[var(--text-3)]">Driver:</span>
                    <input
                      type="text"
                      value={degDriver}
                      onChange={(e) => setDegDriver(e.target.value.toUpperCase())}
                      className="w-16 px-2 py-0.5 text-[12px] font-mono bg-[var(--surface-2)] border border-[var(--border)] rounded text-[var(--text)] text-center uppercase"
                      maxLength={3}
                    />
                    <button
                      type="button"
                      onClick={fetchDegradation}
                      className="px-2.5 py-0.5 text-[11px] font-mono bg-[var(--accent)] text-white rounded hover:opacity-90 transition-opacity"
                    >
                      Load Driver
                    </button>
                  </div>

                  <ChartState
                    data={degData}
                    error={null}
                    isLoading={degLoading && !degData}
                    retry={fetchDegradation}
                  >
                    <DegradationChart d={degData || { stints: [] }} />
                  </ChartState>
                </div>
              </ChartPanel>
            </ChartErrorBoundary>
          </div>
        )}

        {activeTab === "pitstops" && (
          <ChartErrorBoundary chartName="Pit Stops">
            <ChartPanel
              title="Pit Stop Execution & Times"
              source={data?.source || "Jolpica"}
              coverageNote={data?.coverage_note}
              fetchedAt={data?.fetched_at}
            >
              <ChartState
                data={data}
                error={error}
                isLoading={loading}
                retry={fetchData}
              >
                <PitChart d={data || { stops: [] }} />
              </ChartState>
            </ChartPanel>
          </ChartErrorBoundary>
        )}

        {activeTab === "sectors" && (
          <ChartErrorBoundary chartName="Sector Heatmap">
            <ChartPanel
              title="Driver Sector Heatmap"
              source={data?.source || "FastF1"}
              coverageNote={data?.coverage_note}
              fetchedAt={data?.fetched_at}
            >
              <ChartState
                data={data}
                error={error}
                isLoading={loading}
                retry={fetchData}
              >
                <Heatmap d={data || { rows: [], sectors: ["S1", "S2", "S3"] }} />
              </ChartState>
            </ChartPanel>
          </ChartErrorBoundary>
        )}

        {activeTab === "qualifying" && (
          <ChartErrorBoundary chartName="Qualifying Benchmark">
            <ChartPanel
              title="Qualifying Stage Benchmark"
              source={data?.source || "Jolpica"}
              coverageNote={data?.coverage_note}
              fetchedAt={data?.fetched_at}
            >
              <ChartState
                data={data}
                error={error}
                isLoading={loading}
                retry={fetchData}
              >
                <QualiGap d={data || { rows: [] }} />
              </ChartState>
            </ChartPanel>
          </ChartErrorBoundary>
        )}

        {activeTab === "season" && (
          <ChartErrorBoundary chartName="Championship Progression">
            <ChampionshipProgressionChart data={data} loading={loading} />
          </ChartErrorBoundary>
        )}

        {activeTab === "weather" && (
          <ChartErrorBoundary chartName="Weather Conditions">
            <ChartPanel
              title="Track & Air Temperature with Rain Bands"
              source={data?.source || "FastF1"}
              coverageNote={data?.coverage_note}
              fetchedAt={data?.fetched_at}
            >
              <ChartState
                data={data}
                error={error}
                isLoading={loading}
                retry={fetchData}
              >
                {Array.isArray(data?.rows) && data.rows.length > 0 ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-4 text-[11px] font-mono">
                      <span className="text-rose-400">● Track Temp (°C)</span>
                      <span className="text-sky-400">● Air Temp (°C)</span>
                      {Array.isArray(data.rain_bands) && data.rain_bands.length > 0 && (
                        <span className="text-amber-400">
                          🌧 Rain on laps:{" "}
                          {data.rain_bands
                            .map((b: any) => `L${b.start_lap}-L${b.end_lap}`)
                            .join(", ")}
                        </span>
                      )}
                    </div>
                    <Plot
                      x={data.rows.map((r: any) => (typeof r.lap === "number" ? r.lap : 0))}
                      ys={[
                        data.rows.map((r: any) =>
                          typeof r.track_c === "number" && Number.isFinite(r.track_c)
                            ? r.track_c
                            : null
                        ),
                        data.rows.map((r: any) =>
                          typeof r.air_c === "number" && Number.isFinite(r.air_c)
                            ? r.air_c
                            : null
                        ),
                      ]}
                      series={[
                        { label: "Track Temp", colour: "#f43f5e" },
                        { label: "Air Temp", colour: "#38bdf8" },
                      ]}
                      xLabel="Lap"
                      yLabel="Temperature (°C)"
                      height={220}
                      bands={
                        Array.isArray(data.rain_bands) && data.rain_bands.length > 0
                          ? [
                              {
                                bits: data.rows.map((r: any) => (r.rain ? 1 : 0)),
                                colour: "rgba(56, 189, 248, 0.2)",
                              },
                            ]
                          : undefined
                      }
                    />
                  </div>
                ) : (
                  <div className="text-center py-8 text-[12px] text-[var(--text-3)] font-mono">
                    {data?.coverage_note || "No weather observations recorded for this session."}
                  </div>
                )}
              </ChartState>
            </ChartPanel>
          </ChartErrorBoundary>
        )}
      </div>
    </div>
  );
}

export default function AnalyticsPage(): React.JSX.Element {
  return (
    <Suspense fallback={<div className="p-8 text-center text-[12px] font-mono text-[var(--text-3)]">Loading analytics studio...</div>}>
      <AnalyticsStudio />
    </Suspense>
  );
}
