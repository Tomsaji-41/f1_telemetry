"use client";

import React, { use } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  DRIVERS,
  DEMO_LABEL,
  STANDINGS_DRIVERS,
  getRace,
  teamById,
  buildTelemetry,
  fmtLap,
} from "@/demo/demoData";
import { ArrowLeft, Flag, Award, Gauge } from "lucide-react";

export default function DriverDetailPage({
  params,
}: {
  params: Promise<{ driverId: string }>;
}): React.JSX.Element {
  const { driverId } = use(params);
  const driver = DRIVERS.find(
    (d) => d.code.toLowerCase() === driverId.toLowerCase() || d.code === driverId
  );

  if (!driver) {
    notFound();
  }

  const team = teamById(driver.team);
  const standing = STANDINGS_DRIVERS.find((s) => s.code === driver.code);
  const race = getRace();
  const raceResult = race.classification.find((c) => c.code === driver.code);
  const tel = buildTelemetry(driver.code);
  const topSpeed = Math.max(...tel.speed);
  const monogram = driver.name
    .split(" ")
    .map((n) => n[0])
    .join("");

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Link
        href="/drivers"
        className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--accent)] hover:underline transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        <span>Back to All Drivers</span>
      </Link>

      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl overflow-hidden shadow-xl">
        {/* Header Hero */}
        <div className="p-8 border-b border-[var(--border)] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 bg-gradient-to-r from-[var(--surface)] to-[var(--raised)]">
          <div className="flex items-center gap-5">
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center font-bold text-2xl text-white shadow-lg"
              style={{ backgroundColor: team.color }}
            >
              {monogram}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-semibold text-[var(--text-3)]">
                  #{driver.num}
                </span>
                <span className="px-2 py-0.5 rounded font-mono text-xs font-bold bg-[var(--raised)] border border-[var(--border)] text-[var(--text-2)]">
                  {driver.code}
                </span>
              </div>
              <h1 className="text-3xl sm:text-4xl font-bold text-[var(--text)] mt-1 tracking-tight">
                {driver.name}
              </h1>
              <p className="text-sm text-[var(--text-3)] mt-0.5">
                {team.name} • {driver.nat}
              </p>
            </div>
          </div>

          <div className="text-left sm:text-right font-mono">
            <span className="text-[11px] uppercase tracking-wider text-[var(--text-3)]">
              Championship Position
            </span>
            <p className="text-3xl font-black text-[var(--accent)]">
              P{standing?.pos ?? "-"}
            </p>
            <span className="text-xs text-[var(--text-2)]">
              {standing?.points ?? 0} Points
            </span>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-8 space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-[var(--raised)] p-4 rounded-xl border border-[var(--border)]">
              <span className="text-xs text-[var(--text-3)] font-mono uppercase">
                Grid Position
              </span>
              <p className="text-2xl font-bold font-mono text-[var(--text)] mt-1">
                P{driver.grid}
              </p>
            </div>

            <div className="bg-[var(--raised)] p-4 rounded-xl border border-[var(--border)]">
              <span className="text-xs text-[var(--text-3)] font-mono uppercase">
                Sample Finish
              </span>
              <p className="text-2xl font-bold font-mono text-[var(--accent)] mt-1">
                {raceResult?.status === "Finished" ? `P${raceResult.pos}` : "DNF"}
              </p>
            </div>

            <div className="bg-[var(--raised)] p-4 rounded-xl border border-[var(--border)]">
              <span className="text-xs text-[var(--text-3)] font-mono uppercase">
                Sample Lap Time
              </span>
              <p className="text-2xl font-bold font-mono text-[var(--text)] mt-1">
                {fmtLap(tel.lapTime)}
              </p>
            </div>

            <div className="bg-[var(--raised)] p-4 rounded-xl border border-[var(--border)]">
              <span className="text-xs text-[var(--text-3)] font-mono uppercase">
                Top Speed
              </span>
              <p className="text-2xl font-bold font-mono text-[var(--text)] mt-1">
                {topSpeed} km/h
              </p>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--raised)] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Flag className="w-5 h-5 text-[var(--accent)]" />
              <div>
                <span className="text-sm font-semibold text-[var(--text)]">
                  Sample Race Strategy
                </span>
                <p className="text-xs text-[var(--text-3)] mt-0.5">
                  Laps Completed: {raceResult?.lapsCompleted ?? 57} / 57
                </p>
              </div>
            </div>
            <Link
              href={`/telemetry?d1=${driver.code}&d2=VER`}
              className="text-xs font-semibold px-3 py-1.5 rounded bg-[var(--accent)] text-white hover:opacity-90 transition-opacity"
            >
              Compare Telemetry
            </Link>
          </div>

          <p className="text-[11px] font-mono text-[var(--text-3)] text-center pt-2">
            {DEMO_LABEL}
          </p>
        </div>
      </div>
    </div>
  );
}
