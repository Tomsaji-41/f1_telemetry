"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { MessageSquare, Trophy, Award, Zap, Flag } from "lucide-react";
import { Panel, Stat, DataTable, EmptyState, Skeleton, ErrorState } from "@/components/primitives/kit";
import { RaceStoryScrollytelling } from "@/components/dashboard/RaceStoryScrollytelling";
import { TyreStintGantt } from "@/components/charts/TyreStintGantt";
import { ChampionshipProgressionChart } from "@/components/charts/ChampionshipProgressionChart";
import { GridVsFinishChart } from "@/components/charts/GridVsFinishChart";
import { CircuitCompactPanel } from "@/features/circuits/CircuitCompactPanel";
import { useInspector } from "@/components/layouts/inspector-drawer";
import { fetcher } from "@/lib/api";
import en from "@/content/en.json";

function DashboardContent(): React.JSX.Element {
  const searchParams = useSearchParams();
  const { inspectItem } = useInspector();

  const [raceData, setRaceData] = useState<any>(null);
  const [raceControlData, setRaceControlData] = useState<any[]>([]);
  const [positionData, setPositionData] = useState<any>(null);
  const [stintData, setStintData] = useState<any>(null);
  const [progressionData, setProgressionData] = useState<any>(null);
  const [gridData, setGridData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      try {
        setLoading(true);
        setError(null);

        // 1. Resolve year and round
        const currentYear = new Date().getFullYear();
        let targetYear = searchParams.get("year") ? parseInt(searchParams.get("year")!, 10) : currentYear;
        let targetRound = searchParams.get("round") ? parseInt(searchParams.get("round")!, 10) : null;

        if (!targetRound) {
          const schedRes = await fetcher<{ status: string; latest_completed_round: number; year: number }>(
            `/api/schedule?year=${targetYear}`
          ).catch(() => null);

          if (schedRes && schedRes.status === "ok") {
            targetRound = schedRes.latest_completed_round || 1;
            targetYear = schedRes.year || targetYear;
          } else {
            targetRound = 1;
          }
        }

        // 2. Critical path: fetch race classification & grid comparison first
        const [raceRes, gridRes, rcRes] = await Promise.all([
          fetcher(`/api/race?year=${targetYear}&round=${targetRound}`).catch(() => null),
          fetcher(`/api/charts/grid-vs-finish?year=${targetYear}&round=${targetRound}`).catch(() => null),
          fetcher(`/api/race-control?year=${targetYear}&round=${targetRound}`).catch(() => null),
        ]);

        if (!mounted) return;

        if (raceRes && raceRes.status === "ok") {
          setRaceData(raceRes);
        } else if (raceRes?.reason) {
          setError(raceRes.reason);
        }

        setGridData(gridRes);
        setRaceControlData(rcRes?.messages || []);
        setLoading(false); // Render dashboard immediately without waiting for heavy telemetry

        // 3. Stagger below-the-fold charts progressively so the event-loop / FastF1 loads do not contend
        fetcher(`/api/charts/position-by-lap?year=${targetYear}&round=${targetRound}`)
          .then((res) => mounted && setPositionData(res))
          .catch(() => null);

        fetcher(`/api/charts/stints?year=${targetYear}&round=${targetRound}`)
          .then((res) => mounted && setStintData(res))
          .catch(() => null);

        fetcher(`/api/charts/championship-progression?year=${targetYear}`)
          .then((res) => mounted && setProgressionData(res))
          .catch(() => null);
      } catch (err: any) {
        if (!mounted) return;
        setError(err.message || "Failed to load Grand Prix telemetry data.");
        setLoading(false);
      }
    }

    loadDashboard();

    return () => {
      mounted = false;
    };
  }, [searchParams]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-44 w-full rounded-lg" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-96 w-full rounded-lg" />
      </div>
    );
  }

  if (error || !raceData) {
    return (
      <ErrorState
        title="Dashboard Telemetry Offline"
        message={error || "Official race session data could not be retrieved from Jolpica."}
        source="Jolpica"
        onRetry={() => window.location.reload()}
      />
    );
  }

  const classification = raceData.classification || [];
  const winner = classification[0] || { driver: "Leader", team: "Formula 1", time: "" };
  const totalLaps = raceData.total_laps || (classification[0]?.laps ?? 0);
  const finishers = classification.filter((c: any) => c.status === "Finished" || c.status?.includes("Lap"));

  return (
    <div className="space-y-6">
      {/* Race Header Banner */}
      <section className="p-6 border border-[var(--border)] rounded-lg bg-[var(--surface)]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono uppercase text-[var(--accent)] font-semibold">
                FIA Formula 1 World Championship {raceData.year}
              </span>
              <span className="text-[var(--text-3)] text-[12px]">•</span>
              <span className="text-[11px] font-mono text-[var(--text-3)]">
                Round {raceData.round} — {raceData.circuit} ({totalLaps} Laps)
              </span>
            </div>
            <h1 className="text-[28px] font-semibold text-[var(--text)] tracking-tight mt-1">
              {raceData.race_name}
            </h1>
            <p className="text-[13px] text-[var(--text-2)] mt-0.5">
              Official race results & telemetry verified via Jolpica & FastF1
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => {
                const event = new KeyboardEvent("keydown", { key: "p" });
                window.dispatchEvent(event);
              }}
              className="flex items-center gap-2 px-3.5 py-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-[13px] font-medium rounded transition-colors"
              style={{ borderRadius: "var(--radius-s)" }}
            >
              <MessageSquare className="w-4 h-4" />
              <span>Ask Pit Boss</span>
            </button>
          </div>
        </div>

        {/* Quick KPI stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-6 mt-6 border-t border-[var(--border)]">
          <Stat
            label="Grand Prix Winner"
            value={winner.driver}
            unit={winner.team ? `(${winner.team})` : ""}
            delta="P1 Classification"
            deltaType="positive"
          />
          <Stat
            label="Total Race Laps"
            value={`${totalLaps} Laps`}
            unit={raceData.date || "Race Day"}
            delta="Official Race Distance"
            deltaType="neutral"
          />
          <Stat
            label="Classified Finishers"
            value={`${finishers.length} Cars`}
            unit={`of ${classification.length}`}
            delta="Final Classification"
            deltaType="neutral"
          />
          <Stat
            label="Data Synchronization"
            value="Official Verified"
            unit="Jolpica + FastF1"
            delta="Ground Truth Engine"
            deltaType="positive"
          />
        </div>
      </section>

      {/* Circuit Preview Panel (Phase K) */}
      <section>
        <CircuitCompactPanel
          circuitId={raceData.circuit_id || raceData.circuit}
          year={raceData.year}
          round={raceData.round}
        />
      </section>

      {/* Race Control & Pit Timeline + Position Chart */}
      <section>
        <RaceStoryScrollytelling
          positionData={positionData}
          raceControl={raceControlData}
          pitStops={raceData.pit_stops}
        />
      </section>

      {/* Grid vs Finish Slope Chart */}
      <section>
        <GridVsFinishChart data={gridData} loading={loading} />
      </section>

      {/* Strategy Gantt & Standings Progression Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section>
          <TyreStintGantt data={stintData} loading={loading} />
        </section>
        <section>
          <ChampionshipProgressionChart data={progressionData} loading={loading} />
        </section>
      </div>

      {/* Classification Table */}
      <section>
        <Panel
          title={en.dashboard.classification}
          subtitle={`Official verified classification for ${raceData.race_name} ${raceData.year}`}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-[var(--border)] text-[var(--text-3)]">
                <tr>
                  <th className="py-2.5 px-3 text-left">Pos</th>
                  <th className="py-2.5 px-3 text-left">Driver</th>
                  <th className="py-2.5 px-3 text-left">Constructor</th>
                  <th className="py-2.5 px-3 text-right">Grid</th>
                  <th className="py-2.5 px-3 text-right">Time / Gap</th>
                  <th className="py-2.5 px-3 text-right">Points</th>
                  <th className="py-2.5 px-3 text-right">Gain / Loss</th>
                  <th className="py-2.5 px-3 text-right">Fastest Lap</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)] font-mono">
                {classification.map((item: any) => {
                  const placesGained = item.places_gained ?? 0;
                  return (
                    <tr
                      key={item.code || item.driver}
                      className="hover:bg-[var(--raised)] transition-colors"
                      style={{ borderLeft: `3px solid ${item.team_color || "var(--accent)"}` }}
                    >
                      <td className="py-2 px-3 font-bold text-[var(--text)]">
                        P{item.position}
                      </td>
                      <td
                        className="py-2 px-3 font-sans font-semibold text-[var(--text)] cursor-pointer hover:underline"
                        onClick={() => {
                          inspectItem({
                            type: "driver",
                            title: item.driver,
                            subtitle: item.team,
                            details: {
                              "Finishing Position": `P${item.position}`,
                              "Starting Grid": `P${item.grid}`,
                              Points: String(item.points),
                              Status: item.status,
                              "Fastest Lap": item.fastest_lap || "-",
                            },
                            queryContext: `Detailed race breakdown for ${item.driver}`,
                          });
                        }}
                      >
                        {item.driver} <span className="text-[var(--text-3)] text-[11px]">({item.code})</span>
                      </td>
                      <td className="py-2 px-3 font-sans text-[var(--text-2)]">
                        {item.team}
                      </td>
                      <td className="py-2 px-3 text-right text-[var(--text-3)]">
                        P{item.grid}
                      </td>
                      <td className="py-2 px-3 text-right text-[var(--accent)] font-semibold">
                        {item.time}
                      </td>
                      <td className="py-2 px-3 text-right text-[var(--text)] font-bold">
                        {item.points}
                      </td>
                      <td
                        className={`py-2 px-3 text-right font-bold ${
                          placesGained > 0
                            ? "text-[var(--positive)]"
                            : placesGained < 0
                            ? "text-[var(--negative)]"
                            : "text-[var(--text-3)]"
                        }`}
                      >
                        {placesGained > 0 ? `+${placesGained}` : placesGained}
                      </td>
                      <td className="py-2 px-3 text-right text-[var(--text-2)]">
                        {item.fastest_lap || "-"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      </section>
    </div>
  );
}

export default function DashboardHub(): React.JSX.Element {
  return (
    <Suspense fallback={<div className="p-8 text-center text-sm font-mono text-[var(--text-3)]">Loading Dashboard...</div>}>
      <DashboardContent />
    </Suspense>
  );
}
