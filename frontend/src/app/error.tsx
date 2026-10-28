"use client";

import React, { useEffect } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/primitives/button";

export default function RootErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}): React.JSX.Element {
  useEffect(() => {
    console.error("Root error boundary caught:", error);
  }, [error]);

  return (
    <div className="min-h-[50vh] flex flex-col items-center justify-center text-center p-6 space-y-4">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-rose-500/10 text-rose-500 border border-rose-500/20">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <h2 className="text-xl font-bold text-white">Application Telemetry Disruption</h2>
      <p className="text-sm text-slate-400 max-w-md">
        An unexpected error occurred while processing telemetry stream data: {error.message}
      </p>
      <Button variant="primary" onClick={() => reset()} className="gap-2">
        <RotateCcw className="h-4 w-4" />
        <span>Reset Pipeline</span>
      </Button>
    </div>
  );
}
