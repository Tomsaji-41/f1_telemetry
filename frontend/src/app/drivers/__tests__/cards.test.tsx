import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import DriversPage from "../page";
import TeamsHubPage from "../../teams/page";

// Mock fetcher
vi.mock("@/lib/api", () => ({
  fetcher: vi.fn((url: string) => {
    if (url === "/api/drivers") {
      return Promise.resolve({
        status: "ok",
        drivers: [
          {
            id: "verstappen",
            name: "Max Verstappen",
            code: "VER",
            number: "1",
            team: "Red Bull Racing",
            team_color: "#3671C6",
            nationality: "Dutch",
            position: 1,
            points: 362,
            wins: 8,
          },
        ],
      });
    }
    if (url === "/api/teams") {
      return Promise.resolve({
        status: "ok",
        teams: [
          {
            id: "red_bull",
            name: "Red Bull Racing",
            color: "#3671C6",
            position: 1,
            points: 544,
            wins: 8,
            drivers: ["Max Verstappen", "Sergio Perez"],
          },
        ],
      });
    }
    return Promise.resolve({});
  }),
}));

describe("Static Driver and Team Cards (Phase 4)", () => {
  it("renders driver cards with zero anchor tags inside", async () => {
    const { container } = render(<DriversPage />);
    const card = await screen.findByTestId("driver-card");
    expect(card).toBeDefined();

    // Assert ZERO anchors inside card
    const anchors = card.querySelectorAll("a");
    expect(anchors.length).toBe(0);

    // Assert card is not clickable (no role=button, no cursor-pointer)
    expect(card.getAttribute("role")).toBeNull();
    expect(card.className).not.toContain("cursor-pointer");
  });

  it("renders team cards with zero anchor tags inside", async () => {
    const { container } = render(<TeamsHubPage />);
    const card = await screen.findByTestId("team-card");
    expect(card).toBeDefined();

    // Assert ZERO anchors inside card
    const anchors = card.querySelectorAll("a");
    expect(anchors.length).toBe(0);

    // Assert card is not clickable
    expect(card.getAttribute("role")).toBeNull();
    expect(card.className).not.toContain("cursor-pointer");
  });
});
