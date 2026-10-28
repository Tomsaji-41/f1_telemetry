"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Segmented } from "@/components/primitives/kit";
import { ChartPanel } from "@/components/charts/ChartPanel";
import { ChartState } from "@/components/charts/ChartState";
import { PositionByLapChart } from "@/components/charts/PositionByLapChart";
import { GapEvolutionChart } from "@/components/charts/GapEvolutionChart";
import { TyreStintGantt } from "@/components/charts/TyreStintGantt";
import { DegradationChart } from "@/components/charts/DegradationChart";
import { PitChart } from "@/components/charts/PitChart";
import { QualiGap } from "@/components/charts/QualiGap";
import { Heatmap } from "@/components/charts/Heatmap";
import { ChampionshipProgressionChart } from "@/components/charts/ChampionshipProgressionChart";
import Plot from "@/components/charts/Plot";
import en from "@/content/en.json";
import { fetcher } from "@/lib/api";
import { DEMO_MODE, DEMO_LABEL } from "@/demo/demoData";

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
  const currentYear = new Date().getFullYear();
  const year = parseInt(searchParams.get("year") || String(currentYear), 10);
  const round = parseInt(searchParams.get("round") || "1", 10);

  const [activeTab, setActiveTab] = useState<AnalyticsTab>("positions");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<any>(null);

  // For tyres tab: driver selection for degradation
  const [degDriver, setDegDriver] = useState<string>("VER");
  const [degData, setDegData] = useState<any>(null);

  const fetchData = () => {
    setLoading(true);
    setError(null);

    let endpoint = `/api/charts/position-by-lap?year=${year}&round=${round}`;
    if (activeTab === "positions") {
      endpoint = `/api/charts/position-by-lap?year=${year}&round=${round}`;
    } else if (activeTab === "pace") {
      endpoint = `/api/charts/gap-evolution?year=${year}&round=${round}`;
    } else if (activeTab === "tyres") {
      endpoint = `/api/charts/stints?year=${year}&round=${round}`;
    } else if (activeTab === "pitstops") {
      endpoint = `/api/charts/pit-stops?year=${year}&round=${round}`;
    } else if (activeTab === "sectors") {
      endpoint = `/api/charts/sector-heatmap?year=${year}&round=${round}`;
    } else if (activeTab === "qualifying") {
      endpoint = `/api/charts/quali-gap?year=${year}&round=${round}`;
    } else if (activeTab === "season") {
      endpoint = `/api/charts/championship-progression?year=${year}&kind=drivers`;
    } else if (activeTab === "weather") {
      endpoint = `/api/charts/weather?year=${year}&round=${round}`;
    }

    fetcher(endpoint)
      .then((resData) => {
        setData(resData);
        setLoading(false);
      })
      .catch((err) => {
        setError(err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchData();
  }, [activeTab, year, round]);

  // Fetch degradation when on tyres tab
  useEffect(() => {
    if (activeTab === "tyres") {
      fetcher(`/api/charts/degradation?year=${year}&round=${round}&driver=${degDriver}`)
        .then((d) => setDegData(d))
        .catch(() => setDegData(null));
    }
  }, [activeTab, year, round, degDriver]);

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
      {/* Demo badge banner */}
      {DEMO_MODE && (
        <div className="px-3 py-1.5 rounded text-xs font-mono bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center justify-between">
          <span>{DEMO_LABEL}</span>
          <span className="text-[11px] uppercase tracking-wider font-semibold">Offline Analytics</span>
        </div>
      )}

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
          <PositionByLapChart data={data} loading={loading} />
        )}

        {activeTab === "pace" && (
          <GapEvolutionChart data={data} loading={loading} />
        )}

        {activeTab === "tyres" && (
          <div className="space-y-6">
            <TyreStintGantt data={data} loading={loading} />

            {/* Tyre Degradation Panel */}
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
                    onClick={() => {
                      fetch(`/api/charts/degradation?year=${year}&round=${round}&driver=${degDriver}`)
                        .then((res) => res.json())
                        .then((d) => setDegData(d));
                    }}
                    className="px-2.5 py-0.5 text-[11px] font-mono bg-[var(--accent)] text-white rounded"
                  >
                    Load Driver
                  </button>
                </div>

                <ChartState
                  data={degData}
                  error={null}
                  isLoading={loading && !degData}
                  retry={fetchData}
                >
                  <DegradationChart d={degData || { stints: [] }} />
                </ChartState>
              </div>
            </ChartPanel>
          </div>
        )}

        {activeTab === "pitstops" && (
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
        )}

        {activeTab === "sectors" && (
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
        )}

        {activeTab === "qualifying" && (
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
        )}

        {activeTab === "season" && (
          <ChampionshipProgressionChart data={data} loading={loading} />
        )}

        {activeTab === "weather" && (
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
              {data?.rows?.length > 0 ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-4 text-[11px] font-mono">
                    <span className="text-rose-400">● Track Temp (°C)</span>
                    <span className="text-sky-400">● Air Temp (°C)</span>
                    {data.rain_bands?.length > 0 && (
                      <span className="text-amber-400">
                        🌧 Rain on laps:{" "}
                        {data.rain_bands.map((b: any) => `L${b.start_lap}-L${b.end_lap}`).join(", ")}
                      </span>
                    )}
                  </div>
                  <Plot
                    x={data.rows.map((r: any) => r.lap)}
                    ys={[
                      data.rows.map((r: any) => r.track_c),
                      data.rows.map((r: any) => r.air_c),
                    ]}
                    series={[
                      { label: "Track Temp", colour: "#f43f5e" },
                      { label: "Air Temp", colour: "#38bdf8" },
                    ]}
                    xLabel="Lap"
                    yLabel="Temperature (°C)"
                    height={220}
                    bands={
                      data.rain_bands?.length > 0
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
                  No weather observations recorded for this session.
                </div>
              )}
            </ChartState>
          </ChartPanel>
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
