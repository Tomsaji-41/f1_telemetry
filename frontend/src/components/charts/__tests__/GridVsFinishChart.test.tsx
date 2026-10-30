import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { GridVsFinishChart } from "../GridVsFinishChart";

const mockIdentityMap: Record<string, any> = {
  VER: {
    driverId: "max_verstappen",
    code: "VER",
    name: "Max Verstappen",
    team: "Red Bull Racing",
    teamColor: "#3671C6",
    tintColor: "#3671C6",
    isSecondDriver: false,
    strokeDash: null,
  },
  PER: {
    driverId: "perez",
    code: "PER",
    name: "Sergio Perez",
    team: "Red Bull Racing",
    teamColor: "#3671C6",
    tintColor: "#87ADE5",
    isSecondDriver: true,
    strokeDash: "4 2",
  },
  NOR: {
    driverId: "norris",
    code: "NOR",
    name: "Lando Norris",
    team: "McLaren",
    teamColor: "#FF8000",
    tintColor: "#FF8000",
    isSecondDriver: false,
    strokeDash: null,
  },
  PIA: {
    driverId: "piastri",
    code: "PIA",
    name: "Oscar Piastri",
    team: "McLaren",
    teamColor: "#FF8000",
    tintColor: "#FFAC59",
    isSecondDriver: true,
    strokeDash: "4 2",
  },
  RUS: {
    driverId: "russell",
    code: "RUS",
    name: "George Russell",
    team: "Mercedes",
    teamColor: "#27F4D2",
    tintColor: "#27F4D2",
    isSecondDriver: false,
    strokeDash: null,
  },
  ANT: {
    driverId: "antonelli",
    code: "ANT",
    name: "Andrea Kimi Antonelli",
    team: "Mercedes",
    teamColor: "#27F4D2",
    tintColor: "#7FF8E4",
    isSecondDriver: true,
    strokeDash: "4 2",
  },
};

vi.mock("@/lib/useIdentity", () => ({
  useIdentity: () => ({
    getDriver: (codeOrId: string) => mockIdentityMap[codeOrId?.toUpperCase()] || undefined,
    getDriverColor: (codeOrId: string) => mockIdentityMap[codeOrId?.toUpperCase()]?.teamColor || "#A9A9BC",
    getTeam: () => undefined,
  }),
}));

describe("GridVsFinishChart", () => {
  // 6-driver fixture across teams with 1 DNF
  const fixture6Drivers = {
    status: "ok",
    source: "Jolpica",
    rows: [
      {
        code: "VER",
        name: "Max Verstappen",
        team: "Red Bull Racing",
        grid: 3,
        finish: 1,
        delta: 2,
        status: "Finished",
      },
      {
        code: "PER",
        name: "Sergio Perez",
        team: "Red Bull Racing",
        grid: 6,
        finish: 4,
        delta: 2,
        status: "Finished",
      },
      {
        code: "NOR",
        name: "Lando Norris",
        team: "McLaren",
        grid: 1,
        finish: 2,
        delta: -1,
        status: "Finished",
      },
      {
        code: "PIA",
        name: "Oscar Piastri",
        team: "McLaren",
        grid: 2,
        finish: 3,
        delta: -1,
        status: "Finished",
      },
      {
        code: "RUS",
        name: "George Russell",
        team: "Mercedes",
        grid: 4,
        finish: 5,
        delta: -1,
        status: "Finished",
      },
      {
        code: "ANT",
        name: "Andrea Kimi Antonelli",
        team: "Mercedes",
        grid: 5,
        finish: 18,
        delta: -13,
        badge: "DNF" as const,
        is_dnf: true,
        status: "Hydraulics",
      },
    ],
  };

  it("renders with data and shows column headers and driver codes", () => {
    render(<GridVsFinishChart data={fixture6Drivers} loading={false} />);

    // Column headers
    expect(screen.getByText("Grid")).toBeDefined();
    expect(screen.getByText("Drv")).toBeDefined();
    expect(screen.getByText("Start")).toBeDefined();
    expect(screen.getByText("Finish")).toBeDefined();
    expect(screen.getByText("Result & Delta")).toBeDefined();

    // Driver codes
    expect(screen.getAllByText("VER").length).toBeGreaterThan(0);
    expect(screen.getAllByText("NOR").length).toBeGreaterThan(0);
  });

  it("mounts correctly with data-testid and aria-label", () => {
    const { container } = render(
      <main className="space-y-8 max-w-[1400px] mx-auto">
        <section>
          <GridVsFinishChart data={fixture6Drivers} loading={false} />
        </section>
      </main>
    );

    const svg = container.querySelector('svg[data-testid="grid-vs-finish-chart"]');
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("role")).toBe("img");
  });

  it("ensures every slope line has a team colour other than neutral fallback", () => {
    const { container } = render(<GridVsFinishChart data={fixture6Drivers} loading={false} />);
    const slopeLines = container.querySelectorAll("g.group line");
    expect(slopeLines.length).toBe(6);

    slopeLines.forEach((line) => {
      const stroke = line.getAttribute("stroke");
      expect(stroke).toBeTruthy();
      expect(stroke).not.toBe("#A9A9BC");
      expect(stroke).not.toBe("var(--text-3)");
    });
  });

  it("ensures no two label text elements share identical (x, y) coordinates", () => {
    const { container } = render(<GridVsFinishChart data={fixture6Drivers} loading={false} />);
    const textNodes = Array.from(container.querySelectorAll("svg text"));
    const coords = new Set<string>();

    textNodes.forEach((node) => {
      const x = node.getAttribute("x");
      const y = node.getAttribute("y");
      if (x && y) {
        const key = `${x},${y}`;
        expect(coords.has(key)).toBe(false);
        coords.add(key);
      }
    });
  });

  it("distinguishes teammates by dash pattern AND lighter tint", () => {
    const { container } = render(<GridVsFinishChart data={fixture6Drivers} loading={false} />);
    const slopeGroups = Array.from(container.querySelectorAll("g.group"));

    // Red Bull: VER (driver 1) vs PER (driver 2)
    const verLine = slopeGroups[0].querySelector("line");
    const perLine = slopeGroups[1].querySelector("line");

    expect(verLine?.getAttribute("stroke-dasharray")).toBeNull();
    expect(perLine?.getAttribute("stroke-dasharray")).toBe("4 2");

    const verStroke = verLine?.getAttribute("stroke");
    const perStroke = perLine?.getAttribute("stroke");
    expect(verStroke).not.toBe(perStroke);

    // McLaren: NOR (driver 1) vs PIA (driver 2)
    const norLine = slopeGroups[2].querySelector("line");
    const piaLine = slopeGroups[3].querySelector("line");

    expect(norLine?.getAttribute("stroke-dasharray")).toBeNull();
    expect(piaLine?.getAttribute("stroke-dasharray")).toBe("4 2");

    const norStroke = norLine?.getAttribute("stroke");
    const piaStroke = piaLine?.getAttribute("stroke");
    expect(norStroke).not.toBe(piaStroke);
  });

  it("renders deltas with directional arrows and DNF badge", () => {
    render(<GridVsFinishChart data={fixture6Drivers} loading={false} />);
    expect(screen.getAllByText("▲ +2").length).toBe(2);
    expect(screen.getAllByText("▼ -1").length).toBe(3);
    expect(screen.getByText("[DNF]")).toBeDefined();
  });
});
