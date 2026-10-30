"use client";

import React, { useEffect } from "react";
import { ErrorState } from "@/components/primitives/kit";

export default function CircuitsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}): React.JSX.Element {
  useEffect(() => {
    console.error("Circuits route error:", error);
  }, [error]);

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <ErrorState
        title="Failed to load circuits catalog"
        message={error.message || "An unexpected error occurred while loading circuit telemetry."}
        source="Circuits Service"
        onRetry={() => reset()}
      />
    </div>
  );
}
