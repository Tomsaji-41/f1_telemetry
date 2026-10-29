"use client";

/**
 * ChartState — universal status resolver for chart data.
 * Decides what to render: loading skeleton, preparing spinner, error, empty, outside_coverage, or children.
 */
import React from "react";
import { t } from "@/lib/i18n";
import { Skeleton } from "@/components/primitives/kit";

interface ChartStateProps {
  data: any;
  error: any;
  isLoading: boolean;
  retry: () => void;
  children: React.ReactNode;
  minHeight?: number;
}

export function ChartState({
  data,
  error,
  isLoading,
  retry,
  children,
  minHeight = 240,
}: ChartStateProps) {
  const box: React.CSSProperties = {
    minHeight,
    display: "grid",
    placeItems: "center",
    color: "var(--text-2)",
    padding: "1.5rem",
    textAlign: "center",
    fontSize: "0.8125rem",
  };

  if (error) {
    return (
      <div style={box} role="alert">
        <div>
          <p style={{ marginBottom: 8 }}>{t("chart.unreachable")}</p>
          <button
            onClick={retry}
            className="px-3 py-1.5 text-[11px] font-medium border border-[var(--border)] rounded bg-[var(--surface)] hover:bg-[var(--raised)] text-[var(--text-2)]"
          >
            {t("retry")}
          </button>
        </div>
      </div>
    );
  }

  if (isLoading && !data) {
    return (
      <div style={{ ...box, gap: 12 }} aria-busy="true">
        <div className="w-full space-y-3 px-4">
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-44 w-full" />
          <div className="flex gap-2">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-16" />
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={box}>
        <p>{t("chart.empty")}</p>
      </div>
    );
  }

  switch (data.status) {
    case "ok":
      return <>{children}</>;

    case "preparing":
    case "loading":
      return (
        <div style={box}>
          <div>
            <div
              className="inline-block w-5 h-5 border-2 border-[var(--text-3)] border-t-transparent rounded-full"
              style={{ animation: "spin 0.8s linear infinite" }}
            />
            <p style={{ marginTop: 8 }}>
              {t("chart.preparing")}{" "}
              {data.eta_s ? `(~${data.eta_s}s)` : ""}
            </p>
          </div>
        </div>
      );

    case "not_ingested":
      return (
        <div style={box}>
          <p>{data.coverage_note || "Data not ingested yet for this session."}</p>
        </div>
      );

    case "outside_coverage":
      return (
        <div style={box}>
          <p>{data.coverage_note || t("chart.outsideCoverage")}</p>
        </div>
      );

    case "not_published_yet":
      return (
        <div style={box}>
          <p>{t("chart.notPublished")}</p>
        </div>
      );

    case "source_error":
      return (
        <div style={box}>
          <div>
            <p style={{ marginBottom: 8 }}>{t("chart.sourceError")}</p>
            <button
              onClick={retry}
              className="px-3 py-1.5 text-[11px] font-medium border border-[var(--border)] rounded bg-[var(--surface)] hover:bg-[var(--raised)] text-[var(--text-2)]"
            >
              {t("retry")}
            </button>
          </div>
        </div>
      );

    case "empty":
    default:
      return (
        <div style={box}>
          <p>{data.coverage_note || t("chart.empty")}</p>
        </div>
      );
  }
}
