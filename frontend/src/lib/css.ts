/**
 * css.ts — Read CSS custom properties at runtime for canvas-based charts.
 */
export const cssVar = (name: string): string =>
  typeof document !== "undefined"
    ? getComputedStyle(document.documentElement)
        .getPropertyValue(name)
        .trim() || "#A9A9BC"
    : "#A9A9BC";
