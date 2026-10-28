import { describe, it, expect } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
import { Button } from "../button";

describe("Button Primitive Component", () => {
  it("renders with default primary variant and text", () => {
    render(<Button>Launch Engine</Button>);
    const button = screen.getByRole("button", { name: /launch engine/i });
    expect(button).toBeDefined();
  });

  it("handles loading state correctly", () => {
    render(<Button isLoading>Telemetry Sync</Button>);
    const button = screen.getByRole("button", { name: /telemetry sync/i });
    expect(button).toBeDefined();
    expect(button.getAttribute("disabled")).not.toBeNull();
  });
});
