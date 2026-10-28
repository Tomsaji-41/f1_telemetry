"use client";

import React, { useState } from "react";

export interface TelemetryPoint {
  Distance?: number;
  Speed?: number;
  Throttle?: number;
  Brake?: number;
  RPM?: number;
  nGear?: number;
  lap?: number;
  speed?: number;
  delta?: number;
  [key: string]: any;
}

export interface TelemetryChartProps {
  driverCode?: string;
  driverColor?: string;
  telemetryData?: TelemetryPoint[];
  driver1Name?: string;
  driver1Color?: string;
  driver1Data?: TelemetryPoint[];
  driver2Name?: string;
  driver2Color?: string;
  driver2Data?: TelemetryPoint[];
}

export function TelemetryChart({
  driverCode = "VER",
  driverColor = "#E8002D",
  telemetryData,
  driver1Name,
  driver1Color,
  driver1Data,
  driver2Name,
  driver2Color,
  driver2Data,
}: TelemetryChartProps) {
  const [selectedMetric, setSelectedMetric] = useState<"Speed" | "Throttle" | "Brake">("Speed");

  const d1Code = driver1Name || driverCode;
  const d1Color = driver1Color || driverColor;
  const d1Data = driver1Data || telemetryData || [];

  const d2Code = driver2Name;
  const d2Color = driver2Color || "#27F4D2";
  const d2Data = driver2Data || [];

  if (d1Data.length === 0 && d2Data.length === 0) {
    return (
      <div className="p-6 bg-slate-900 rounded-xl border border-slate-800 text-slate-400 text-center font-sans">
        No active telemetry stream loaded for {d1Code}.
      </div>
    );
  }

  const allPoints = [...d1Data, ...d2Data];
  const maxValue = Math.max(
    ...allPoints.map((d) => d[selectedMetric] ?? d[selectedMetric.toLowerCase()] ?? 1),
    100
  );

  const dataLen = Math.max(d1Data.length, d2Data.length, 1);

  return (
    <div className="p-6 bg-slate-900 rounded-xl border border-slate-800 space-y-4 font-sans shadow-xl">
      <div className="flex flex-wrap justify-between items-center border-b border-slate-800 pb-3 gap-3">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: d1Color }} />
            <span className="font-bold text-white uppercase text-sm tracking-wide">
              {d1Code}
            </span>
          </div>
          {d2Code && (
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: d2Color }} />
              <span className="font-bold text-white uppercase text-sm tracking-wide">
                {d2Code}
              </span>
            </div>
          )}
          <span className="text-xs text-slate-500 font-mono">LIVE TELEMETRY TRACE</span>
        </div>

        <div className="flex gap-2">
          {(["Speed", "Throttle", "Brake"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setSelectedMetric(m)}
              className={`px-3 py-1 rounded text-xs font-bold uppercase transition ${
                selectedMetric === m
                  ? "bg-red-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:bg-slate-700"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* SVG Dynamic Trace Chart */}
      <div className="h-52 w-full relative pt-4">
        <svg className="w-full h-full overflow-visible" viewBox={`0 0 ${dataLen} 100`}>
          {/* Driver 1 Polyline */}
          {d1Data.length > 0 && (
            <polyline
              fill="none"
              stroke={d1Color}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              points={d1Data
                .map((pt, idx) => {
                  const val = pt[selectedMetric] ?? pt[selectedMetric.toLowerCase()] ?? 0;
                  const y = 95 - (val / maxValue) * 85;
                  return `${idx},${y}`;
                })
                .join(" ")}
            />
          )}

          {/* Driver 2 Polyline */}
          {d2Data.length > 0 && (
            <polyline
              fill="none"
              stroke={d2Color}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray="4 2"
              points={d2Data
                .map((pt, idx) => {
                  const val = pt[selectedMetric] ?? pt[selectedMetric.toLowerCase()] ?? 0;
                  const y = 95 - (val / maxValue) * 85;
                  return `${idx},${y}`;
                })
                .join(" ")}
            />
          )}
        </svg>
      </div>

      <div className="flex justify-between text-xs text-slate-500 font-mono pt-2 border-t border-slate-800">
        <span>Start (Sector 1)</span>
        <span>Mid-Lap (Sector 2)</span>
        <span>Finish Line (Sector 3)</span>
      </div>
    </div>
  );
}

export default TelemetryChart;
