"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { t } from "@/lib/i18n";

interface Props {
  chartName?: string;
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ChartErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(
      `[ChartErrorBoundary: ${this.props.chartName || "Chart"}]`,
      error,
      errorInfo
    );
  }

  resetError = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div
          role="alert"
          className="min-h-[220px] flex flex-col items-center justify-center p-6 text-center border border-[var(--border)] rounded-lg bg-[var(--surface-2)] text-[var(--text-2)]"
        >
          <div className="text-[14px] font-semibold text-[var(--text)] mb-1">
            {this.props.chartName
              ? `${this.props.chartName} unavailable`
              : "Chart rendering error"}
          </div>
          <p className="text-[12px] text-[var(--text-3)] max-w-md mb-4 font-mono">
            {this.state.error?.message ||
              "An unexpected error occurred while rendering this visualization."}
          </p>
          <button
            type="button"
            onClick={this.resetError}
            className="px-3 py-1.5 text-[11px] font-medium border border-[var(--border)] rounded bg-[var(--surface)] hover:bg-[var(--raised)] text-[var(--text-2)] transition-colors"
          >
            {t("retry") || "Retry"}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

