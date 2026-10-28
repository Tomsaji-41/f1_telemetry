"use client";

import React from "react";
import Link from "next/link";
import { Shield, MapPin, ArrowUpRight } from "lucide-react";
import { TEAM_LIST, STANDINGS_CONSTRUCTORS, DRIVERS } from "@/demo/demoData";

export function ConstructorGrid(): React.JSX.Element {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {TEAM_LIST.map((team) => {
        const standing = STANDINGS_CONSTRUCTORS.find((s) => s.id === team.id);
        const drivers = DRIVERS.filter((d) => d.team === team.id);

        return (
          <Link
            key={team.id}
            href={`/teams/${team.id}`}
            className="group relative rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 hover:border-[var(--border-strong)] hover:bg-[var(--raised)] transition-all flex flex-col justify-between overflow-hidden"
            style={{ borderTopWidth: "4px", borderTopColor: team.color }}
          >
            <div className="space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-3)]">
                    Constructor
                  </span>
                  <h3 className="text-lg font-bold text-[var(--text)] group-hover:text-[var(--accent)] transition-colors">
                    {team.name}
                  </h3>
                </div>
                <div
                  className="flex h-8 w-8 items-center justify-center rounded-lg shadow-sm"
                  style={{ backgroundColor: `${team.color}20`, color: team.color }}
                >
                  <Shield className="h-4 w-4" />
                </div>
              </div>

              <div className="flex items-center gap-1.5 text-xs text-[var(--text-3)] font-mono">
                <MapPin className="h-3.5 w-3.5" />
                <span>{team.base}</span>
              </div>

              <p className="text-[12px] text-[var(--text-2)]">{team.note}</p>

              <div className="pt-2 border-t border-[var(--border)] flex items-center justify-between text-xs font-mono">
                <span className="text-[var(--text-3)]">
                  Drivers: {drivers.map((d) => d.code).join(", ")}
                </span>
                <span className="font-bold text-[var(--text)]">
                  {standing ? `${standing.points} pts (P${standing.pos})` : ""}
                </span>
              </div>
            </div>

            <div className="pt-3 mt-3 flex items-center justify-end text-xs text-[var(--accent)] font-semibold gap-1">
              <span>View Profile</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </div>
          </Link>
        );
      })}
    </div>
  );
}
