"use client";

import React, { useState } from "react";
import { PositionByLapChart } from "../charts/PositionByLapChart";
import { Flag, ShieldAlert, Award, Clock } from "lucide-react";

interface TimelineEvent {
  type: "control" | "pit";
  lap: number;
  time: string;
  title: string;
  description: string;
  category?: string;
  flag?: string;
}

interface RaceStoryProps {
  positionData: any;
  raceControl?: Array<{ lap: number; time?: string; message?: string; flag?: string; category?: string }>;
  pitStops?: Array<{ driver?: string; stop?: number; lap?: number; duration?: string }>;
}

export function RaceStoryScrollytelling({
  positionData,
  raceControl = [],
  pitStops = [],
}: RaceStoryProps) {
  const [filter, setFilter] = useState<"all" | "control" | "pits">("all");

  const controlEvents: TimelineEvent[] = (raceControl || []).map((m) => ({
    type: "control" as const,
    lap: m.lap || 1,
    time: m.time || "",
    title: m.flag ? `${m.flag} FLAG (Lap ${m.lap})` : `Race Control (Lap ${m.lap})`,
    description: m.message || "",
    category: m.category || "Notice",
    flag: m.flag || "",
  }));

  const pitEvents: TimelineEvent[] = (pitStops || []).map((p) => ({
    type: "pit" as const,
    lap: p.lap || 1,
    time: "",
    title: `Pit Stop: ${p.driver || "Car"}`,
    description: `Stop ${p.stop || 1} on Lap ${p.lap || 1} — Duration: ${p.duration || "-"}`,
    category: "Pit",
    flag: "",
  }));

  const allEvents = [...controlEvents, ...pitEvents].sort((a, b) => a.lap - b.lap);
  const displayedEvents = allEvents.filter((ev) => {
    if (filter === "control") return ev.type === "control";
    if (filter === "pits") return ev.type === "pit";
    return true;
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 my-8">
      {/* Race Timeline on the left (5 cols) */}
      <div className="lg:col-span-5 space-y-4">
        <div className="pb-3 border-b border-[var(--border)] flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono uppercase text-[var(--accent)] font-semibold">
              Event Chronology
            </span>
            <h2 className="text-[20px] font-semibold text-[var(--text)] mt-0.5">
              Race Control & Pit Timeline
            </h2>
            <p className="text-[12px] text-[var(--text-3)]">
              Chronological log derived strictly from official messages and pit telemetry
            </p>
          </div>
        </div>

        {/* Filter buttons */}
        <div className="flex gap-1.5 pb-2">
          <button
            onClick={() => setFilter("all")}
            className={`px-2.5 py-1 text-xs font-mono rounded border transition-colors ${
              filter === "all"
                ? "bg-[var(--accent)] text-white border-[var(--accent)] font-semibold"
                : "bg-[var(--surface)] text-[var(--text-2)] border-[var(--border)] hover:bg-[var(--raised)]"
            }`}
          >
            All Events ({allEvents.length})
          </button>
          <button
            onClick={() => setFilter("control")}
            className={`px-2.5 py-1 text-xs font-mono rounded border transition-colors ${
              filter === "control"
                ? "bg-[var(--accent)] text-white border-[var(--accent)] font-semibold"
                : "bg-[var(--surface)] text-[var(--text-2)] border-[var(--border)] hover:bg-[var(--raised)]"
            }`}
          >
            Race Control ({controlEvents.length})
          </button>
          <button
            onClick={() => setFilter("pits")}
            className={`px-2.5 py-1 text-xs font-mono rounded border transition-colors ${
              filter === "pits"
                ? "bg-[var(--accent)] text-white border-[var(--accent)] font-semibold"
                : "bg-[var(--surface)] text-[var(--text-2)] border-[var(--border)] hover:bg-[var(--raised)]"
            }`}
          >
            Pit Stops ({pitEvents.length})
          </button>
        </div>

        {/* Scrollable Timeline */}
        <div className="space-y-2.5 max-h-[560px] overflow-y-auto pr-1">
          {displayedEvents.length === 0 ? (
            <div className="p-4 text-center text-xs font-mono text-[var(--text-3)] border border-[var(--border)] rounded-lg">
              No incidents or pit events recorded for this session.
            </div>
          ) : (
            displayedEvents.map((ev, idx) => (
              <div
                key={`${ev.type}-${ev.lap}-${idx}`}
                className="p-3.5 border border-[var(--border)] rounded-lg bg-[var(--surface)] hover:bg-[var(--raised)] transition-colors"
                style={{ borderRadius: "var(--radius-m)" }}
              >
                <div className="flex items-center justify-between text-[11px] font-mono text-[var(--text-3)] mb-1">
                  <span className="flex items-center gap-1.5 font-bold text-[var(--text)]">
                    {ev.type === "control" ? (
                      ev.flag === "CHEQUERED" ? (
                        <Award className="w-3.5 h-3.5 text-[var(--positive)]" />
                      ) : ev.flag === "YELLOW" ? (
                        <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                      ) : (
                        <Flag className="w-3.5 h-3.5 text-[var(--accent)]" />
                      )
                    ) : (
                      <Clock className="w-3.5 h-3.5 text-[var(--warning)]" />
                    )}
                    Lap {ev.lap}
                  </span>
                  <span>{ev.time}</span>
                </div>
                <h3 className="text-[13px] font-semibold text-[var(--text)]">
                  {ev.title}
                </h3>
                <p className="text-[12px] text-[var(--text-2)] mt-1 font-mono">
                  {ev.description}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Sticky chart column on the right (7 cols) */}
      <div className="lg:col-span-7">
        <div className="sticky top-20">
          <PositionByLapChart data={positionData} />
        </div>
      </div>
    </div>
  );
}
