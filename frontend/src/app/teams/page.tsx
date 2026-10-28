"use client";

import React from "react";
import Link from "next/link";
import {
  TEAM_LIST,
  DEMO_LABEL,
  STANDINGS_CONSTRUCTORS,
  DRIVERS,
} from "@/demo/demoData";
import { ChevronRight, Shield } from "lucide-react";
import en from "@/content/en.json";

export default function TeamsHubPage(): React.JSX.Element {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-[var(--border)]">
        <h1 className="text-[28px] font-semibold text-[var(--text)] tracking-tight">
          {en.nav.constructors}
        </h1>
        <p className="text-[13px] text-[var(--text-3)] mt-0.5">
          {DEMO_LABEL} — Championship constructors and driver pairings
        </p>
      </div>

      {/* Constructors Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {TEAM_LIST.map((team) => {
          const standing = STANDINGS_CONSTRUCTORS.find((s) => s.id === team.id);
          const drivers = DRIVERS.filter((d) => d.team === team.id);

          return (
            <Link
              key={team.id}
              href={`/teams/${team.id}`}
              className="p-5 border border-[var(--border)] rounded-lg bg-[var(--surface)] hover:bg-[var(--raised)] hover:border-[var(--border-strong)] transition-all flex flex-col justify-between group"
              style={{
                borderRadius: "var(--radius-m)",
                borderLeft: `3px solid ${team.color}`,
              }}
            >
              <div>
                <div className="flex justify-between items-start">
                  <div>
                    <h2 className="text-[20px] font-semibold text-[var(--text)] group-hover:text-[var(--accent)] transition-colors">
                      {team.name}
                    </h2>
                    <p className="text-[12px] text-[var(--text-3)] mt-0.5">{team.base}</p>
                  </div>
                  <span className="font-mono text-[12px] font-bold px-2.5 py-1 rounded bg-[var(--raised)] border border-[var(--border)] text-[var(--accent)]">
                    P{standing?.pos ?? "-"} ({standing?.points ?? 0} pts)
                  </span>
                </div>

                <p className="text-[12px] text-[var(--text-2)] mt-3 leading-relaxed">
                  {team.note}
                </p>

                {/* Driver Lineup */}
                <div className="mt-4 pt-3 border-t border-[var(--border)]">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-3)]">
                    Driver Lineup
                  </span>
                  <div className="flex gap-2 mt-1.5">
                    {drivers.map((d) => (
                      <span
                        key={d.code}
                        className="px-2 py-1 bg-[var(--raised)] border border-[var(--border)] rounded text-[11px] font-mono text-[var(--text)]"
                      >
                        #{d.num} {d.name} ({d.code})
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between text-[11px] font-mono text-[var(--text-3)] pt-2 border-t border-[var(--border)]">
                <span>Constructor Profile</span>
                <span className="text-[var(--accent)] flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform">
                  View Team Details <ChevronRight className="w-3 h-3" />
                </span>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
