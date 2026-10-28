"use client";

import React from "react";
import Link from "next/link";
import {
  DRIVERS,
  DEMO_LABEL,
  STANDINGS_DRIVERS,
  getRace,
  teamById,
  fmtLap,
} from "@/demo/demoData";
import { ChevronRight } from "lucide-react";
import en from "@/content/en.json";

export default function DriversPage(): React.JSX.Element {
  const race = getRace();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border)]">
        <div>
          <h1 className="text-[28px] font-semibold text-[var(--text)] tracking-tight">
            {en.nav.drivers}
          </h1>
          <p className="text-[13px] text-[var(--text-3)] mt-0.5">
            {DEMO_LABEL} — Sample championship roster and race performance
          </p>
        </div>
      </div>

      {/* Grid: all 10 drivers */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {DRIVERS.map((driver) => {
          const team = teamById(driver.team);
          const standing = STANDINGS_DRIVERS.find((s) => s.code === driver.code);
          const raceResult = race.classification.find((c) => c.code === driver.code);
          const monogram = driver.name
            .split(" ")
            .map((n) => n[0])
            .join("");

          return (
            <Link
              key={driver.code}
              href={`/drivers/${driver.code}`}
              className="p-5 border border-[var(--border)] rounded-lg bg-[var(--surface)] hover:bg-[var(--raised)] hover:border-[var(--border-strong)] transition-all flex flex-col justify-between group"
              style={{
                borderRadius: "var(--radius-m)",
                borderLeft: `3px solid ${team.color}`,
              }}
            >
              <div>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-full flex items-center justify-center font-bold text-[13px] text-white shadow-xs"
                      style={{ backgroundColor: team.color }}
                    >
                      {monogram}
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[11px] font-semibold text-[var(--text-3)]">
                          #{driver.num}
                        </span>
                        <h2 className="text-[17px] font-semibold text-[var(--text)] group-hover:text-[var(--accent)] transition-colors">
                          {driver.name}
                        </h2>
                      </div>
                      <p className="text-[12px] text-[var(--text-3)]">
                        {team.name} • {driver.nat}
                      </p>
                    </div>
                  </div>
                  <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-[var(--raised)] border border-[var(--border)] text-[var(--text-2)]">
                    {driver.code}
                  </span>
                </div>

                {/* Performance stats */}
                <div className="grid grid-cols-2 gap-3 mt-4 pt-3 border-t border-[var(--border)]">
                  <div className="p-2.5 bg-[var(--raised)] border border-[var(--border)] rounded">
                    <span className="text-[10px] text-[var(--text-3)] font-mono uppercase">
                      Championship
                    </span>
                    <p className="text-[16px] font-bold font-mono text-[var(--text)] mt-0.5">
                      P{standing?.pos ?? "-"} ({standing?.points ?? 0} pts)
                    </p>
                  </div>
                  <div className="p-2.5 bg-[var(--raised)] border border-[var(--border)] rounded">
                    <span className="text-[10px] text-[var(--text-3)] font-mono uppercase">
                      Sample Result
                    </span>
                    <p className="text-[16px] font-bold font-mono text-[var(--accent)] mt-0.5">
                      {raceResult ? (raceResult.status === "Finished" ? `P${raceResult.pos}` : "DNF") : "-"}
                    </p>
                  </div>
                </div>

                <div className="mt-3 text-[11px] font-mono text-[var(--text-3)] flex items-center justify-between">
                  <span>Best Lap: {raceResult?.bestLap ? fmtLap(raceResult.bestLap) : "-"}</span>
                  <span className="text-[var(--accent)] flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform">
                    Details <ChevronRight className="w-3 h-3" />
                  </span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
