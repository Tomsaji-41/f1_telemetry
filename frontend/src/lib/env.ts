// In browser, use empty string so all fetches are relative paths (/api/...) proxied via Next.js rewrite
export const NEXT_PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL || "";

// Single API base URL exported everywhere
export const API_URL = NEXT_PUBLIC_API_URL;
export const API_BASE_URL = NEXT_PUBLIC_API_URL;

export const env = {
  NEXT_PUBLIC_API_URL,
  API_URL,
  API_BASE_URL,
  NEXT_PUBLIC_BACKEND_URL: NEXT_PUBLIC_API_URL,
  NEXT_PUBLIC_API_BASE_URL: `${NEXT_PUBLIC_API_URL}/api/v1`,
};
