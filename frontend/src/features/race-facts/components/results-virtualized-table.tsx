"use client";

import React, { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { RaceResult } from "../types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/primitives/card";
import { Badge } from "@/components/primitives/badge";

interface ResultsVirtualizedTableProps {
  results: RaceResult[];
}

export function ResultsVirtualizedTable({ results }: ResultsVirtualizedTableProps): React.JSX.Element {
  const parentRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer = useVirtualizer({
    count: results.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,
    overscan: 5,
  });

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-bold text-white flex items-center justify-between">
          <span>Official Classification & Grid Delta</span>
          <Badge variant="outline">{results.length} Drivers</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {/* Header Row */}
        <div className="grid grid-cols-12 border-b border-slate-800 bg-slate-950/80 px-4 py-2.5 text-xs font-semibold text-slate-400">
          <div className="col-span-1">POS</div>
          <div className="col-span-3">DRIVER</div>
          <div className="col-span-4">TEAM</div>
          <div className="col-span-2 text-center">GRID / DELTA</div>
          <div className="col-span-2 text-right">POINTS</div>
        </div>

        {/* Virtualized Container */}
        <div
          ref={parentRef}
          className="h-[360px] overflow-auto divide-y divide-slate-800/40"
          tabIndex={0}
          aria-label="Race Results Table"
        >
          <div
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              width: "100%",
              position: "relative",
            }}
          >
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const row = results[virtualRow.index];
              const gridDelta = row.position !== null ? row.grid - row.position : 0;

              return (
                <div
                  key={row.code}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: `${virtualRow.size}px`,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                  className="grid grid-cols-12 items-center px-4 text-xs text-slate-200 hover:bg-slate-800/40 transition-colors"
                >
                  <div className="col-span-1 font-bold text-white">
                    {row.position ? `P${row.position}` : "DNF"}
                  </div>
                  <div className="col-span-3 flex items-center gap-1.5">
                    <span className="font-mono font-bold text-red-400">{row.code}</span>
                    <span className="truncate text-slate-400 text-[11px] hidden sm:inline">{row.full_name}</span>
                  </div>
                  <div className="col-span-4 truncate text-slate-300">{row.team}</div>
                  <div className="col-span-2 text-center flex items-center justify-center gap-1">
                    <span className="text-slate-400">P{row.grid}</span>
                    {gridDelta > 0 && (
                      <span className="text-emerald-400 font-bold text-[10px]">+{gridDelta}</span>
                    )}
                    {gridDelta < 0 && (
                      <span className="text-rose-400 font-bold text-[10px]">{gridDelta}</span>
                    )}
                  </div>
                  <div className="col-span-2 text-right font-semibold text-amber-300">
                    {row.points > 0 ? `+${row.points} pts` : "0 pts"}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
