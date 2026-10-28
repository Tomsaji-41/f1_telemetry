"use client";

import React, { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { brand } from "@/config/brand";
import { DEMO_LABEL, DEMO_MODE } from "@/demo/demoData";

export function AppFooter({ buildStamp }: { buildStamp?: string }) {
  const [fetchedAt, setFetchedAt] = useState<string>("");
  const [sources, setSources] = useState<string[]>(["Jolpica", "FastF1", "OpenF1"]);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.fetched_at) {
          setFetchedAt(data.fetched_at);
        }
        if (data?.sources && Array.isArray(data.sources)) {
          const allowed = ["Jolpica", "FastF1", "OpenF1"];
          const filtered = data.sources.filter((s: string) => allowed.includes(s));
          if (filtered.length > 0) setSources(filtered);
        }
      })
      .catch(() => {});
  }, []);

  return (
    <footer className="border-t border-[var(--border)] py-4 px-4 font-mono text-[11px] text-[var(--text-3)] bg-[var(--surface)] select-none">
      <div className="flex flex-col items-center justify-center gap-2 max-w-[1480px] mx-auto text-center">
        {/* Brand logo at 20px height */}
        <div className="flex items-center gap-2">
          <Logo height={20} />
          <span className="text-[12px] font-semibold text-[var(--text)] tracking-tight">
            {brand.appName}
          </span>
        </div>

        {/* Sources and Freshness */}
        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
          <span>
            Sources:{" "}
            <span className="text-[var(--text-2)] font-medium">
              {sources.join(", ")}
            </span>
          </span>
          {fetchedAt && (
            <>
              <span className="text-[var(--border-strong)]">•</span>
              <span>
                Fetched: <span className="text-[var(--text-2)]">{fetchedAt}</span>
              </span>
            </>
          )}
          {buildStamp && (
            <>
              <span className="text-[var(--border-strong)]">•</span>
              <span>
                Build: <span className="text-[var(--accent)]">{buildStamp}</span>
              </span>
            </>
          )}
        </div>

        {/* Mandatory Legal Disclaimer on every page */}
        {DEMO_MODE && (
          <p className="text-[11px] font-mono text-amber-300 bg-amber-500/10 px-3 py-1 border border-amber-500/20 rounded max-w-2xl mt-1">
            {DEMO_LABEL}
          </p>
        )}
        <p className="text-[10px] text-[var(--text-3)] max-w-2xl leading-relaxed mt-1">
          {brand.disclaimer}
        </p>
      </div>
    </footer>
  );
}
