"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { MessageSquare, Trophy, Award, Zap, Flag } from "lucide-react";
import { Panel, Stat, DataTable, EmptyState, Skeleton } from "@/components/primitives/kit";
import { RaceStoryScrollytelling } from "@/components/dashboard/RaceStoryScrollytelling";
import { TyreStintGantt } from "@/components/charts/TyreStintGantt";
import { ChampionshipProgressionChart } from "@/components/charts/ChampionshipProgressionChart";
import { GridVsFinishChart } from "@/components/charts/GridVsFinishChart";
import { useInspector } from "@/components/layouts/inspector-drawer";
import {
  DEMO_RACE,
  DEMO_LABEL,
  SEASON_LABEL,
  STANDINGS_DRIVERS,
  STANDINGS_CONSTRUCTORS,
  COMPOUND_COLOR,
  getRace,
  sectorTable,
  fmtLap,
} from "@/demo/demoData";
import en from "@/content/en.json";

function DashboardHub(): React.JSX.Element {
  const searchParams = useSearchParams();
  const { inspectItem } = useInspector();

  const race = getRace();
  const sectors = sectorTable();
  const classification = race.classification;
  const winner = classification[0];

  const [positionData, setPositionData] = useState<any>(null);
  const [stintData, setStintData] = useState<any>(null);
  const [progressionData, setProgressionData] = useState<any>(null);
  const [gridData, setGridData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // In demo mode, fetchApi returns demo data immediately
    Promise.all([
      fetch(`/api/charts/position-by-lap`).then((r) => r.json()).catch(() => ({})),
      fetch(`/api/charts/stints`).then((r) => r.json()).catch(() => ({})),
      fetch(`/api/charts/championship-progression`).then((r) => r.json()).catch(() => ({})),
      fetch(`/api/charts/grid-vs-finish`).then((r) => r.json()).catch(() => ({})),
    ]).then(([pos, stints, prog, grid]) => {
      setPositionData(pos);
      setStintData(stints);
      setProgressionData(prog);
      setGridData(grid);
    });
  }, []);

  return (
    <div className="space-y-6">
      {/* Race Header Banner */}
      <section className="p-6 border border-[var(--border)] rounded-lg bg-[var(--surface)]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono uppercase text-[var(--accent)] font-semibold">
                Formula 1 Demo Championship
              </span>
              <span className="text-[var(--text-3)] text-[12px]">•</span>
              <span className="text-[11px] font-mono text-[var(--text-3)]">
                {DEMO_RACE.name} — {DEMO_RACE.circuit} ({DEMO_RACE.laps} Laps)
              </span>
            </div>
            <h1 className="text-[28px] font-semibold text-[var(--text)] tracking-tight mt-1">
              {DEMO_RACE.name} Dashboard
            </h1>
            <p className="text-[13px] text-[var(--text-2)] mt-0.5">
              {DEMO_LABEL}
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
            label="Chequered Flag Winner"
            value={winner.name}
            unit={`(${winner.team})`}
            delta="P1 Classification"
            deltaType="positive"
          />
          <Stat
            label="Total Race Laps"
            value={`${DEMO_RACE.laps} Laps`}
            unit="5.0 km"
            delta="Grand Prix Distance"
            deltaType="neutral"
          />
          <Stat
            label="Lead Lap Finishers"
            value={`${classification.filter((c) => c.status === "Finished").length} Cars`}
            unit="of 10"
            delta="Verified Gaps"
            deltaType="neutral"
          />
          <Stat
            label="Data Synchronization"
            value="Illustrative Sample"
            unit="Demo Engine"
            delta="14:00 UTC"
            deltaType="neutral"
          />
        </div>
      </section>

      {/* Sector Strip: Session Best S1, S2, S3 with holders */}
      <section className="p-4 border border-[var(--border)] rounded-lg bg-[var(--surface)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
          <span className="text-xs font-mono uppercase tracking-wider text-[var(--text-3)] font-semibold">
            Track Sector Benchmark
          </span>
          <span className="text-[11px] font-mono text-[var(--text-3)]">
            Purples indicate session-best sector benchmarks
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-3 bg-[var(--raised)] border border-[var(--border)] rounded-lg flex items-center justify-between">
            <div>
              <span className="text-[11px] font-mono text-[var(--text-3)]">Sector 1 Record</span>
              <p className="text-lg font-bold font-mono text-purple-400">
                {sectors.sessionBest.s1.toFixed(3)}s
              </p>
            </div>
            <span className="px-2 py-1 rounded bg-[var(--surface)] font-mono text-xs font-bold text-[var(--text)] border border-[var(--border)]">
              {sectors.holders.s1}
            </span>
          </div>

          <div className="p-3 bg-[var(--raised)] border border-[var(--border)] rounded-lg flex items-center justify-between">
            <div>
              <span className="text-[11px] font-mono text-[var(--text-3)]">Sector 2 Record</span>
              <p className="text-lg font-bold font-mono text-purple-400">
                {sectors.sessionBest.s2.toFixed(3)}s
              </p>
            </div>
            <span className="px-2 py-1 rounded bg-[var(--surface)] font-mono text-xs font-bold text-[var(--text)] border border-[var(--border)]">
              {sectors.holders.s2}
            </span>
          </div>

          <div className="p-3 bg-[var(--raised)] border border-[var(--border)] rounded-lg flex items-center justify-between">
            <div>
              <span className="text-[11px] font-mono text-[var(--text-3)]">Sector 3 Record</span>
              <p className="text-lg font-bold font-mono text-purple-400">
                {sectors.sessionBest.s3.toFixed(3)}s
              </p>
            </div>
            <span className="px-2 py-1 rounded bg-[var(--surface)] font-mono text-xs font-bold text-[var(--text)] border border-[var(--border)]">
              {sectors.holders.s3}
            </span>
          </div>
        </div>
      </section>

      {/* Race Control & Pit Timeline + Position Chart */}
      <section>
        <RaceStoryScrollytelling positionData={positionData} />
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
          subtitle={`Final verified classification for ${DEMO_RACE.name} with tyre stints and lap records`}
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
                  <th className="py-2.5 px-3 text-center">Tyres</th>
                  <th className="py-2.5 px-3 text-right">Best Lap</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)] font-mono">
                {classification.map((item) => {
                  const driverStints = race.stints.filter((s) => s.driver === item.code);
                  const isRetired = item.status.startsWith("Retired");

                  return (
                    <tr
                      key={item.code}
                      className="hover:bg-[var(--raised)] transition-colors"
                      style={{ borderLeft: `3px solid ${item.teamColor}` }}
                    >
                      <td className="py-2 px-3 font-bold text-[var(--text)]">
                        P{item.pos}
                      </td>
                      <td
                        className="py-2 px-3 font-sans font-semibold text-[var(--text)] cursor-pointer hover:underline"
                        onClick={() => {
                          inspectItem({
                            type: "driver",
                            title: item.name,
                            subtitle: item.team,
                            details: {
                              "Finishing Position": `P${item.pos}`,
                              "Starting Grid": `P${item.grid}`,
                              Points: String(item.points),
                              "Fastest Lap": fmtLap(item.bestLap),
                            },
                            queryContext: `Detailed race breakdown for ${item.name}`,
                          });
                        }}
                      >
                        {item.name} <span className="text-[var(--text-3)] text-[11px]">({item.code})</span>
                      </td>
                      <td className="py-2 px-3 font-sans text-[var(--text-2)]">
                        {item.team}
                      </td>
                      <td className="py-2 px-3 text-right text-[var(--text-3)]">
                        P{item.grid}
                      </td>
                      <td className="py-2 px-3 text-right text-[var(--accent)] font-semibold">
                        {item.timeOrGap}
                      </td>
                      <td className="py-2 px-3 text-right text-[var(--text)] font-bold">
                        {item.points}
                      </td>
                      <td className="py-2 px-3 text-right">
                        {isRetired ? (
                          <span className="px-2 py-0.5 rounded bg-red-500/15 border border-red-500/30 text-red-400 font-bold text-[10px]">
                            DNF
                          </span>
                        ) : item.placesGained != null && item.placesGained > 0 ? (
                          <span className="text-[var(--positive)] font-bold">
                            +{item.placesGained}
                          </span>
                        ) : item.placesGained != null && item.placesGained < 0 ? (
                          <span className="text-[var(--negative)]">
                            {item.placesGained}
                          </span>
                        ) : (
                          <span className="text-[var(--text-3)]">0</span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-center">
                        <div className="flex items-center justify-center gap-1">
                          {driverStints.map((s, si) => (
                            <span
                              key={si}
                              className="w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] text-black shadow-xs"
                              style={{ backgroundColor: COMPOUND_COLOR[s.compound] }}
                              title={`Stint ${s.stint}: ${s.compound} (${s.laps} laps)`}
                            >
                              {s.compound}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-2 px-3 text-right text-[var(--text-2)]">
                        {fmtLap(item.bestLap)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      </section>

      {/* Standings Summary: Drivers & Constructors with SEASON_LABEL */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Drivers Standings */}
        <div className="p-5 border border-[var(--border)] rounded-lg bg-[var(--surface)]">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-base font-bold text-[var(--text)]">
              Drivers Championship Standings
            </h2>
            <span className="text-xs font-mono text-[var(--text-3)]">
              {SEASON_LABEL}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead className="border-b border-[var(--border)] text-[var(--text-3)]">
                <tr>
                  <th className="py-2 px-2 text-left">Pos</th>
                  <th className="py-2 px-2 text-left">Driver</th>
                  <th className="py-2 px-2 text-left">Team</th>
                  <th className="py-2 px-2 text-right">Wins</th>
                  <th className="py-2 px-2 text-right">Points</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {STANDINGS_DRIVERS.map((d) => (
                  <tr key={d.code} className="hover:bg-[var(--raised)]">
                    <td className="py-2 px-2 font-bold text-[var(--text)]">P{d.pos}</td>
                    <td className="py-2 px-2 font-sans font-medium text-[var(--text)]">{d.name}</td>
                    <td className="py-2 px-2 font-sans text-[var(--text-2)]">{d.team}</td>
                    <td className="py-2 px-2 text-right text-[var(--text-3)]">{d.wins}</td>
                    <td className="py-2 px-2 text-right font-bold text-[var(--accent)]">{d.points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Constructors Standings */}
        <div className="p-5 border border-[var(--border)] rounded-lg bg-[var(--surface)]">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-base font-bold text-[var(--text)]">
              Constructors Championship Standings
            </h2>
            <span className="text-xs font-mono text-[var(--text-3)]">
              {SEASON_LABEL}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead className="border-b border-[var(--border)] text-[var(--text-3)]">
                <tr>
                  <th className="py-2 px-2 text-left">Pos</th>
                  <th className="py-2 px-2 text-left">Constructor</th>
                  <th className="py-2 px-2 text-right">Points</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {STANDINGS_CONSTRUCTORS.map((c) => (
                  <tr key={c.id} className="hover:bg-[var(--raised)]">
                    <td className="py-2 px-2 font-bold text-[var(--text)]">P{c.pos}</td>
                    <td className="py-2 px-2 font-sans font-medium text-[var(--text)] flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: c.color }} />
                      {c.name}
                    </td>
                    <td className="py-2 px-2 text-right font-bold text-[var(--accent)]">{c.points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}

export default function HomePage(): React.JSX.Element {
  return (
    <Suspense fallback={<div className="p-8 text-center text-[12px] font-mono text-[var(--text-3)]">Loading workspace intelligence...</div>}>
      <DashboardHub />
    </Suspense>
  );
}
