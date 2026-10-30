/**
 * Single API client module for Pit Boss telemetry.
 * All URLs are constructed and fetched here using relative /api paths.
 * Connects directly to backend FastAPI proxy.
 */

export interface HealthResponse {
  status: string;
  fetched_at?: string;
  sources?: string[];
  keys: {
    gemini_configured: boolean;
    groq_configured: boolean;
  };
  models?: Record<string, string>;
  cache?: Record<string, any>;
  source_reachability?: Record<string, string>;
}

export function getClientHeaders(): Record<string, string> {
  const clientId =
    typeof window !== "undefined"
      ? localStorage.getItem("pitboss_client_id") || "web-client"
      : "server";
  return {
    "Content-Type": "application/json",
    "X-Client-Id": clientId,
  };
}

export async function fetchApi<T = any>(endpoint: string, options?: RequestInit): Promise<T> {
  const path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = path.startsWith("/api") ? path : `/api${path}`;

  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        ...getClientHeaders(),
        ...options?.headers,
      },
    });

    if (!res.ok) {
      console.error(`[API Error] Cannot reach the data service: ${res.status} ${res.statusText} at ${url}`);
      const err: any = new Error(`Cannot reach the data service. Retry (URL: ${url}, Status: ${res.status})`);
      err.url = url;
      err.status = res.status;
      throw err;
    }

    return await res.json();
  } catch (err: any) {
    if (!err.url) {
      err.url = url;
      err.status = err.status || "offline";
    }
    console.error(`[Network Error] Cannot reach the data service at ${url}:`, err);
    throw err;
  }
}

export async function checkHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>("/api/health");
}

// ── Chart-specific fetcher and helpers with in-flight deduplication & client SWR ────

export class ApiError extends Error {
  url: string;
  statusCode: number;
  constructor(url: string, statusCode: number, message?: string) {
    super(message || `API error ${statusCode} at ${url}`);
    this.url = url;
    this.statusCode = statusCode;
    this.name = "ApiError";
  }
}

// In-flight request deduplication (prevents React StrictMode double-fetch)
const _IN_FLIGHT_REQUESTS = new Map<string, Promise<any>>();
const _CLIENT_CACHE = new Map<string, { data: any; timestamp: number }>();

/**
 * High-performance fetcher with in-flight request de-duplication (P4)
 * and micro-caching to eliminate duplicate requests and StrictMode re-fetches.
 */
export async function fetcher<T = any>(url: string, bypassCache = false): Promise<T> {
  const now = Date.now();

  // Check client micro-cache (valid for 4 seconds to deduplicate rapid consecutive mounts)
  if (!bypassCache) {
    const cached = _CLIENT_CACHE.get(url);
    if (cached && now - cached.timestamp < 4000) {
      return cached.data as T;
    }
  }

  // Check if identical request is already in-flight
  if (_IN_FLIGHT_REQUESTS.has(url)) {
    return _IN_FLIGHT_REQUESTS.get(url) as Promise<T>;
  }

  const reqPromise = (async () => {
    try {
      const r = await fetch(url, { headers: { Accept: "application/json" } });
      if (!r.ok) {
        console.error("API error", r.status, url);
        throw new ApiError(url, r.status);
      }
      const data = await r.json();
      _CLIENT_CACHE.set(url, { data, timestamp: Date.now() });
      return data;
    } finally {
      // Clean up in-flight tracker shortly after resolution
      setTimeout(() => {
        _IN_FLIGHT_REQUESTS.delete(url);
      }, 50);
    }
  })();

  _IN_FLIGHT_REQUESTS.set(url, reqPromise);
  return reqPromise;
}

/**
 * Build a query string from an object.
 * Arrays are expanded to repeated keys, null/empty values are dropped.
 */
export const qs = (p: Record<string, any>): string =>
  new URLSearchParams(
    Object.entries(p)
      .filter(([, v]) => v != null && v !== "")
      .flatMap(([k, v]) =>
        Array.isArray(v) ? v.map((x) => [k, String(x)]) : [[k, String(v)]]
      )
  ).toString();
