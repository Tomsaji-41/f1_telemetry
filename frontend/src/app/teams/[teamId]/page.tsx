"use client";

import React, { use } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  TEAM_LIST,
  DEMO_LABEL,
  STANDINGS_CONSTRUCTORS,
  DRIVERS,
  getRace,
  fmtLap,
} from "@/demo/demoData";
import { ArrowLeft } from "lucide-react";

export default function TeamDetailPage({
  params,
}: {
  params: Promise<{ teamId: string }>;
}): React.JSX.Element {
  const { teamId } = use(params);
  const team = TEAM_LIST.find((t) => t.id === teamId);

  if (!team) {
    notFound();
  }

  const standing = STANDINGS_CONSTRUCTORS.find((s) => s.id === team.id);
  const drivers = DRIVERS.filter((d) => d.team === team.id);
  const race = getRace();

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Link
        href="/teams"
        className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--accent)] hover:underline transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        <span>Back to Constructors</span>
      </Link>

      <div
        className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl overflow-hidden shadow-xl"
        style={{ borderTop: `6px solid ${team.color}` }}
      >
        <div className="p-8 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <span className="text-xs font-mono uppercase tracking-wider text-[var(--text-3)]">
                Constructor Profile
              </span>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-[var(--text)] mt-1">
                {team.name}
              </h1>
              <p className="text-[var(--text-3)] text-sm mt-0.5">{team.base}</p>
            </div>
            <div className="font-mono text-left sm:text-right">
              <span className="text-[11px] uppercase tracking-wider text-[var(--text-3)]">
                Championship Standing
              </span>
              <p className="text-3xl font-black text-[var(--accent)]">
                P{standing?.pos ?? "-"}
              </p>
              <span className="text-xs text-[var(--text-2)]">
                {standing?.points ?? 0} Points
              </span>
            </div>
          </div>

          <div className="p-4 bg-[var(--raised)] border border-[var(--border)] rounded-xl">
            <h2 className="text-xs font-mono uppercase tracking-wider text-[var(--text-3)] mb-1">
              Historical Note
            </h2>
            <p className="text-sm text-[var(--text-2)] leading-relaxed">{team.note}</p>
          </div>

          {/* Drivers Sample Results */}
          <div className="border-t border-[var(--border)] pt-6">
            <h2 className="text-lg font-bold text-[var(--text)] mb-3">
              Driver Roster & Sample Grand Prix Results
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {drivers.map((d) => {
                const res = race.classification.find((c) => c.code === d.code);
                return (
                  <div
                    key={d.code}
                    className="p-4 rounded-xl border border-[var(--border)] bg-[var(--raised)] flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex justify-between items-center">
                        <span className="font-mono text-xs font-bold text-[var(--accent)]">
                          #{d.num}
                        </span>
                        <span className="font-mono text-xs px-2 py-0.5 rounded bg-[var(--surface)] border border-[var(--border)]">
                          {d.code}
                        </span>
                      </div>
                      <h3 className="text-base font-bold text-[var(--text)] mt-1">
                        {d.name}
                      </h3>
                      <p className="text-xs text-[var(--text-3)]">{d.nat}</p>
                    </div>

                    <div className="mt-4 pt-3 border-t border-[var(--border)] grid grid-cols-2 gap-2 text-xs font-mono">
                      <div>
                        <span className="text-[var(--text-3)]">Finish:</span>{" "}
                        <span className="font-bold text-[var(--text)]">
                          {res?.status === "Finished" ? `P${res.pos}` : "DNF"}
                        </span>
                      </div>
                      <div>
                        <span className="text-[var(--text-3)]">Best Lap:</span>{" "}
                        <span className="font-bold text-[var(--text)]">
                          {res?.bestLap ? fmtLap(res.bestLap) : "-"}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <p className="text-[11px] font-mono text-[var(--text-3)] text-center pt-2">
            {DEMO_LABEL}
          </p>
        </div>
      </div>
    </div>
  );
}
