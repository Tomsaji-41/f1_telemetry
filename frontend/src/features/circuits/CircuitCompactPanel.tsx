"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { fetcher } from "@/lib/api";

interface CircuitCompactPanelProps {
  circuitId?: string;
  year?: number;
  round?: number;
  className?: string;
}

export function CircuitCompactPanel({
  circuitId = "silverstone",
  year,
  round,
  className = "",
}: CircuitCompactPanelProps): React.JSX.Element | null {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!circuitId) return;
    let mounted = true;
    setLoading(true);

    const query = year ? `?year=${year}&round=${round || 1}` : "";
    fetcher<any>(`/api/circuits/${circuitId}${query}`)
      .then((res) => {
        if (!mounted) return;
        if (res.status === "ok") {
          setData(res);
        }
        setLoading(false);
      })
      .catch(() => {
        if (!mounted) return;
        setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [circuitId, year, round]);

  if (loading) {
    return (
      <div className={`p-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] animate-pulse ${className}`}>
        <div className="h-4 bg-[var(--raised)] rounded w-1/3 mb-2" />
        <div className="h-3 bg-[var(--raised)] rounded w-1/2" />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className={`p-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] font-mono text-xs ${className}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2 pb-2 border-b border-[var(--border)]">
        <div>
          <span className="text-[10px] text-[var(--accent)] uppercase font-bold tracking-wider block">
            Circuit Profile
          </span>
          <h4 className="text-[15px] font-bold text-[var(--text)] tracking-tight">
            {data.name}
          </h4>
          <span className="text-[11px] text-[var(--text-3)]">
            {data.identity.locality}, {data.identity.country}
          </span>
        </div>

        <Link
          href={`/circuits?circuit=${data.circuit_id}`}
          className="px-2.5 py-1 rounded bg-[var(--raised)] border border-[var(--border)] text-[11px] text-[var(--text-2)] hover:text-[var(--text)] transition"
        >
          View 3D Track →
        </Link>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center pt-1">
        <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
          <div className="text-[9px] uppercase text-[var(--text-3)]">Length</div>
          <div className="text-[12px] font-bold text-[var(--text)] mt-0.5">
            {data.track_facts.length_km ? `${data.track_facts.length_km} km` : "n/a"}
          </div>
        </div>
        <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
          <div className="text-[9px] uppercase text-[var(--text-3)]">Turns</div>
          <div className="text-[12px] font-bold text-[var(--text)] mt-0.5">
            {data.track_facts.corner_count || "n/a"}
          </div>
        </div>
        <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
          <div className="text-[9px] uppercase text-[var(--text-3)]">Direction</div>
          <div className="text-[12px] font-bold text-[var(--text)] uppercase mt-0.5">
            {data.track_facts.direction || "Clockwise"}
          </div>
        </div>
        <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
          <div className="text-[9px] uppercase text-[var(--text-3)]">Lap Record</div>
          <div className="text-[11px] font-bold text-[var(--text)] mt-0.5 truncate">
            {data.race_history.lap_record ? data.race_history.lap_record.split(" ")[0] : "n/a"}
          </div>
        </div>
      </div>
    </div>
  );
}
