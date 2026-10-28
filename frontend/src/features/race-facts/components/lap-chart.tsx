


"use client";

import React, { useMemo } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";
import { LapPosition } from "../types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/primitives/card";
import { Skeleton } from "@/components/primitives/skeleton";

const DRIVER_COLORS: Record<string, string> = {
  VER: "#3671C6",
  PER: "#1E41B0",
  HAM: "#27F4D2",
  RUS: "#6CD3BF",
  LEC: "#E8002D",
  SAI: "#FF2D55",
  NOR: "#FF8000",
  PIA: "#FF9E3B",
  ALO: "#229971",
  STR: "#35B589",
};

interface LapChartProps {
  lapPositions: LapPosition[];
  isLoading?: boolean;
  isError?: boolean;
}

export function LapProgressionChart({ lapPositions, isLoading = false, isError = false }: LapChartProps): React.JSX.Element {
  const chartData = useMemo(() => {
    if (!lapPositions || lapPositions.length === 0) return [];
    
    // Group by lap
    const lapMap = new Map<number, Record<string, number | null>>();
    const allDrivers = new Set<string>();

    for (const item of lapPositions) {
      allDrivers.add(item.driver);
      const currentLapData = lapMap.get(item.lap) || { lap: item.lap };
      currentLapData[item.driver] = item.position;
      lapMap.set(item.lap, currentLapData);
    }

    return Array.from(lapMap.values()).sort((a, b) => (Number(a.lap) - Number(b.lap)));
  }, [lapPositions]);

  const topDrivers = useMemo(() => {
    if (!lapPositions) return [];
    const drivers = Array.from(new Set(lapPositions.map((l) => l.driver)));
    return drivers.slice(0, 10);
  }, [lapPositions]);

  if (isLoading) {
    return (
      <Card className="h-[420px] flex flex-col justify-between p-6">
        <Skeleton className="h-6 w-48 mb-4" />
        <Skeleton className="h-[300px] w-full" />
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="h-[420px] flex items-center justify-center p-6 border-rose-800/40">
        <p className="text-rose-400 font-medium">Failed to load lap progression chart.</p>
      </Card>
    );
  }

  if (chartData.length === 0) {
    return (
      <Card className="h-[420px] flex items-center justify-center p-6">
        <p className="text-slate-500 font-medium">No lap telemetry points available for this session.</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-bold text-white flex items-center justify-between">
          <span>Lap-by-Lap Position Progression</span>
          <span className="text-xs text-slate-400 font-normal">Top 10 Active Drivers</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="h-[360px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="lap" stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 11 }} label={{ value: "Lap Number", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }} />
            <YAxis reversed domain={[1, 20]} ticks={[1, 5, 10, 15, 20]} stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 11 }} label={{ value: "Position", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "8px", color: "#f8fafc", fontSize: "12px" }}
              formatter={(val: number, name: string) => [`P${val}`, name]}
            />
            <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "10px" }} />
            {topDrivers.map((driver) => (
              <Line
                key={driver}
                type="monotone"
                dataKey={driver}
                stroke={DRIVER_COLORS[driver] || "#94a3b8"}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
