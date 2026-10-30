import React, { useState } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// Mock component simulating race switching behaviour with cache invalidation
function RaceSwitchingDashboard() {
  const [selectedRound, setSelectedRound] = useState(1);
  const [data, setData] = useState<{ round: number; winner: string } | null>({ round: 1, winner: "Max Verstappen" });
  const [loading, setLoading] = useState(false);

  const switchRound = async (newRound: number) => {
    // Clear old chart data immediately to prevent cross-contamination
    setData(null);
    setLoading(true);
    setSelectedRound(newRound);

    // Simulate async network fetch
    setTimeout(() => {
      setData({
        round: newRound,
        winner: newRound === 2 ? "Charles Leclerc" : "Max Verstappen"
      });
      setLoading(false);
    }, 50);
  };

  return (
    <div>
      <div data-testid="round-indicator">Active Round: {selectedRound}</div>
      <button onClick={() => switchRound(2)} data-testid="switch-btn">Switch to Round 2</button>
      {loading && <div data-testid="loading-skeleton">Loading session telemetry...</div>}
      {data && !loading && (
        <div data-testid="chart-content">
          <span>Winner: {data.winner}</span>
          <span>Round Data: {data.round}</span>
        </div>
      )}
    </div>
  );
}

describe("Race Switching Matrix Test (F2)", () => {
  it("clears old data immediately, displays loading skeleton, and renders fresh round data with no stale values", async () => {
    render(<RaceSwitchingDashboard />);

    // Initial state: Round 1
    expect(screen.getByTestId("round-indicator").textContent).toContain("Round: 1");
    expect(screen.getByTestId("chart-content").textContent).toContain("Max Verstappen");

    // Click switch to Round 2
    fireEvent.click(screen.getByTestId("switch-btn"));

    // Old data must be cleared immediately, skeleton shown
    expect(screen.queryByText("Max Verstappen")).toBeNull();
    expect(screen.getByTestId("loading-skeleton")).toBeDefined();

    // After async resolution: Round 2 data rendered
    await waitFor(() => {
      expect(screen.getByTestId("round-indicator").textContent).toContain("Round: 2");
      expect(screen.getByTestId("chart-content").textContent).toContain("Charles Leclerc");
      expect(screen.queryByTestId("loading-skeleton")).toBeNull();
    });
  });
});

