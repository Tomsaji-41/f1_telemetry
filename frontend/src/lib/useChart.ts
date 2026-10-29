/**
 * useChart — SWR-based data hook with automatic polling for "preparing" status
 * and an explicit 45-second timeout with retry support (never infinite spinner).
 */
import { useState, useRef } from "react";
import useSWR from "swr";
import { fetcher, qs } from "./api";

export interface ChartData {
  status: string;
  source?: string;
  coverage_note?: string;
  fetched_at?: string;
  job_id?: string;
  eta_s?: number;
  [key: string]: any;
}

export function useChart<T extends ChartData = ChartData>(
  path: string | null,
  params: Record<string, any> = {}
) {
  const url = path ? `/api/charts/${path}?${qs(params)}` : null;
  const preparingStartRef = useRef<number | null>(null);
  const [timedOut, setTimedOut] = useState(false);

  const { data, error, isLoading, mutate } = useSWR<T>(url, fetcher, {
    keepPreviousData: true,
    refreshInterval: (latestData: T | undefined) => {
      if (timedOut) return 0;
      if (latestData?.status === "preparing") {
        if (!preparingStartRef.current) {
          preparingStartRef.current = Date.now();
        } else if (Date.now() - preparingStartRef.current > 45000) {
          setTimedOut(true);
          return 0;
        }
        return 2000;
      } else {
        preparingStartRef.current = null;
      }
      return 0;
    },
    revalidateOnFocus: false,
    dedupingInterval: 5000,
  });

  const handleRetry = () => {
    preparingStartRef.current = null;
    setTimedOut(false);
    mutate();
  };

  const finalData = timedOut
    ? ({
        ...data,
        status: "source_error",
        coverage_note: "Session data loading timed out after 45s. Please retry.",
      } as T)
    : data;

  return { data: finalData, error, isLoading, retry: handleRetry, url };
}
