import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Track3D from "../Track3D";

describe("Track3D & 2D Circuit Figure Visualization", () => {
  it("renders 2D fallback when WebGL or 3D is unavailable", () => {
    const geometry = {
      status: "ok",
      circuit_id: "silverstone",
      circuit_name: "Silverstone Circuit",
      total_length_meters: 5891.0,
      x: [0, 100, 200, 300, 400, 300, 200, 100, 0, 10],
      y: [0, 50, 100, 150, 200, 250, 200, 100, 0, 10],
      corners: [{ number: 1, angle: 90, distance: 400 }],
    };

    const { container } = render(<Track3D geometry={geometry} />);
    expect(screen.getByText("Switch to 3D Perspective")).toBeDefined();
    expect(screen.getByText("Reset Camera")).toBeDefined();
    expect(container.querySelector("svg") || container.querySelector("canvas")).toBeDefined();
  });

  it("renders informative not_available state when geometry status is not_available", () => {
    const geometry = {
      status: "not_available",
      circuit_id: "pescara",
      circuit_name: "Pescara Circuit",
      reason: "No telemetry position data or OSM track geometry available for circuit 'pescara'",
    };

    render(<Track3D geometry={geometry} />);
    expect(screen.getByText("Track Layout Information")).toBeDefined();
    expect(
      screen.getByText("No telemetry position data or OSM track geometry available for circuit 'pescara'")
    ).toBeDefined();
  });
});
