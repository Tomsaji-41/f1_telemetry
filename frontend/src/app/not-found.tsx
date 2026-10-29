"use client";

import React from "react";
import Link from "next/link";
import { Flag, ArrowLeft } from "lucide-react";
import { Button } from "@/components/primitives/button";

export default function NotFound(): React.JSX.Element {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center p-6 space-y-4">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--raised)] border border-[var(--border)] text-[var(--accent)]">
        <Flag className="h-7 w-7" />
      </div>
      <div className="space-y-1">
        <h2 className="text-2xl font-bold text-[var(--text)] tracking-tight">404 — Telemetry Out of Bounds</h2>
        <p className="text-sm text-[var(--text-3)] max-w-md">
          The requested timing feed, session, or telemetry channel is not available or does not exist.
        </p>
      </div>
      <div className="pt-2">
        <Link href="/">
          <Button variant="primary" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            <span>Return to Dashboard</span>
          </Button>
        </Link>
      </div>
    </div>
  );
}
