"use client";

import React, { useState, useEffect } from "react";
import { Trophy, Award, Calendar, Sparkles } from "lucide-react";
import { fetcher } from "@/lib/api";
import { Skeleton, EmptyState, ErrorState } from "@/components/primitives/kit";

interface Legend {
  name: string;
  driver_id: string;
  titles: number;
  years: number[];
  teams: string[];
  nationality: string;
}

interface Era {
  id: string;
  name: string;
  from: number;
  to: number | null;
  text: string;
  champions_count?: number;
  dominant_drivers?: { driver: string; titles_in_era: number }[];
}

export default function LegendsPage(): React.JSX.Element {
  const [selectedEra, setSelectedEra] = useState<string>("all");
  const [legends, setLegends] = useState<Legend[]>([]);
  const [eras, setEras] = useState<Era[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      fetcher<{ legends: Legend[] }>("/api/legends").catch(() => ({ legends: [] })),
      fetcher<{ eras: Era[] }>("/api/eras").catch(() => ({ eras: [] }))
    ])
      .then(([legRes, erasRes]) => {
        if (!mounted) return;
        setLegends(legRes.legends || []);
        setEras(erasRes.eras || []);
        setLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to load legends.");
        setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-44 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Failed to load F1 Legends"
        message={error}
        source="Jolpica Historical Archives"
        onRetry={() => window.location.reload()}
      />
    );
  }

  const filteredLegends = legends.filter((l) => {
    if (selectedEra === "all") return true;
    const era = eras.find((e) => e.id === selectedEra);
    if (!era) return true;
    const toYear = era.to || new Date().getFullYear();
    return l.years && l.years.some((y) => y >= era.from && y <= toYear);
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-[var(--border)]">
        <h1 className="text-[28px] font-semibold text-[var(--text)] tracking-tight">
          Formula 1 Legends
        </h1>
        <p className="text-[13px] text-[var(--text-3)] mt-0.5">
          Official World Champions & Historical Technical Eras — 1950 to Present
        </p>
      </div>

      {/* Eras Strip */}
      {eras.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs font-mono uppercase tracking-wider text-[var(--text-3)]">
            Championship Eras
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
            {eras.map((era) => (
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
                  <span>{era.from} – {era.to || "Now"}</span>
                  {era.champions_count !== undefined && (
                    <span className="text-[10px] text-[var(--text-3)] font-normal">
                      {era.champions_count} title{era.champions_count !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>
                <h3 className="text-sm font-bold text-[var(--text)] mt-1 truncate">
                  {era.name}
                </h3>
                <p className="text-[11px] text-[var(--text-3)] mt-1 line-clamp-2">
                  {era.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter and Count Bar */}
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
      {filteredLegends.length === 0 ? (
        <EmptyState title="No champions found" message="No champions match the selected era filter." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredLegends.map((l) => (
            <div
              key={l.driver_id || l.name}
              className="bg-[var(--surface)] border border-[var(--border)] rounded-lg p-5 flex flex-col justify-between hover:border-[var(--border-strong)] transition-all"
            >
              <div>
                <div className="flex justify-between items-start gap-2">
                  <div>
                    <h3 className="text-lg font-bold text-[var(--text)] tracking-tight">
                      {l.name}
                    </h3>
                    <p className="text-xs font-mono text-[var(--text-3)] mt-0.5">
                      {l.nationality || "Formula 1"}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 px-2.5 py-1 rounded bg-[var(--raised)] border border-[var(--border)] text-xs font-mono font-bold text-[var(--accent)]">
                    <Trophy className="w-3.5 h-3.5" />
                    <span>{l.titles}x</span>
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  <div className="text-[11px] font-mono text-[var(--text-3)] flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-[var(--text-3)]" />
                    <span className="text-[var(--text-2)]">
                      {l.years && l.years.length > 0 ? l.years.join(", ") : "-"}
                    </span>
                  </div>

                  {l.teams && l.teams.length > 0 && (
                    <div className="text-[11px] font-mono text-[var(--text-3)] flex items-center gap-1.5">
                      <Award className="w-3.5 h-3.5 text-[var(--text-3)]" />
                      <span className="text-[var(--text-2)] truncate">
                        {l.teams.join(", ")}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] font-mono text-[var(--text-3)] flex justify-between items-center">
                <span>Driver Profile</span>
                <span className="text-[var(--accent)]">FIA Champion</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
