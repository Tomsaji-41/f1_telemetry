import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TyreStintGantt } from "../TyreStintGantt";
import { ChampionshipProgressionChart } from "../ChampionshipProgressionChart";
import { GapEvolutionChart } from "../GapEvolutionChart";

// Mock Identity provider
vi.mock("@/lib/useIdentity", () => ({
  useIdentity: () => ({
    getDriver: (idOrCode: string) => {
      const code = idOrCode.toUpperCase();
      if (code === "VER") {
        return {
          driverId: "max_verstappen",
          code: "VER",
          name: "Max Verstappen",
          team: "Red Bull Racing",
          teamColor: "#3671C6",
        };
      }
      if (code === "HAM") {
        return {
          driverId: "hamilton",
          code: "HAM",
          name: "Lewis Hamilton",
          team: "Ferrari",
          teamColor: "#E8002D",
        };
      }
      return undefined;
    },
    getTeam: (teamIdOrName: string) => {
      if (teamIdOrName.toLowerCase().includes("red_bull")) {
        return {
          teamId: "red_bull",
          name: "Red Bull Racing",
          teamColor: "#3671C6",
        };
      }
      return undefined;
    },
    getDriverColor: (code: string) => (code === "VER" ? "#3671C6" : "#6b7280"),
  }),
}));

// Mock Inspector drawer
vi.mock("../../layouts/inspector-drawer", () => ({
  useInspector: () => ({
    inspectItem: vi.fn(),
  }),
}));

describe("Chart Driver Identity & Fallback Audit", () => {
  let consoleErrorSpy: any;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it("TyreStintGantt derives identity for known drivers and falls back cleanly for unmapped drivers", () => {
    const data = {
      series: [
        { driver: "VER", stint: 1, compound: "MEDIUM", start_lap: 1, end_lap: 20 },
        { driver: "ROO", stint: 1, compound: "HARD", start_lap: 1, end_lap: 25 },
      ],
    };

    const { container } = render(<TyreStintGantt data={data} />);

    // Must render driver codes
    expect(screen.getByText("VER")).toBeDefined();
    expect(screen.getByText("ROO")).toBeDefined();

    // Verify SVG circles for team colours
    const circles = container.querySelectorAll("circle");
    expect(circles.length).toBeGreaterThanOrEqual(2);
    // VER should have Red Bull colour
    const verCircle = Array.from(circles).find((c) => c.getAttribute("fill") === "#3671C6");
    expect(verCircle).toBeDefined();

    // Must NOT contain "undefined" or "NaN" in any rendered text or attribute
    const html = container.innerHTML;
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("NaN");
  });

  it("ChampionshipProgressionChart applies identity colors and handles unmapped drivers", () => {
    const data = {
      series: [
        { code: "VER", name: "VER", points: 25, position: 1 },
        { code: "HAM", name: "HAM", points: 18, position: 2 },
        { code: "ROO", name: "ROO", points: 0, position: 20 },
      ],
    };

    const { container } = render(<ChampionshipProgressionChart data={data} />);

    expect(screen.getByText("VER")).toBeDefined();
    expect(screen.getByText("HAM")).toBeDefined();
    expect(screen.getByText("ROO")).toBeDefined();

    // Check colors
    expect(container.querySelector('rect[fill="#3671C6"]')).toBeDefined();
    expect(container.querySelector('rect[fill="#E8002D"]')).toBeDefined();
    expect(container.querySelector('rect[fill="#6b7280"]')).toBeDefined();

    // Toggle to Table view to verify full names from identity
    const tableBtn = screen.getByRole("button", { name: /table/i });
    expect(tableBtn).toBeDefined();
    fireEvent.click(tableBtn);

    expect(screen.getByText("Max Verstappen")).toBeDefined();
    expect(screen.getByText("Lewis Hamilton")).toBeDefined();
    expect(container.innerHTML).not.toContain("undefined");
    expect(container.innerHTML).not.toContain("NaN");
  });

  it("GapEvolutionChart renders identity colours and handles leader vs trailing unmapped drivers", () => {
    const data = {
      series: [
        { driver: "VER", position: 1, gap: "0.000s" },
        { driver: "ROO", position: 2, gap: "+15.200s" },
      ],
    };

    const { container } = render(<GapEvolutionChart data={data} />);

    expect(screen.getByText("VER")).toBeDefined();
    expect(screen.getByText("ROO")).toBeDefined();

    const html = container.innerHTML;
    expect(html).not.toContain("undefined");
    expect(html).not.toContain("NaN");
  });
});
