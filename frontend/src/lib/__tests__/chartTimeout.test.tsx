import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChartState } from "@/components/charts/ChartState";

describe("Chart Loading Timeout and Retry (Vitest)", () => {
  it("renders error state with Retry button when loading times out or returns source_error", () => {
    const handleRetry = vi.fn();
    const timeoutData = {
      status: "source_error",
      source: "FastF1",
      coverage_note: "Session data loading timed out after 45s. Please retry.",
    };

    render(
      <ChartState
        data={timeoutData}
        error={null}
        isLoading={false}
        retry={handleRetry}
      >
        <div>Chart Content</div>
      </ChartState>
    );

    // Chart content must not be shown
    expect(screen.queryByText("Chart Content")).toBeNull();

    // Must display error state and Retry button
    const retryBtn = screen.getByRole("button", { name: /retry/i });
    expect(retryBtn).toBeDefined();

    // Clicking retry must invoke the retry handler
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });
});

