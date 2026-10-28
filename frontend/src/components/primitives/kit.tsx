"use client";

import React, { useState, useEffect } from "react";

// ============================================================================
// D4 COMPONENT KIT
// ============================================================================

export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`border rounded-lg bg-[var(--surface)] border-[var(--border)] p-4 transition-all duration-[var(--dur-2)] ${className}`}
      style={{ borderRadius: "var(--radius-m)" }}
    >
      {(title || action) && (
        <div className="flex items-center justify-between pb-3 mb-4 border-b border-[var(--border)]">
          <div>
            {title && (
              <h2 className="text-[16px] font-semibold text-[var(--text)] tracking-tight">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="text-[12px] text-[var(--text-3)] mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

export function Stat({
  label,
  value,
  unit,
  delta,
  deltaType = "neutral",
}: {
  label: string;
  value: string | number;
  unit?: string;
  delta?: string | number;
  deltaType?: "positive" | "negative" | "neutral";
}) {
  const deltaColor =
    deltaType === "positive"
      ? "text-[var(--positive)]"
      : deltaType === "negative"
      ? "text-[var(--negative)]"
      : "text-[var(--text-3)]";

  return (
    <div className="flex flex-col">
      <span className="text-[12px] font-medium text-[var(--text-3)]">{label}</span>
      <div className="flex items-baseline gap-1 mt-1 font-mono">
        <span className="text-[28px] font-semibold text-[var(--text)] tracking-tight leading-none">
          {value}
        </span>
        {unit && <span className="text-[13px] text-[var(--text-2)]">{unit}</span>}
      </div>
      {delta !== undefined && (
        <span className={`text-[12px] font-mono mt-1 ${deltaColor}`}>
          {delta}
        </span>
      )}
    </div>
  );
}

export function TyreBadge({
  compound,
  size = "md",
}: {
  compound: string;
  size?: "sm" | "md";
}) {
  const norm = compound.toUpperCase();
  let color = "var(--tyre-hard)";
  let letter = "H";

  if (norm.includes("SOFT") || norm === "S") {
    color = "var(--tyre-soft)";
    letter = "S";
  } else if (norm.includes("MEDIUM") || norm === "M") {
    color = "var(--tyre-medium)";
    letter = "M";
  } else if (norm.includes("HARD") || norm === "H") {
    color = "var(--tyre-hard)";
    letter = "H";
  } else if (norm.includes("INTER") || norm === "I") {
    color = "var(--tyre-inter)";
    letter = "I";
  } else if (norm.includes("WET") || norm === "W") {
    color = "var(--tyre-wet)";
    letter = "W";
  }

  const dim = size === "sm" ? "w-5 h-5 text-[10px]" : "w-6 h-6 text-[12px]";

  return (
    <span
      className={`inline-flex items-center justify-center font-mono font-bold rounded-full border border-black/20 ${dim}`}
      style={{ backgroundColor: color, color: norm.includes("HARD") ? "#0B0F14" : "#FFFFFF" }}
      title={`${compound} compound`}
    >
      {letter}
    </span>
  );
}

export function StatusBadge({
  status,
}: {
  status: "completed" | "live" | "upcoming" | "preparing" | "stale";
}) {
  const styles = {
    completed: "bg-[var(--raised)] text-[var(--text-2)] border-[var(--border)]",
    live: "bg-red-500/10 text-[var(--live)] border-red-500/30 animate-pulse",
    upcoming: "bg-blue-500/10 text-[var(--accent)] border-blue-500/30",
    preparing: "bg-amber-500/10 text-[var(--warning)] border-amber-500/30",
    stale: "bg-[var(--raised)] text-[var(--text-3)] border-[var(--border)]",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[12px] font-medium border rounded ${styles[status]}`}
      style={{ borderRadius: "var(--radius-s)" }}
    >
      {status === "live" && <span className="w-1.5 h-1.5 rounded-full bg-[var(--live)]" />}
      {status.toUpperCase()}
    </span>
  );
}

export function DriverChip({
  code,
  colour = "var(--accent)",
  selected = false,
  onToggle,
}: {
  code: string;
  colour?: string;
  selected?: boolean;
  onToggle?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`inline-flex items-center gap-2 px-2.5 py-1 text-[12px] font-mono border rounded transition-colors ${
        selected
          ? "bg-[var(--raised)] border-[var(--accent)] text-[var(--text)] font-semibold"
          : "bg-[var(--surface)] border-[var(--border)] text-[var(--text-2)] hover:border-[var(--border-strong)]"
      }`}
      style={{ borderRadius: "var(--radius-s)" }}
    >
      <span
        className="w-1.5 h-3 rounded-full"
        style={{ backgroundColor: colour }}
      />
      <span>{code}</span>
    </button>
  );
}

export function EmptyState({
  message = "No telemetry records found for current parameters.",
  reason,
}: {
  message?: string;
  reason?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center border border-dashed border-[var(--border)] rounded-lg bg-[var(--surface)]">
      <div className="w-10 h-10 rounded-full bg-[var(--raised)] flex items-center justify-center text-[var(--text-3)] mb-3">
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <p className="text-[14px] font-medium text-[var(--text-2)]">{message}</p>
      {reason && <p className="text-[12px] text-[var(--text-3)] mt-1">{reason}</p>}
    </div>
  );
}

export function ErrorState({
  message = "Cannot reach the data service. Retry",
  url,
  status,
  onRetry,
}: {
  message?: string;
  url?: string;
  status?: number | string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-8 px-4 text-center border border-red-500/20 rounded-lg bg-red-500/5">
      <p className="text-[14px] text-[var(--negative)] font-medium">
        {message.includes("Cannot reach the data service") ? message : `Cannot reach the data service. Retry${status ? ` (${status})` : ""}`}
      </p>
      {(url || status) && (
        <p className="text-[12px] font-mono text-[var(--text-3)] mt-1.5 break-all">
          {url ? `URL: ${url}` : ""} {status ? `[Status: ${status}]` : ""}
        </p>
      )}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 px-3 py-1.5 text-[12px] font-medium text-white bg-[var(--accent)] hover:bg-[var(--accent-hover)] rounded transition-colors"
          style={{ borderRadius: "var(--radius-s)" }}
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function Skeleton({
  className = "h-4 w-full",
}: {
  className?: string;
}) {
  return (
    <div
      className={`animate-pulse bg-[var(--raised)] rounded ${className}`}
      style={{ borderRadius: "var(--radius-s)" }}
    />
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  className = "",
}: {
  options: { label: string; value: T }[];
  value: T;
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      className={`tabs inline-flex p-1 bg-[var(--raised)] border border-[var(--border)] rounded ${className}`}
      style={{ borderRadius: "var(--radius-m)" }}
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          role="tab"
          aria-selected={value === opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`px-3 py-1 text-[12px] font-medium rounded transition-all duration-[var(--dur-1)] ${
            value === opt.value
              ? "font-semibold"
              : "text-[var(--text-2)] hover:text-[var(--text)]"
          }`}
          style={{ borderRadius: "var(--radius-s)" }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export function DataTable<T extends Record<string, any>>({
  headers,
  data,
  keyExtractor,
  renderRow,
  stickyHeader = true,
}: {
  headers: { key: string; label: string; align?: "left" | "right" | "center" }[];
  data: T[];
  keyExtractor: (item: T, index: number) => string | number;
  renderRow: (item: T, index: number) => React.ReactNode;
  stickyHeader?: boolean;
}) {
  return (
    <div className="w-full overflow-x-auto border border-[var(--border)] rounded-lg" style={{ borderRadius: "var(--radius-m)" }}>
      <table className="w-full text-[13px] border-collapse">
        <thead className={stickyHeader ? "sticky top-0 bg-[var(--surface)] z-10" : "bg-[var(--surface)]"}>
          <tr className="border-b border-[var(--border)] h-10">
            {headers.map((h) => (
              <th
                key={h.key}
                className={`px-3 font-medium text-[var(--text-2)] text-[12px] ${
                  h.align === "right" ? "text-right" : h.align === "center" ? "text-center" : "text-left"
                }`}
              >
                {h.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)] bg-[var(--surface)]">
          {data.map((item, idx) => (
            <tr
              key={keyExtractor(item, idx)}
              className="h-10 hover:bg-[var(--raised)] transition-colors"
            >
              {renderRow(item, idx)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
