"use client";

import React, { useState } from "react";
import { Flag, AlertTriangle, ShieldAlert, Radio, Info, Filter } from "lucide-react";
import { Badge } from "@/components/primitives/badge";

export interface RaceIncident {
  id: string;
  lap: number;
  type: "yellow_flag" | "red_flag" | "vsc" | "safety_car" | "investigation" | string;
  message: string;
  severity: "info" | "low" | "medium" | "high";
  time: string;
}

const DEFAULT_INCIDENTS: RaceIncident[] = [
  {
    id: "inc-1",
    lap: 1,
    type: "green_flag",
    message: "Race Start: Green flag on pit exit. Formation lap complete.",
    severity: "info",
    time: "15:03:02",
  },
  {
    id: "inc-2",
    lap: 8,
    type: "track_limits",
    message: "Turn 4 Track Limits: Car 44 warned for exceeding track boundaries.",
    severity: "low",
    time: "15:15:40",
  },
  {
    id: "inc-3",
    lap: 19,
    type: "yellow_flag",
    message: "Sector 1 Localized Caution: Car 14 off-line at Turn 1 apex.",
    severity: "medium",
    time: "15:32:12",
  },
  {
    id: "inc-4",
    lap: 28,
    type: "vsc",
    message: "Virtual Safety Car deployed: Marshall intervention required at Turn 6.",
    severity: "high",
    time: "15:44:50",
  },
  {
    id: "inc-5",
    lap: 32,
    type: "green_flag",
    message: "Track clear: Track status returns to Green. DRS re-enabled.",
    severity: "info",
    time: "15:49:15",
  },
];

interface IncidentLogProps {
  incidents?: RaceIncident[];
}

export function IncidentLog({ incidents = DEFAULT_INCIDENTS }: IncidentLogProps): React.JSX.Element {
  const [filter, setFilter] = useState<string>("all");

  const filteredIncidents = incidents.filter((inc) => {
    if (filter === "all") return true;
    if (filter === "high") return inc.severity === "high";
    if (filter === "warnings") return inc.severity === "medium" || inc.severity === "low";
    return true;
  });

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case "high":
        return (
          <span className="flex items-center gap-1 rounded bg-red-950/80 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-red-400 border border-red-800/60">
            <ShieldAlert className="h-3 w-3" /> CRITICAL
          </span>
        );
      case "medium":
        return (
          <span className="flex items-center gap-1 rounded bg-amber-950/80 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-400 border border-amber-800/60">
            <AlertTriangle className="h-3 w-3" /> CAUTION
          </span>
        );
      case "low":
        return (
          <span className="flex items-center gap-1 rounded bg-yellow-950/60 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-yellow-300 border border-yellow-800/50">
            <Flag className="h-3 w-3" /> NOTICE
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1 rounded bg-blue-950/60 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blue-300 border border-blue-800/50">
            <Info className="h-3 w-3" /> INFO
          </span>
        );
    }
  };

  return (
    <div className="flex h-full flex-col rounded-2xl border border-slate-800/80 bg-slate-950/90 p-4 shadow-xl">
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <Radio className="h-4 w-4 text-red-500 animate-pulse" />
          <h3 className="text-sm font-bold tracking-wide text-white uppercase">Race Control Incident Log</h3>
        </div>
        <span className="rounded bg-slate-900 px-2 py-0.5 font-mono text-xs font-semibold text-slate-400">
          {incidents.length} events
        </span>
      </div>

      <div className="flex items-center gap-1.5 py-2.5">
        <Filter className="h-3 w-3 text-slate-500" />
        <span className="text-[11px] font-medium text-slate-400 mr-1">Filter:</span>
        <button
          type="button"
          onClick={() => setFilter("all")}
          className={`rounded px-2 py-0.5 text-[11px] font-semibold transition ${
            filter === "all" ? "bg-red-600 text-white" : "bg-slate-900 text-slate-400 hover:text-white"
          }`}
        >
          All
        </button>
        <button
          type="button"
          onClick={() => setFilter("high")}
          className={`rounded px-2 py-0.5 text-[11px] font-semibold transition ${
            filter === "high" ? "bg-red-600 text-white" : "bg-slate-900 text-slate-400 hover:text-white"
          }`}
        >
          High Alert
        </button>
        <button
          type="button"
          onClick={() => setFilter("warnings")}
          className={`rounded px-2 py-0.5 text-[11px] font-semibold transition ${
            filter === "warnings" ? "bg-red-600 text-white" : "bg-slate-900 text-slate-400 hover:text-white"
          }`}
        >
          Notices
        </button>
      </div>

      <div className="flex-1 space-y-2.5 overflow-y-auto max-h-[360px] pr-1">
        {filteredIncidents.map((incident) => (
          <div
            key={incident.id}
            className="group rounded-xl border border-slate-800/60 bg-slate-900/50 p-3 hover:border-slate-700 transition"
          >
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] font-bold text-slate-300">
                  LAP {incident.lap}
                </span>
                {getSeverityBadge(incident.severity)}
              </div>
              <span className="font-mono text-[11px] text-slate-500">{incident.time}</span>
            </div>
            <p className="text-xs text-slate-200 leading-relaxed font-sans">{incident.message}</p>
          </div>
        ))}
        {filteredIncidents.length === 0 && (
          <p className="py-6 text-center text-xs text-slate-500">No incidents matching the current filter.</p>
        )}
      </div>
    </div>
  );
}
