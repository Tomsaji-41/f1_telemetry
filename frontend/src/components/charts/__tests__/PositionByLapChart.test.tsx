import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { PositionByLapChart, firstValidIndex, lastValidIndex } from "../PositionByLapChart";

// Mock Identity provider
vi.mock("@/lib/useIdentity", () => ({
  useIdentity: () => ({
    getDriver: (code: string) => ({
      code,
      teamColor: code === "RET" ? "#ef4444" : code === "FIN" ? "#10b981" : "#6b7280",
      strokeDash: undefined,
    }),
    getDriverColor: () => "#3b82f6",
  }),
}));

// Mock Inspector drawer
vi.mock("../layouts/inspector-drawer", () => ({
  useInspector: () => ({
    inspectItem: vi.fn(),
  }),
}));

describe("PositionByLapChart", () => {
  let consoleErrorSpy: any;
  let consoleWarnSpy: any;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    consoleWarnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    consoleWarnSpy.mockRestore();
  });

  it("calculates firstValidIndex and lastValidIndex correctly", () => {
    expect(firstValidIndex([null, undefined, 3, 4, null])).toBe(2);
    expect(lastValidIndex([null, undefined, 3, 4, null])).toBe(3);
    expect(firstValidIndex([3, 3, 4, null, null])).toBe(0);
    expect(lastValidIndex([3, 3, 4, null, null])).toBe(2);
    expect(firstValidIndex([null, null, null])).toBe(-1);
    expect(lastValidIndex([null, null, null])).toBe(-1);
    expect(firstValidIndex([])).toBe(-1);
    expect(lastValidIndex([])).toBe(-1);
  });

  it("handles retired driver [3, 3, 4, null, null] and all-null driver without NaN in SVG and without console errors", () => {
    const mockData = {
      status: "ok",
      series: [
        {
          driver: "RET",
          x: [1, 2, 3, 4, 5],
          y: [3, 3, 4, null, null],
        },
        {
          driver: "NUL",
          x: [1, 2, 3, 4, 5],
          y: [null, null, null, null, null],
        },
        {
          driver: "FIN",
          x: [1, 2, 3, 4, 5],
          y: [1, 1, 1, 1, 1],
        },
      ],
      driver_meta: [
        { code: "RET", name: "Retired Driver", team: "Ferrari", colour: "#ef4444" },
        { code: "NUL", name: "Null Driver", team: "Haas", colour: "#6b7280" },
        { code: "FIN", name: "Finishing Driver", team: "Red Bull", colour: "#10b981" },
      ],
    };

    const { container } = render(<PositionByLapChart data={mockData} />);

    // 1. Verify no console.error or console.warn occurred
    expect(consoleErrorSpy).not.toHaveBeenCalled();
    expect(consoleWarnSpy).not.toHaveBeenCalled();

    // 2. Assert no NaN attribute anywhere in the rendered SVG
    const html = container.innerHTML;
    expect(html).not.toContain("NaN");
    expect(html).not.toContain('="NaN"');
    expect(html).not.toContain("undefined");

    // 3. Verify driver RET has labels rendered (start at lap 1, end at lap 3)
    const retLabels = screen.getAllByText("RET");
    expect(retLabels.length).toBeGreaterThanOrEqual(1);

    // 4. Verify driver NUL has NO chart labels rendered in SVG (skipped due to all-null)
    const svgTexts = Array.from(container.querySelectorAll("svg text")).map((t) => t.textContent);
    expect(svgTexts).not.toContain("NUL");

    // 5. Verify driver FIN has labels
    const finLabels = screen.getAllByText("FIN");
    expect(finLabels.length).toBeGreaterThanOrEqual(1);
  });
});
