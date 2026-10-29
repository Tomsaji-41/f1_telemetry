import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GridVsFinishChart } from "../GridVsFinishChart";

describe("GridVsFinishChart", () => {
  const sampleData = {
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
        code: "NOR",
        name: "Lando Norris",
        team: "McLaren",
        grid: 1,
        finish: 2,
        delta: -1,
        status: "Finished",
      },
      {
        code: "LEC",
        name: "Charles Leclerc",
        team: "Ferrari",
        grid: 4,
        finish: 4,
        delta: 0,
        status: "Finished",
      },
      {
        code: "HAM",
        name: "Lewis Hamilton",
        team: "Mercedes",
        grid: 7,
        finish: 18,
        delta: -11,
        badge: "DNF" as const,
        is_dnf: true,
        status: "Engine",
      },
    ],
  };

  it("renders with data and shows column headers and driver codes", () => {
    render(<GridVsFinishChart data={sampleData} loading={false} />);
    
    // Column headers
    expect(screen.getByText("Start Grid")).toBeDefined();
    expect(screen.getByText("Finish")).toBeDefined();

    // Driver codes
    expect(screen.getAllByText("VER").length).toBeGreaterThan(0);
    expect(screen.getAllByText("NOR").length).toBeGreaterThan(0);
  });

  it("mounts correctly inside the main dashboard layout container", () => {
    const { container } = render(
      <main className="space-y-8 max-w-[1400px] mx-auto">
        <section>
          <GridVsFinishChart data={sampleData} loading={false} />
        </section>
      </main>
    );

    const svg = container.querySelector('svg[aria-label="Grid versus finish comparison slope chart"]');
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("role")).toBe("img");
  });

  it("shows DNF badge for retired driver without inventing positions", () => {
    render(<GridVsFinishChart data={sampleData} loading={false} />);
    expect(screen.getByText("[DNF]")).toBeDefined();
  });
});
