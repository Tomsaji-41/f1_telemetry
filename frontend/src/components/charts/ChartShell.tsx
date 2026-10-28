"use client";

import React, { useState, useRef } from "react";
import { Download, Table, BarChart3, AlertCircle } from "lucide-react";
import { EmptyState, Skeleton, ErrorState } from "../primitives/kit";
import { useInspector } from "../layouts/inspector-drawer";

export interface ChartShellProps {
  title: string;
  subtitle?: string;
  source?: string;
  coverageNote?: string;
  loading?: boolean;
  empty?: boolean;
  emptyReason?: string;
  error?: { message?: string; url?: string; status?: number | string } | string | null;
  onRetry?: () => void;
  csvData?: string;
  csvFilename?: string;
  tableHeaders?: string[];
  tableRows?: (string | number)[][];
  children: React.ReactNode;
}

export function ChartShell({
  title,
  subtitle,
  source = "FastF1 & Jolpica",
  coverageNote,
  loading = false,
  empty = false,
  emptyReason,
  error = null,
  onRetry,
  csvData,
  csvFilename = "telemetry_data.csv",
  tableHeaders,
  tableRows,
  children,
}: ChartShellProps) {
  const [viewMode, setViewMode] = useState<"chart" | "table">("chart");
  const chartRef = useRef<HTMLDivElement>(null);

  const downloadCsv = () => {
    if (!csvData) return;
    const blob = new Blob([csvData], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = csvFilename;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-4 flex flex-col space-y-3">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[var(--border)]">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-[14px] font-semibold text-[var(--text)]">{title}</h3>
            {source && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--raised)] text-[var(--text-3)] border border-[var(--border)]">
                {source}
              </span>
            )}
          </div>
          {subtitle && (
            <p className="text-[12px] text-[var(--text-3)] mt-0.5">{subtitle}</p>
          )}
        </div>

        {/* Toolbar actions */}
        <div className="flex items-center gap-1.5">
          {tableHeaders && tableRows && (
            <button
              type="button"
              onClick={() => setViewMode(viewMode === "chart" ? "table" : "chart")}
              className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium border border-[var(--border)] rounded bg-[var(--surface)] hover:bg-[var(--raised)] text-[var(--text-2)]"
              title="Toggle Table / Chart"
            >
              {viewMode === "chart" ? <Table className="w-3.5 h-3.5" /> : <BarChart3 className="w-3.5 h-3.5" />}
              <span>{viewMode === "chart" ? "Table" : "Chart"}</span>
            </button>
          )}

          {csvData && (
            <button
              type="button"
              onClick={downloadCsv}
              className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium border border-[var(--border)] rounded bg-[var(--surface)] hover:bg-[var(--raised)] text-[var(--text-2)]"
              title="Export CSV"
            >
              <Download className="w-3.5 h-3.5" />
              <span>CSV</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div ref={chartRef} className="min-h-[260px] relative flex flex-col justify-center">
        {loading ? (
          <div className="space-y-3 p-4">
            <Skeleton className="h-6 w-1/3" />
            <Skeleton className="h-44 w-full" />
            <div className="flex gap-2">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-16" />
            </div>
          </div>
        ) : error ? (
          <ErrorState
            message={typeof error === "string" ? error : error.message}
            url={typeof error === "object" ? error?.url : undefined}
            status={typeof error === "object" ? error?.status : undefined}
            onRetry={onRetry}
          />
        ) : empty ? (
          <EmptyState
            message="No chart data recorded for selected session."
            reason={emptyReason || coverageNote}
          />
        ) : viewMode === "table" && tableHeaders && tableRows ? (
          <div className="overflow-x-auto max-h-[360px] overflow-y-auto">
            <table className="w-full text-[12px] border-collapse">
              <thead className="sticky top-0 bg-[var(--surface)] border-b border-[var(--border)]">
                <tr>
                  {tableHeaders.map((h, i) => (
                    <th key={i} className="py-2 px-3 text-left font-medium text-[var(--text-3)]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {tableRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-[var(--raised)]">
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="py-2 px-3 font-mono text-[var(--text)]">
                        {String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          children
        )}
      </div>

      {/* Coverage note */}
      {coverageNote && (
        <div className="pt-2 border-t border-[var(--border)] flex items-center gap-1.5 text-[11px] text-[var(--text-3)] font-mono">
          <AlertCircle className="w-3 h-3 text-[var(--text-3)] shrink-0" />
          <span>{coverageNote}</span>
        </div>
      )}
    </div>
  );
}
