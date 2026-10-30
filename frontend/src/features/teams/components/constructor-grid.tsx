"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Shield, ArrowUpRight } from "lucide-react";
import { fetcher } from "@/lib/api";
import { Skeleton, ErrorState, EmptyState } from "@/components/primitives/kit";

interface TeamItem {
  id: string;
  name: string;
  color: string;
  position: number | string;
  points: number;
  wins: number;
  drivers: string[];
}

export function ConstructorGrid(): React.JSX.Element {
  const [teams, setTeams] = useState<TeamItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

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
        setError(err.message || "Failed to connect to data service.");
        setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-44 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Constructor Data Unavailable"
        message={error}
        source="Jolpica"
        onRetry={() => window.location.reload()}
      />
    );
  }

  if (teams.length === 0) {
    return <EmptyState title="No constructors" message="No constructor records available." />;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {teams.map((team) => (
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

            <div className="pt-2 border-t border-[var(--border)] flex items-center justify-between text-xs font-mono">
              <span className="text-[var(--text-3)] truncate max-w-[150px]">
                {team.drivers && team.drivers.length > 0 ? team.drivers.join(", ") : "Formula 1 Team"}
              </span>
              <span className="font-bold text-[var(--text)]">
                {team.points} pts (P{team.position})
              </span>
            </div>
          </div>

          <div className="pt-3 mt-3 flex items-center justify-end text-xs text-[var(--accent)] font-semibold gap-1">
            <span>View Profile</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </div>
        </Link>
      ))}
    </div>
  );
}
