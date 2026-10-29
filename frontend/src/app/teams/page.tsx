"use client";

import React, { useState, useEffect } from "react";
import { fetcher } from "@/lib/api";
import { useIdentity } from "@/lib/useIdentity";
import { Skeleton, ErrorState, EmptyState } from "@/components/primitives/kit";

interface TeamItem {
  id: string;
  name: string;
  color: string;
  position: number | string;
  points: number;
  wins: number;
  podiums?: number;
  best_finish?: string | number;
  nationality?: string;
  drivers: string[];
}

export default function TeamsHubPage(): React.JSX.Element {
  const [teams, setTeams] = useState<TeamItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const { getTeam, getDriver } = useIdentity();

  useEffect(() => {
    let mounted = true;
    fetcher<{ status: string; teams: TeamItem[]; reason?: string }>("/api/teams")
      .then((data) => {
        if (!mounted) return;
        if (data.status === "ok") {
          setTeams(data.teams || []);
        } else {
          setError(data.reason || "Failed to load constructor standings.");
        }
        setLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to connect to telemetry service.");
        setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="space-y-6 select-none">
      {/* Header */}
      <div className="pb-4 border-b border-[var(--border)]">
        <h1 className="text-[28px] font-bold text-[var(--text)] tracking-tight">
          Constructors & Teams
        </h1>
        <p className="text-[13px] text-[var(--text-3)] mt-0.5">
          FIA Formula 1 World Championship constructors, standings and driver rosters
        </p>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-56 w-full" />
          ))}
        </div>
      ) : error ? (
        <ErrorState
          title="Cannot load constructors"
          message={error}
          source="Jolpica"
          onRetry={() => window.location.reload()}
        />
      ) : teams.length === 0 ? (
        <EmptyState title="No constructors found" message="No constructor records available for this season." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {teams.map((team) => {
            const teamIdentity = getTeam(team.id) || getTeam(team.name);
            const teamColor = teamIdentity?.teamColor || team.color || "var(--accent)";

            return (
              <div
                key={team.id}
                data-testid="team-card"
                className="p-5 border border-[var(--border)] rounded-lg bg-[var(--surface)] flex flex-col justify-between"
                style={{
                  borderRadius: "var(--radius-m)",
                  borderLeft: `4px solid ${teamColor}`,
                }}
              >
                <div>
                  {/* Team Title & Position */}
                  <div className="flex justify-between items-start gap-4">
                    <div>
                      <h2 className="text-[20px] font-bold text-[var(--text)] tracking-tight">
                        {team.name}
                      </h2>
                      <p className="text-[12px] text-[var(--text-3)] mt-0.5 font-mono">
                        Base: <span className="text-[var(--text-2)]">{team.nationality || "FIA Registered Base"}</span>
                      </p>
                    </div>

                    <span className="font-mono text-[13px] font-bold px-2.5 py-1 rounded bg-[var(--raised)] border border-[var(--border)] text-[var(--text)]">
                      P{team.position !== undefined && team.position !== null ? team.position : "n/a"} ({team.points} pts)
                    </span>
                  </div>

                  {/* Constructor Metrics */}
                  <div className="grid grid-cols-3 gap-2 mt-4 text-center">
                    <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
                      <div className="text-[10px] font-mono uppercase text-[var(--text-3)]">Points</div>
                      <div className="text-[14px] font-bold font-mono text-[var(--text)] mt-0.5">
                        {team.points !== undefined && team.points !== null ? team.points : "n/a"}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
                      <div className="text-[10px] font-mono uppercase text-[var(--text-3)]">Wins</div>
                      <div className="text-[14px] font-bold font-mono text-[var(--text)] mt-0.5">
                        {team.wins !== undefined && team.wins !== null ? team.wins : "0"}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
                      <div className="text-[10px] font-mono uppercase text-[var(--text-3)]">Podiums</div>
                      <div className="text-[14px] font-bold font-mono text-[var(--text)] mt-0.5">
                        {team.podiums !== undefined && team.podiums !== null ? team.podiums : "n/a"}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Driver Roster */}
                <div className="mt-4 pt-3 border-t border-[var(--border)]">
                  <div className="text-[11px] font-mono uppercase text-[var(--text-3)] mb-2 font-bold tracking-wider">
                    Official Driver Lineup
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {team.drivers && team.drivers.length > 0 ? (
                      team.drivers.map((drvName, idx) => {
                        const drvMeta = getDriver(drvName);
                        const code = drvMeta?.code || drvName.split(" ").slice(-1)[0].slice(0, 3).toUpperCase();
                        const isSecond = idx === 1;

                        return (
                          <div
                            key={drvName}
                            className="flex items-center gap-2 px-2.5 py-1 rounded bg-[var(--raised)] border border-[var(--border)] text-[12px] font-mono"
                          >
                            <span
                              className="w-2 h-2 rounded-full inline-block"
                              style={{
                                backgroundColor: teamColor,
                                border: isSecond ? "1px dashed var(--text)" : "none",
                              }}
                            />
                            <span className="font-bold text-[var(--accent)]">{code}</span>
                            <span className="text-[var(--text-2)]">{drvName}</span>
                          </div>
                        );
                      })
                    ) : (
                      <span className="text-[12px] font-mono text-[var(--text-3)]">
                        No classified drivers assigned
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
