/**
 * Shared Chart Response Contract (Phase 1.4)
 * Mirrored from backend/charts/schema.py
 */

export type ChartStatus = "ok" | "loading" | "not_available" | "error" | "preparing";

export interface ChartResponse<T = any> {
  status: ChartStatus;
  source: string;
  coverage_note?: string;
  fetched_at: string;
  message?: string;
  series?: T[];
  axes?: Record<string, any>;
  job_id?: string;
  eta_s?: number;
  year?: number;
  round?: number;
  [key: string]: any;
}
