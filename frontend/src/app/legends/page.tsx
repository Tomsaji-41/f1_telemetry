"use client";

import React, { useState } from "react";
import {
  LEGENDS,
  LEGENDS_NOTE,
  ERAS,
  DEMO_LABEL,
} from "@/demo/demoData";
import { Trophy, Award, Calendar, Sparkles } from "lucide-react";
import { Segmented } from "@/components/primitives/kit";

export default function LegendsPage(): React.JSX.Element {
  const [selectedEra, setSelectedEra] = useState<string>("all");

  const eraOptions = [
    { label: "All Eras", value: "all" },
    ...ERAS.map((e) => ({ label: e.name, value: e.id })),
  ];

  const filteredLegends = LEGENDS.filter((l) => {
    if (selectedEra === "all") return true;
    const era = ERAS.find((e) => e.id === selectedEra);
    if (!era) return true;
    return l.titleYears.some((y) => y >= era.from && y <= era.to);
  }).sort((a, b) => b.titles - a.titles || b.wins - a.wins);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-[var(--border)]">
        <h1 className="text-[28px] font-semibold text-[var(--text)] tracking-tight">
          Formula 1 Legends
        </h1>
        <p className="text-[13px] text-[var(--text-3)] mt-0.5">
          {DEMO_LABEL} — Retired World Champions and Championship Eras
        </p>
      </div>

      {/* Note banner */}
      <div className="p-3.5 bg-amber-500/10 border border-amber-500/20 rounded-lg text-[12px] font-mono text-amber-300">
        ℹ️ {LEGENDS_NOTE}
      </div>

      {/* Eras Strip */}
      <div className="space-y-3">
        <h2 className="text-xs font-mono uppercase tracking-wider text-[var(--text-3)]">
          Championship Eras
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {ERAS.map((era) => (
            <div
              key={era.id}
              onClick={() => setSelectedEra(selectedEra === era.id ? "all" : era.id)}
              className={`p-3.5 rounded-lg border transition-all cursor-pointer ${
                selectedEra === era.id
                  ? "bg-[var(--raised)] border-[var(--accent)] ring-1 ring-[var(--accent)]"
                  : "bg-[var(--surface)] border-[var(--border)] hover:border-[var(--border-strong)]"
              }`}
            >
              <div className="flex justify-between items-center text-xs font-mono text-[var(--accent)] font-semibold">
                <span>{era.from} – {era.to}</span>
                {era.champions.length > 0 && (
                  <span className="text-[10px] text-[var(--text-3)] font-normal">
                    {era.champions.length} Champ{era.champions.length > 1 ? "s" : ""}
                  </span>
                )}
              </div>
              <h3 className="text-sm font-bold text-[var(--text)] mt-1">
                {era.name}
              </h3>
              <p className="text-[11px] text-[var(--text-3)] mt-1 line-clamp-2">
                {era.text}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Filter by Era Segmented */}
      <div className="pt-2">
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-xs font-mono uppercase tracking-wider text-[var(--text-3)]">
            World Champions ({filteredLegends.length})
          </h2>
          {selectedEra !== "all" && (
            <button
              onClick={() => setSelectedEra("all")}
              className="text-xs font-mono text-[var(--accent)] hover:underline"
            >
              Reset filter
            </button>
          )}
        </div>
      </div>

      {/* Legends Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredLegends.map((l) => (
          <div
            key={l.id}
            className="p-5 border border-[var(--border)] rounded-lg bg-[var(--surface)] hover:bg-[var(--raised)] transition-all flex flex-col justify-between"
            style={{ borderRadius: "var(--radius-m)" }}
          >
            <div>
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-[18px] font-bold text-[var(--text)]">
                    {l.name}
                  </h3>
                  <p className="text-[11px] font-mono text-[var(--text-3)] mt-0.5">
                    Active: {l.active}
                  </p>
                </div>
                <div className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300 font-mono text-xs font-bold">
                  <Trophy className="w-3.5 h-3.5" />
                  <span>{l.titles} Title{l.titles > 1 ? "s" : ""}</span>
                </div>
              </div>

              {/* Title Years */}
              <div className="mt-4 pt-3 border-t border-[var(--border)]">
                <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-3)]">
                  Championship Seasons
                </span>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {l.titleYears.map((yr) => (
                    <span
                      key={yr}
                      className="px-2 py-0.5 bg-[var(--raised)] border border-[var(--border)] rounded text-[11px] font-mono font-bold text-[var(--accent)]"
                    >
                      {yr}
                    </span>
                  ))}
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3 mt-3">
                <div className="p-2 bg-[var(--raised)] border border-[var(--border)] rounded text-xs font-mono">
                  <span className="text-[10px] text-[var(--text-3)] uppercase">Grand Prix Wins</span>
                  <p className="text-base font-bold text-[var(--text)] mt-0.5">{l.wins}</p>
                </div>
                <div className="p-2 bg-[var(--raised)] border border-[var(--border)] rounded text-xs font-mono">
                  <span className="text-[10px] text-[var(--text-3)] uppercase">Titles</span>
                  <p className="text-base font-bold text-amber-300 mt-0.5">{l.titles}</p>
                </div>
              </div>

              <div className="mt-3 text-[11px] text-[var(--text-3)]">
                <span className="font-semibold text-[var(--text-2)]">Teams:</span> {l.teams}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
