"use client";

import React, { useState, useEffect } from "react";
import { fetcher } from "@/lib/api";
import { useIdentity } from "@/lib/useIdentity";
import { Skeleton, ErrorState, EmptyState } from "@/components/primitives/kit";

interface DriverItem {
  id: string;
  name: string;
  code: string;
  number: string;
  team: string;
  team_color: string;
  nationality: string;
  position: string | number;
  points: number;
  wins: number;
  podiums?: number;
  poles?: number;
  fastest_laps?: number;
  dnfs?: number;
  best_finish?: string | number;
  headshot_url?: string | null;
}

export default function DriversPage(): React.JSX.Element {
  const [drivers, setDrivers] = useState<DriverItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const { getDriver, getDriverColor } = useIdentity();

  useEffect(() => {
    let mounted = true;
    fetcher<{ status: string; drivers: DriverItem[]; reason?: string }>("/api/drivers")
      .then((data) => {
        if (!mounted) return;
        if (data.status === "ok") {
          setDrivers(data.drivers || []);
        } else {
          setError(data.reason || "Failed to load drivers.");
        }
        setLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to connect to data service.");
        setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="space-y-6 select-none">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
        <div>
          <h1 className="text-[28px] font-bold text-[var(--text)] tracking-tight">
            Formula 1 Drivers
          </h1>
          <p className="text-[13px] text-[var(--text-3)] mt-0.5">
            FIA Formula 1 World Championship active drivers and career benchmarks
          </p>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-56 w-full" />
          ))}
        </div>
      ) : error ? (
        <ErrorState
          title="Cannot load drivers"
          message={error}
          source="Jolpica"
          onRetry={() => window.location.reload()}
        />
      ) : drivers.length === 0 ? (
        <EmptyState title="No drivers found" message="No active driver records available for this season." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {drivers.map((driver) => {
            const drvIdentity = getDriver(driver.id) || getDriver(driver.code);
            const teamColor = drvIdentity?.teamColor || driver.team_color || getDriverColor(driver.code) || "var(--accent)";
            const code = drvIdentity?.code || driver.code || "DRV";
            const number = drvIdentity?.number && drvIdentity.number !== "#-" ? drvIdentity.number : (driver.number && driver.number !== "#-" ? driver.number : "n/a");
            const headshot = drvIdentity?.headshotUrl || driver.headshot_url;
            const nationality = driver.nationality || drvIdentity?.nationality || "n/a";

            const monogram = driver.name
              .split(" ")
              .map((n) => n[0])
              .join("")
              .slice(0, 2)
              .toUpperCase();

            return (
              <div
                key={driver.id || code}
                data-testid="driver-card"
                className="p-5 border border-[var(--border)] rounded-lg bg-[var(--surface)] flex flex-col justify-between"
                style={{
                  borderRadius: "var(--radius-m)",
                  borderLeft: `4px solid ${teamColor}`,
                }}
              >
                <div>
                  {/* Driver Header Row */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      {headshot ? (
                        <img
                          src={headshot}
                          alt={driver.name}
                          className="w-12 h-12 rounded-full object-cover border border-[var(--border)] bg-[var(--surface-2)]"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = "none";
                          }}
                        />
                      ) : (
                        <div
                          className="w-12 h-12 rounded-full flex items-center justify-center font-bold text-[14px] border border-[var(--border)]"
                          style={{
                            backgroundColor: "var(--raised)",
                            color: teamColor,
                          }}
                        >
                          {monogram}
                        </div>
                      )}

                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-mono font-bold px-1.5 py-0.5 rounded bg-[var(--raised)] border border-[var(--border)] text-[var(--text-2)]">
                            #{number}
                          </span>
                          <span className="text-[11px] font-mono font-bold text-[var(--accent)] tracking-wider">
                            {code}
                          </span>
                        </div>
                        <h2 className="text-[18px] font-bold text-[var(--text)] tracking-tight mt-0.5">
                          {driver.name}
                        </h2>
                      </div>
                    </div>

                    <span className="font-mono text-[13px] font-bold px-2 py-0.5 rounded bg-[var(--raised)] border border-[var(--border)] text-[var(--text)]">
                      P{driver.position !== undefined && driver.position !== null ? driver.position : "n/a"}
                    </span>
                  </div>

                  {/* Team & Nationality */}
                  <div className="mt-3 flex items-center justify-between text-[12px] font-mono text-[var(--text-3)] pb-3 border-b border-[var(--border)]">
                    <span className="font-medium text-[var(--text-2)] truncate max-w-[170px]">
                      {driver.team || "FIA Competitor"}
                    </span>
                    <span>{nationality}</span>
                  </div>

                  {/* Season Metrics Grid */}
                  <div className="grid grid-cols-3 gap-2 mt-3 text-center">
                    <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
                      <div className="text-[10px] font-mono uppercase text-[var(--text-3)]">Points</div>
                      <div className="text-[14px] font-bold font-mono text-[var(--text)] mt-0.5">
                        {driver.points !== undefined && driver.points !== null ? driver.points : "n/a"}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
                      <div className="text-[10px] font-mono uppercase text-[var(--text-3)]">Wins</div>
                      <div className="text-[14px] font-bold font-mono text-[var(--text)] mt-0.5">
                        {driver.wins !== undefined && driver.wins !== null ? driver.wins : "0"}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
                      <div className="text-[10px] font-mono uppercase text-[var(--text-3)]">Podiums</div>
                      <div className="text-[14px] font-bold font-mono text-[var(--text)] mt-0.5">
                        {driver.podiums !== undefined && driver.podiums !== null ? driver.podiums : "n/a"}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Benchmark Footer */}
                <div className="mt-3 pt-2.5 border-t border-[var(--border)] flex items-center justify-between text-[11px] font-mono text-[var(--text-3)]">
                  <span>Fastest Laps: <strong className="font-bold text-[var(--text)]">{driver.fastest_laps ?? "n/a"}</strong></span>
                  <span>Best Finish: <strong className="font-bold text-[var(--text)]">{driver.best_finish ? `P${driver.best_finish}` : "n/a"}</strong></span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
