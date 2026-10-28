/**
 * Minimal i18n helper — reads from en.json at build time.
 * Dot-path lookup: t("chart.preparing") → "Preparing session data…"
 */
import en from "@/content/en.json";

export function t(path: string): string {
  const parts = path.split(".");
  let cur: any = en;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return path;
    cur = cur[p];
  }
  return typeof cur === "string" ? cur : path;
}
