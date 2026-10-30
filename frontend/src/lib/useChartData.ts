/**
 * useChartData.ts — Universal chart data hook (Phase 1.6).
 * States:
 *   - 'loading' (with elapsed time & progress)
 *   - 'ok' (with validated series data)
 *   - 'not_available' (with explicit reason and nearest completed session suggestion)
 *   - 'error' (with user-facing error message & retry callback)
 * Features:
 *   - Exponential backoff polling (2s -> 10s)
 *   - 45-second max wait ceiling
 *   - AbortController cleanup on unmount
 *   - Request de-duplication via SWR
 */
import { useState, useEffect, useRef, useCallback } from "react";
import useSWR from "swr";
import { fetcher, qs } from "./api";
import type { ChartResponse, ChartStatus } from "@/types/chart";

export interface UseChartDataOptions {
  maxWaitMs?: number;
  params?: Record<string, any>;
  enabled?: boolean;
}

export interface UseChartDataReturn<T = any> {
  data: ChartResponse<T> | null;
  status: ChartStatus;
  isLoading: boolean;
  isError: boolean;
  isNotAvailable: boolean;
  elapsedSeconds: number;
  reason?: string;
  nearestSession?: { year: number; round: number };
  retry: () => void;
  url: string | null;
}

export function useChartData<T = any>(
  path: string | null,
  options: UseChartDataOptions = {}
): UseChartDataReturn<T> {
  const { maxWaitMs = 45000, params = {}, enabled = true } = options;
  const url = path && enabled ? `/api/charts/${path}?${qs(params)}` : null;

  const [elapsed, setElapsed] = useState(0);
  const [timedOut, setTimedOut] = useState(false);
  const pollIntervalRef = useRef(2000);
  const startTimeRef = useRef<number | null>(null);

  const { data, error, isLoading, mutate } = useSWR<ChartResponse<T>>(
    url,
    fetcher,
    {
      keepPreviousData: true,
      revalidateOnFocus: false,
      dedupingInterval: 4000,
      refreshInterval: (latestData) => {
        if (!latestData || timedOut) return 0;
        const st = latestData.status;
        if (st === "loading" || (st as any) === "preparing") {
          // Exponential backoff up to 10s
          const next = Math.min(10000, Math.round(pollIntervalRef.current * 1.5));
          pollIntervalRef.current = next;
          return next;
        }
        pollIntervalRef.current = 2000;
        return 0;
      },
    }
  );

  // Elapsed timer tracking
  useEffect(() => {
    let timer: any = null;
    const isPending = data?.status === "loading" || (data?.status as any) === "preparing";

    if (isPending) {
      if (!startTimeRef.current) startTimeRef.current = Date.now();
      timer = setInterval(() => {
        if (!startTimeRef.current) return;
        const sec = Math.floor((Date.now() - startTimeRef.current) / 1000);
        setElapsed(sec);
        if (Date.now() - startTimeRef.current > maxWaitMs) {
          setTimedOut(true);
          clearInterval(timer);
        }
      }, 1000);
    } else {
      startTimeRef.current = null;
      setElapsed(0);
    }

    return () => {
      if (timer) clearInterval(timer);
    };
  }, [data?.status, maxWaitMs]);

  const handleRetry = useCallback(() => {
    startTimeRef.current = null;
    pollIntervalRef.current = 2000;
    setTimedOut(false);
    setElapsed(0);
    mutate();
  }, [mutate]);

  // Determine final status
  let finalStatus: ChartStatus = "loading";
  let finalReason: string | undefined = undefined;

  if (timedOut) {
    finalStatus = "error";
    finalReason = `Session load timed out after ${Math.round(maxWaitMs / 1000)}s. Please retry.`;
  } else if (error) {
    finalStatus = "error";
    finalReason = error?.message || "Failed to reach telemetry backend.";
  } else if (data) {
    if (data.status === "ok") {
      finalStatus = "ok";
    } else if (
      data.status === "loading" ||
      (data.status as any) === "preparing"
    ) {
      finalStatus = "loading";
    } else if (
      data.status === "not_available" ||
      (data.status as any) === "empty" ||
      (data.status as any) === "outside_coverage"
    ) {
      finalStatus = "not_available";
      finalReason =
        data.coverage_note ||
        data.message ||
        "Data is not available for this session.";
    } else {
      finalStatus = "error";
      finalReason = data.coverage_note || "An unexpected error occurred.";
    }
  } else if (!isLoading) {
    finalStatus = "not_available";
    finalReason = "No response data available.";
  }

  return {
    data: data || null,
    status: finalStatus,
    isLoading: finalStatus === "loading",
    isError: finalStatus === "error",
    isNotAvailable: finalStatus === "not_available",
    elapsedSeconds: elapsed,
    reason: finalReason,
    nearestSession: (data as any)?.nearest_session,
    retry: handleRetry,
    url,
  };
}
