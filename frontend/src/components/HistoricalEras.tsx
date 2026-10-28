"use client";

import React, { useState } from "react";
import { History, Calendar, Users, Cpu, ChevronRight } from "lucide-react";

export interface F1Era {
  eraName: string;
  years: string;
  keyDrivers: string[];
  description: string;
}

export const F1_HISTORICAL_ERAS: F1Era[] = [
  {
    eraName: "Ground Effect & Hybrid Era",
    years: "2022 – 2026",
    keyDrivers: ["Max Verstappen", "Lando Norris", "Charles Leclerc", "Oscar Piastri", "George Russell"],
    description: "Venturi tunnels, 18-inch low-profile wheels, and close-wheel racing regulations."
  },
  {
    eraName: "Turbo-Hybrid Dominance Era",
    years: "2014 – 2021",
    keyDrivers: ["Lewis Hamilton", "Nico Rosberg", "Sebastian Vettel", "Valtteri Bottas", "Daniel Ricciardo"],
    description: "1.6L V6 Turbo Hybrid power units delivering over 1000 horsepower with energy recovery (MGU-K / MGU-H)."
  },
  {
    eraName: "V8 & Blown Diffuser Era",
    years: "2006 – 2013",
    keyDrivers: ["Sebastian Vettel", "Fernando Alonso", "Kimi Räikkönen", "Jenson Button", "Lewis Hamilton"],
    description: "High-revving 2.4L V8 engines, KERS system introductions, and complex aerodynamic blown diffusers."
  },
  {
    eraName: "V10 Screamers & Golden Era",
    years: "1995 – 2005",
    keyDrivers: ["Michael Schumacher", "Mika Häkkinen", "Fernando Alonso", "Rubens Barrichello", "Juan Pablo Montoya"],
    description: "Refueling pit stops, ultra-light chassis, 19,000 RPM V10 engines, and tyre wars between Bridgestone and Michelin."
  }
];

interface HistoricalErasProps {
  onSelectEra?: (era: F1Era) => void;
}

export function HistoricalEras({ onSelectEra }: HistoricalErasProps): React.JSX.Element {
  const [selectedEra, setSelectedEra] = useState<F1Era>(F1_HISTORICAL_ERAS[0]);

  return (
    <div className="space-y-4 rounded-2xl border border-slate-800/80 bg-slate-950/80 p-6 shadow-xl">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <History className="h-5 w-5 text-red-500" />
          <div>
            <h3 className="font-bold text-base text-white tracking-wide">F1 Historical Eras & Technical Regulations</h3>
            <p className="text-xs text-slate-400">Explore technical architecture, engine regulations, and champion drivers</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {F1_HISTORICAL_ERAS.map((era) => {
          const isCurrent = selectedEra.eraName === era.eraName;
          return (
            <div
              key={era.eraName}
              onClick={() => {
                setSelectedEra(era);
                if (onSelectEra) onSelectEra(era);
              }}
              className={`cursor-pointer rounded-xl border p-4 transition-all duration-300 ${
                isCurrent
                  ? "border-red-500/80 bg-slate-900/95 ring-1 ring-red-500/50 shadow-lg shadow-red-950/30 scale-[1.02]"
                  : "border-slate-800/80 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/70"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-xs font-bold text-red-400 bg-red-950/60 px-2 py-0.5 rounded border border-red-800/50">
                  {era.years}
                </span>
                <ChevronRight className={`h-4 w-4 text-slate-500 transition-transform ${isCurrent ? "rotate-90 text-red-400" : ""}`} />
              </div>

              <h4 className="font-bold text-sm text-white">{era.eraName}</h4>
              <p className="text-xs text-slate-300 mt-2 leading-relaxed line-clamp-3">
                {era.description}
              </p>

              <div className="mt-3 pt-3 border-t border-slate-800/80">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                  Key Drivers
                </span>
                <div className="flex flex-wrap gap-1">
                  {era.keyDrivers.map((driver) => (
                    <span
                      key={driver}
                      className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded font-medium"
                    >
                      {driver}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
export default HistoricalEras;
