import { describe, it, expect } from "vitest";
import { parseHex, getRelativeLuminance, getContrastRatio, getAccessibleTextColor } from "../colors";

describe("colors utility", () => {
  it("parses hex colours correctly", () => {
    expect(parseHex("#ffffff")).toEqual([255, 255, 255]);
    expect(parseHex("#000000")).toEqual([0, 0, 0]);
    expect(parseHex("#fff")).toEqual([255, 255, 255]);
    expect(parseHex("invalid")).toEqual([0, 0, 0]);
  });

  it("calculates contrast ratios and luminances", () => {
    const whiteLum = getRelativeLuminance(255, 255, 255);
    const blackLum = getRelativeLuminance(0, 0, 0);
    expect(whiteLum).toBeCloseTo(1.0, 2);
    expect(blackLum).toBeCloseTo(0.0, 2);

    const contrast = getContrastRatio("#ffffff", "#000000");
    expect(contrast).toBeCloseTo(21, 1);
  });

  it("chooses accessible text colors", () => {
    // White background -> black text
    expect(getAccessibleTextColor("#ffffff")).toBe("#000000");
    // Black background -> white text
    expect(getAccessibleTextColor("#000000")).toBe("#ffffff");
    // Deep Ferrari red (#e10600) -> white text
    expect(getAccessibleTextColor("#e10600")).toBe("#ffffff");
    // Bright yellow (#fff500) -> black text
    expect(getAccessibleTextColor("#fff500")).toBe("#000000");
  });
});
