"use client";

import React from "react";
import { Gauge, Shield, Trophy, Zap } from "lucide-react";

export interface DriverInfo {
  full_name: string;
  headshot_url?: string;
  team_name: string;
  team_colour?: string;
  driver_number: string;
  code?: string;
  position?: number;
  gap?: string;
  compound?: string;
  lap_time?: string;
}

interface DriverCardProps {
  driver: DriverInfo;
  isSelected?: boolean;
  onSelect?: () => void;
}

export function DriverCard({ driver, isSelected, onSelect }: DriverCardProps): React.JSX.Element {
  const teamColor = driver.team_colour || "#e10600";
  const compoundColor = 
    driver.compound?.toUpperCase() === "SOFT" ? "#ef4444" :
    driver.compound?.toUpperCase() === "MEDIUM" ? "#eab308" :
    driver.compound?.toUpperCase() === "HARD" ? "#f8fafc" : "#3b82f6";

  return (
    <div
      onClick={onSelect}
      className={`relative overflow-hidden rounded-xl border p-4 transition-all duration-300 cursor-pointer ${
        isSelected
          ? "border-red-500/80 bg-slate-900/90 shadow-lg shadow-red-950/40 ring-1 ring-red-500/50 scale-[1.02]"
          : "border-slate-800/80 bg-slate-950/70 hover:border-slate-700 hover:bg-slate-900/60"
      }`}
      style={{
        borderLeftWidth: "4px",
        borderLeftColor: teamColor,
      }}
    >
      {/* Top Banner */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className="flex h-7 w-7 items-center justify-center rounded-md font-mono text-xs font-black text-white shadow-inner"
            style={{ backgroundColor: teamColor }}
          >
            {driver.driver_number}
          </span>
          <div>
            <h4 className="font-bold text-sm text-white leading-none flex items-center gap-1.5">
              <span>{driver.full_name}</span>
              {driver.code && (
                <span className="text-[10px] text-slate-400 font-mono">({driver.code})</span>
              )}
            </h4>
            <p className="text-[11px] text-slate-400 mt-0.5">{driver.team_name}</p>
          </div>
        </div>

        {driver.position && (
          <div className="flex items-center gap-1 rounded bg-slate-800/80 px-2 py-0.5 text-xs font-bold text-slate-200">
            <Trophy className="h-3 w-3 text-amber-400" />
            <span>P{driver.position}</span>
          </div>
        )}
      </div>

      {/* Metrics Row */}
      <div className="mt-3 grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/60 text-xs">
        {driver.lap_time && (
          <div className="flex items-center gap-1.5 text-slate-300">
            <Zap className="h-3.5 w-3.5 text-teal-400" />
            <span className="font-mono text-[11px] truncate">{driver.lap_time}</span>
          </div>
        )}

        {driver.compound && (
          <div className="flex items-center gap-1.5 justify-end">
            <span
              className="h-2 w-2 rounded-full ring-2 ring-slate-800"
              style={{ backgroundColor: compoundColor }}
            />
            <span className="font-mono text-[10px] font-semibold tracking-wider text-slate-300 uppercase">
              {driver.compound}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
export default DriverCard;
