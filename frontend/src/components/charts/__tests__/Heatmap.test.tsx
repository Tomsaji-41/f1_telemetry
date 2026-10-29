import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Heatmap } from "../Heatmap";
import { ChartErrorBoundary } from "../ChartErrorBoundary";

// Mock Identity provider
vi.mock("@/lib/useIdentity", () => ({
  useIdentity: () => ({
    getDriver: (code: string) => ({
      code,
      name: code === "VER" ? "Max Verstappen" : "Lewis Hamilton",
      teamColor: code === "VER" ? "#0600ef" : "#00d2be",
    }),
    getDriverColor: () => "#0600ef",
  }),
}));

describe("Heatmap Component", () => {
  let consoleErrorSpy: any;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it("renders valid sector rows correctly", () => {
    const validData = {
      rows: [
        {
          code: "VER",
          s1_best_ms: 28100,
          s1_mean_ms: 28500,
          s1_gap_ms: 0,
          s1_session_best: true,
          s2_best_ms: 36200,
          s2_mean_ms: 36400,
          s2_gap_ms: 0,
          s2_session_best: true,
          s3_best_ms: 27500,
          s3_mean_ms: 27800,
          s3_gap_ms: 100,
          s3_session_best: false,
          ideal_ms: 91800,
        },
        {
          code: "HAM",
          s1_best_ms: 28300,
          s1_mean_ms: 28700,
          s1_gap_ms: 200,
          s1_session_best: false,
          s2_best_ms: 36400,
          s2_mean_ms: 36600,
          s2_gap_ms: 200,
          s2_session_best: false,
          s3_best_ms: 27400,
          s3_mean_ms: 27600,
          s3_gap_ms: 0,
          s3_session_best: true,
          ideal_ms: 92100,
        },
      ],
    };

    render(<Heatmap d={validData} />);
    expect(screen.getByText("VER")).toBeDefined();
    expect(screen.getByText("HAM")).toBeDefined();
    expect(screen.getByText("S1")).toBeDefined();
    expect(screen.getByText("S2")).toBeDefined();
    expect(screen.getByText("S3")).toBeDefined();
    expect(screen.getByText("Ideal")).toBeDefined();
  });

  it("handles empty and undefined data gracefully without crashing", () => {
    const { container: c1 } = render(<Heatmap d={undefined as any} />);
    expect(screen.getByText(/No sector times recorded for this session/i)).toBeDefined();

    const { container: c2 } = render(<Heatmap d={{ rows: [] }} />);
    expect(screen.getAllByText(/No sector times recorded for this session/i).length).toBeGreaterThan(0);
  });

  it("handles not_available status with custom coverage_note", () => {
    render(
      <Heatmap
        d={{
          status: "not_available",
          coverage_note: "Sector timing was unavailable for this vintage session.",
        } as any}
      />
    );
    expect(
      screen.getByText("Sector timing was unavailable for this vintage session.")
    ).toBeDefined();
  });

  it("handles malformed payload without throwing", () => {
    // rows as string, or row with null / non-finite values
    const malformed = {
      rows: "not-an-array" as any,
    };
    render(<Heatmap d={malformed} />);
    expect(screen.getByText(/No sector times recorded for this session/i)).toBeDefined();
  });
});

describe("ChartErrorBoundary", () => {
  let consoleErrorSpy: any;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  function BuggyChart(): React.JSX.Element {
    throw new Error("Simulated D3 dimension crash");
  }

  it("catches child error and renders friendly fallback with Retry button", () => {
    const onReset = vi.fn();
    render(
      <ChartErrorBoundary chartName="Pace Delta" onReset={onReset}>
        <BuggyChart />
      </ChartErrorBoundary>
    );

    expect(screen.getByText("Pace Delta unavailable")).toBeDefined();
    expect(screen.getByText("Simulated D3 dimension crash")).toBeDefined();
    const retryBtn = screen.getByRole("button", { name: /retry/i });
    expect(retryBtn).toBeDefined();
    fireEvent.click(retryBtn);
    expect(onReset).toHaveBeenCalled();
  });
});

