/**
 * WCAG 2.1 Contrast & Color Utility
 * Used to ensure text on dynamic team colors or driver badges remains legible.
 */

export function parseHex(hex: string): [number, number, number] {
  let clean = hex.replace("#", "").trim();
  if (clean.length === 3) {
    clean = clean
      .split("")
      .map((c) => c + c)
      .join("");
  }
  if (clean.length !== 6) {
    return [0, 0, 0];
  }
  const num = parseInt(clean, 16);
  if (isNaN(num)) return [0, 0, 0];
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

/**
 * Calculate relative luminance according to WCAG 2.1 specs
 */
export function getRelativeLuminance(r: number, g: number, b: number): number {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

/**
 * Calculate WCAG 2.1 contrast ratio between two hex colours (1 to 21)
 */
export function getContrastRatio(hex1: string, hex2: string): number {
  const [r1, g1, b1] = parseHex(hex1);
  const [r2, g2, b2] = parseHex(hex2);
  const l1 = getRelativeLuminance(r1, g1, b1);
  const l2 = getRelativeLuminance(r2, g2, b2);
  const brightest = Math.max(l1, l2);
  const darkest = Math.min(l1, l2);
  return (brightest + 0.05) / (darkest + 0.05);
}

/**
 * Return "#000000" or "#ffffff" depending on which provides better contrast
 * against the provided background colour.
 */
export function getAccessibleTextColor(bgHex: string): "#000000" | "#ffffff" {
  if (!bgHex || typeof bgHex !== "string") return "#ffffff";
  const [r, g, b] = parseHex(bgHex);
  const bgLum = getRelativeLuminance(r, g, b);
  // Luminance of black (#000000) is 0; white (#ffffff) is 1
  const contrastWithWhite = (1 + 0.05) / (bgLum + 0.05);
  const contrastWithBlack = (bgLum + 0.05) / (0 + 0.05);
  return contrastWithBlack >= contrastWithWhite ? "#000000" : "#ffffff";
}
