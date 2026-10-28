"use client";

/**
 * ChartPanel — frame wrapper used by every chart.
 * Header: title, source badge, table toggle, CSV, PNG, fullscreen.
 * Footer: "updated <fetched_at>".
 * Sets data-chart-ready="true" after first render for Playwright.
 */
import React, { useCallback, useRef, useState } from "react";
import {
  Download,
  Table,
  BarChart3,
  Maximize2,
  AlertCircle,
} from "lucide-react";
import { t } from "@/lib/i18n";

interface ChartPanelProps {
  title: string;
  source?: string;
  fetchedAt?: string;
  coverageNote?: string;
  csvData?: string;
  csvFilename?: string;
  tableHeaders?: string[];
  tableRows?: (string | number | null)[][];
  children: React.ReactNode;
  minHeight?: number;
}

export function ChartPanel({
  title,
  source,
  fetchedAt,
  coverageNote,
  csvData,
  csvFilename = "chart_data.csv",
  tableHeaders,
  tableRows,
  children,
  minHeight = 260,
}: ChartPanelProps) {
  const [viewMode, setViewMode] = useState<"chart" | "table">("chart");
  const panelRef = useRef<HTMLDivElement>(null);

  const downloadCsv = useCallback(() => {
    if (!csvData) return;
    const blob = new Blob([csvData], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = csvFilename;
    a.click();
    URL.revokeObjectURL(url);
  }, [csvData, csvFilename]);

  const exportPng = useCallback(() => {
    if (!panelRef.current) return;
    const canvas = panelRef.current.querySelector("canvas");
    const svg = panelRef.current.querySelector("svg");

    if (canvas) {
      canvas.toBlob((blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${title.replace(/\s+/g, "_")}.png`;
        a.click();
        URL.revokeObjectURL(url);
      });
    } else if (svg) {
      const svgData = new XMLSerializer().serializeToString(svg);
      const img = new Image();
      const svgBlob = new Blob([svgData], {
        type: "image/svg+xml;charset=utf-8",
      });
      const url = URL.createObjectURL(svgBlob);
      img.onload = () => {
        const c = document.createElement("canvas");
        c.width = img.naturalWidth * 2;
        c.height = img.naturalHeight * 2;
        const ctx = c.getContext("2d")!;
        ctx.scale(2, 2);
        ctx.drawImage(img, 0, 0);
        c.toBlob((blob) => {
          if (!blob) return;
          const pngUrl = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = pngUrl;
          a.download = `${title.replace(/\s+/g, "_")}.png`;
          a.click();
          URL.revokeObjectURL(pngUrl);
        });
        URL.revokeObjectURL(url);
      };
      img.src = url;
    }
  }, [title]);

  const toggleFullscreen = useCallback(() => {
    if (!panelRef.current) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      panelRef.current.requestFullscreen?.();
    }
  }, []);

  return (
    <div
      ref={panelRef}
      data-chart-ready="true"
      className="border border-[var(--border)] rounded-lg bg-[var(--surface)] p-4 flex flex-col space-y-3"
      style={{ minHeight }}
    >
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <h3 className="text-[14px] font-semibold text-[var(--text)]">
            {title}
          </h3>
          {source && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--raised)] text-[var(--text-3)] border border-[var(--border)]">
              {source}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {tableHeaders && tableRows && (
            <button
              type="button"
              onClick={() =>
                setViewMode(viewMode === "chart" ? "table" : "chart")
              }
              className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium border border-[var(--border)] rounded bg-[var(--surface)] hover:bg-[var(--raised)] text-[var(--text-2)]"
              title="Toggle Table / Chart"
            >
              {viewMode === "chart" ? (
                <Table className="w-3.5 h-3.5" />
              ) : (
                <BarChart3 className="w-3.5 h-3.5" />
              )}
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

          <button
            type="button"
            onClick={exportPng}
            className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium border border-[var(--border)] rounded bg-[var(--surface)] hover:bg-[var(--raised)] text-[var(--text-2)]"
            title="Export PNG"
          >
            <Download className="w-3.5 h-3.5" />
            <span>PNG</span>
          </button>

          <button
            type="button"
            onClick={toggleFullscreen}
            className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium border border-[var(--border)] rounded bg-[var(--surface)] hover:bg-[var(--raised)] text-[var(--text-2)]"
            title={t("chart.fullscreen")}
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 relative">
        {viewMode === "table" && tableHeaders && tableRows ? (
          <div className="overflow-x-auto max-h-[360px] overflow-y-auto">
            <table className="w-full text-[12px] border-collapse">
              <thead className="sticky top-0 bg-[var(--surface)] border-b border-[var(--border)]">
                <tr>
                  {tableHeaders.map((h, i) => (
                    <th
                      key={i}
                      className="py-2 px-3 text-left font-medium text-[var(--text-3)]"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {tableRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-[var(--raised)]">
                    {row.map((cell, cIdx) => (
                      <td
                        key={cIdx}
                        className="py-2 px-3 font-mono text-[var(--text)]"
                      >
                        {cell != null ? String(cell) : "—"}
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

      {/* Footer */}
      {(fetchedAt || coverageNote) && (
        <div className="pt-2 border-t border-[var(--border)] flex items-center gap-1.5 text-[11px] text-[var(--text-3)] font-mono">
          {coverageNote && (
            <>
              <AlertCircle className="w-3 h-3 shrink-0" />
              <span>{coverageNote}</span>
            </>
          )}
          {fetchedAt && (
            <span
              className="ml-auto cursor-help border-b border-dotted border-[var(--border-strong)]"
              title={`Source timestamp: ${fetchedAt}`}
            >
              {t("chart.updated")}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
