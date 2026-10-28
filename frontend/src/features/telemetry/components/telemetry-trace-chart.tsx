"use client";

import React, { useMemo } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";
import { TelemetryComparison } from "../types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/primitives/card";
import { Button } from "@/components/primitives/button";
import { Skeleton } from "@/components/primitives/skeleton";
import { useTelemetryStore } from "../store/telemetry-store";

interface TelemetryTraceChartProps {
  data: TelemetryComparison;
  isLoading?: boolean;
  isError?: boolean;
}

export function TelemetryTraceChart({ data, isLoading = false, isError = false }: TelemetryTraceChartProps): React.JSX.Element {
  const { activeMetric, setActiveMetric } = useTelemetryStore();
  const d1 = data.driver1;
  const d2 = data.driver2;

  const combinedData = useMemo(() => {
    if (!d1 || !d2 || !d1.distance) return [];
    
    // Subsample distance array for 60fps chart rendering performance
    const step = Math.max(1, Math.floor(d1.distance.length / 250));
    const points = [];

    for (let i = 0; i < d1.distance.length; i += step) {
      points.push({
        distance: Math.round(d1.distance[i]),
        d1_val: activeMetric === "speed" ? d1.speed[i] : activeMetric === "throttle" ? d1.throttle[i] : d1.brake[i] * 100,
        d2_val: activeMetric === "speed" ? (d2.speed[i] ?? 0) : activeMetric === "throttle" ? (d2.throttle[i] ?? 0) : (d2.brake[i] ?? 0) * 100,
      });
    }

    return points;
  }, [d1, d2, activeMetric]);

  if (isLoading) {
    return (
      <Card className="h-[460px] flex flex-col justify-between p-6">
        <Skeleton className="h-6 w-48 mb-4" />
        <Skeleton className="h-[340px] w-full" />
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="h-[460px] flex items-center justify-center p-6 border-rose-800/40">
        <p className="text-rose-400 font-medium">Failed to extract driver telemetry overlay.</p>
      </Card>
    );
  }

  const metricLabels = {
    speed: "Speed (km/h)",
    throttle: "Throttle (%)",
    brake: "Brake Application (On/Off %)",
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="text-base font-bold text-white flex items-center gap-2">
            <span>Fastest Lap Telemetry Overlay:</span>
            <span className="text-red-400 font-mono">{d1.code}</span>
            <span className="text-slate-500">vs</span>
            <span className="text-teal-400 font-mono">{d2.code}</span>
          </CardTitle>

          <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800">
            {(["speed", "throttle", "brake"] as const).map((metric) => (
              <Button
                key={metric}
                size="sm"
                variant={activeMetric === metric ? "primary" : "ghost"}
                className="text-xs capitalize h-7 px-2.5"
                onClick={() => setActiveMetric(metric)}
              >
                {metric}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="h-[380px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={combinedData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="distance" stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 11 }} label={{ value: "Lap Distance (m)", position: "insideBottom", offset: -10, fill: "#94a3b8", fontSize: 11 }} />
            <YAxis stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 11 }} label={{ value: metricLabels[activeMetric], angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "8px", color: "#f8fafc", fontSize: "12px" }}
              formatter={(val: number, name: string) => [val, name === "d1_val" ? d1.code : d2.code]}
            />
            <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }} formatter={(value) => (value === "d1_val" ? d1.code : d2.code)} />
            <Line type="monotone" dataKey="d1_val" name="d1_val" stroke="#E10600" strokeWidth={2} dot={false} isAnimationActive={true} />
            <Line type="monotone" dataKey="d2_val" name="d2_val" stroke="#27F4D2" strokeWidth={2} dot={false} isAnimationActive={true} />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
