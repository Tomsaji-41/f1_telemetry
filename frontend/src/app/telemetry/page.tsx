"use client";

import React, { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Skeleton } from "@/components/primitives/kit";
import { TelemetryTeleportView } from "@/features/telemetry/components/TelemetryTeleportView";
import en from "@/content/en.json";

function TelemetryContent(): React.JSX.Element {
  const searchParams = useSearchParams();
  const currentYear = new Date().getFullYear();
  const year = parseInt(searchParams.get("year") || String(currentYear), 10);
  const round = parseInt(searchParams.get("round") || "1", 10);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="pb-4 border-b border-[var(--border)]">
        <h1 className="text-[28px] font-semibold text-[var(--text)] tracking-tight">
          {en.telemetry.title}
        </h1>
        <p className="text-[13px] text-[var(--text-3)] mt-0.5">
          Two-driver synchronous telemetry overlay, circuit map, braking telemetry, and aerodynamic proxies.
        </p>
      </div>

      {/* Telemetry Teleport View */}
      <TelemetryTeleportView year={year} round={round} />
    </div>
  );
}

export default function TelemetryPage(): React.JSX.Element {
  return (
    <Suspense
      fallback={
        <div className="p-8 space-y-4">
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      }
    >
      <TelemetryContent />
    </Suspense>
  );
}
