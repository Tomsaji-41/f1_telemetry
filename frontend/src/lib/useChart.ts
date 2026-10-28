/**
 * useChart — SWR-based data hook with automatic polling for "preparing" status.
 * All chart components use this instead of raw fetch.
 */
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
  const { data, error, isLoading, mutate } = useSWR<T>(url, fetcher, {
    keepPreviousData: true,
    refreshInterval: (latestData: T | undefined) =>
      latestData?.status === "preparing" ? 2000 : 0,
    revalidateOnFocus: false,
    dedupingInterval: 5000,
  });

  return { data, error, isLoading, retry: () => mutate(), url };
}
