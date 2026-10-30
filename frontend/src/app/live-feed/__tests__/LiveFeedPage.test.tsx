import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import LiveFeedPage from "../page";

const mockFetcher = vi.fn();

vi.mock("@/lib/api", () => ({
  fetcher: (url: string) => mockFetcher(url),
}));

let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
}));

describe("LiveFeedPage Replay & Partial Sessions", () => {
  beforeEach(() => {
    mockFetcher.mockReset();
    mockSearchParams = new URLSearchParams();
  });

  it("displays partial data banner and GREEN FLAG for partial race session (5 of 56 laps)", async () => {
    mockSearchParams = new URLSearchParams({ year: "2026", round: "1" });

    mockFetcher.mockImplementation((url: string) => {
      if (url === "/api/live/status") {
        return Promise.resolve({ status: "ok", is_live: false, mode: "replay" });
      }
      if (url.includes("/api/replay/bundle")) {
        return Promise.resolve({
          status: "partial",
          source: "FastF1 & Jolpica",
          coverage_note: "Partial data: 5 of 56 laps",
          is_partial: true,
          loaded_laps: 5,
          total_laps: 56,
          year: 2026,
          round: 1,
          grand_prix: "United States Grand Prix",
          circuit_name: "Circuit of the Americas",
          drivers: {},
          pit_events: [],
          laps: {
            "1": {
              lap: 1,
              track_status: "GREEN",
              weather: { weather_note: "Weather not recorded for this session" },
              leaderboard: [
                {
                  pos: 1,
                  driver: "Max Verstappen",
                  code: "VER",
                  team: "Red Bull",
                  team_color: "#3671C6",
                },
              ],
            },
          },
          chart_data: { laps: [1], positions: {}, lap_times: {} },
        });
      }
      return Promise.reject(new Error("Unknown url"));
    });

    render(<LiveFeedPage />);

    // Wait for bundle to load and verify partial session banner
    await waitFor(() => {
      expect(screen.getByText("⚠ PARTIAL DATA:")).toBeDefined();
    });

    expect(screen.getByText(/Partial data: 5 of 56 laps/i)).toBeDefined();

    // Verify track status is GREEN FLAG and NOT CHEQUERED FLAG
    expect(screen.getByText("GREEN FLAG")).toBeDefined();
    expect(screen.queryByText("CHEQUERED FLAG")).toBeNull();

    // Verify weather shows unrecorded message
    expect(screen.getAllByText("Weather not recorded for this session").length).toBeGreaterThan(0);
  });

  it("passes session params in fetch request when changing round", async () => {
    mockSearchParams = new URLSearchParams({ year: "2024", round: "12" });

    mockFetcher.mockImplementation((url: string) => {
      if (url === "/api/live/status") {
        return Promise.resolve({ status: "ok", is_live: false, mode: "replay" });
      }
      if (url.includes("/api/replay/bundle")) {
        expect(url).toContain("year=2024");
        expect(url).toContain("round=12");
        return Promise.resolve({
          status: "ok",
          total_laps: 52,
          year: 2024,
          round: 12,
          grand_prix: "British Grand Prix",
          circuit_name: "Silverstone",
          drivers: {},
          pit_events: [],
          laps: {
            "1": {
              lap: 1,
              track_status: "GREEN",
              weather: null,
              leaderboard: [],
            },
          },
          chart_data: { laps: [1], positions: {}, lap_times: {} },
        });
      }
      return Promise.reject(new Error("Unknown url"));
    });

    render(<LiveFeedPage />);

    await waitFor(() => {
      expect(screen.getByText("British Grand Prix 2024")).toBeDefined();
    });
  });
});
