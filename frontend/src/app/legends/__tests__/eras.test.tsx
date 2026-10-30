import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import LegendsPage from "../page";
import * as api from "@/lib/api";

// Mock fetcher
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetcher: vi.fn(),
  };
});

describe("Legends and Eras page resilience (Phase 4)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders eras and champions successfully when API succeeds", async () => {
    const mockFetcher = vi.mocked(api.fetcher);
    mockFetcher.mockImplementation((url: string) => {
      if (url === "/api/legends") {
        return Promise.resolve({
          status: "ok",
          legends: [
            {
              name: "Juan Manuel Fangio",
              driver_id: "fangio",
              titles: 5,
              years: [1951, 1954, 1955, 1956, 1957],
              teams: ["Alfa Romeo", "Maserati", "Mercedes", "Ferrari"],
              nationality: "Argentine",
            },
          ],
        });
      }
      if (url === "/api/eras") {
        return Promise.resolve({
          status: "ok",
          eras: [
            {
              id: "early_championship",
              name: "The Foundation & Front-Engine Era",
              from: 1950,
              to: 1960,
              text: "The formative years of the World Championship.",
              champions_count: 11,
              dominant_drivers: [{ driver: "Juan Manuel Fangio", titles_in_era: 5 }],
            },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(<LegendsPage />);

    // Wait for content to appear
    await waitFor(() => {
      expect(screen.getByText("Formula 1 Legends")).toBeDefined();
      expect(screen.getByText("The Foundation & Front-Engine Era")).toBeDefined();
      expect(screen.getByText("Juan Manuel Fangio")).toBeDefined();
    });
  });

  it("renders ErrorState with Retry button when /api/eras returns an error status", async () => {
    const mockFetcher = vi.mocked(api.fetcher);
    mockFetcher.mockImplementation((url: string) => {
      if (url === "/api/legends") {
        return Promise.resolve({ status: "ok", legends: [] });
      }
      if (url === "/api/eras") {
        return Promise.resolve({
          status: "error",
          reason: "Jolpica upstream rate limit (HTTP 429)",
          eras: [],
        });
      }
      return Promise.resolve({});
    });

    render(<LegendsPage />);

    await waitFor(() => {
      expect(screen.getByText("Failed to load F1 Legends & Technical Eras")).toBeDefined();
      expect(screen.getByText("Jolpica upstream rate limit (HTTP 429)")).toBeDefined();
      expect(screen.getByRole("button", { name: /retry/i })).toBeDefined();
    });
  });

  it("renders ErrorState when network rejects and retries on click", async () => {
    const mockFetcher = vi.mocked(api.fetcher);
    let attempts = 0;

    mockFetcher.mockImplementation((url: string) => {
      attempts++;
      if (attempts <= 2) {
        return Promise.reject(new Error("Network connection lost"));
      }
      if (url === "/api/legends") {
        return Promise.resolve({
          status: "ok",
          legends: [
            {
              name: "Michael Schumacher",
              driver_id: "michael_schumacher",
              titles: 7,
              years: [1994, 1995, 2000, 2001, 2002, 2003, 2004],
              teams: ["Benetton", "Ferrari"],
              nationality: "German",
            },
          ],
        });
      }
      return Promise.resolve({
        status: "ok",
        eras: [
          {
            id: "v10_era",
            name: "The 3.0L V10 Era",
            from: 1995,
            to: 2005,
            text: "High-revving naturally aspirated V10 power.",
            champions_count: 11,
          },
        ],
      });
    });

    render(<LegendsPage />);

    // Initially fails with error state
    await waitFor(() => {
      expect(screen.getByText("Failed to load F1 Legends & Technical Eras")).toBeDefined();
      expect(screen.getByText("Network connection lost")).toBeDefined();
    });

    const retryBtn = screen.getByRole("button", { name: /retry/i });
    fireEvent.click(retryBtn);

    // After retry, successful data should be displayed
    await waitFor(() => {
      expect(screen.getByText("The 3.0L V10 Era")).toBeDefined();
      expect(screen.getByText("Michael Schumacher")).toBeDefined();
    });
  });
});

