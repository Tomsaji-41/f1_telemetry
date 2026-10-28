import { describe, it, expect, beforeEach } from "vitest";
import { useTelemetryStore } from "../telemetry-store";

describe("Telemetry Zustand Store", () => {
  beforeEach(() => {
    useTelemetryStore.setState({
      season: 2024,
      round: 1,
      driver1: "VER",
      driver2: "HAM",
      activeMetric: "speed",
    });
  });

  it("should initialize with default season and drivers", () => {
    const state = useTelemetryStore.getState();
    expect(state.season).toBe(2024);
    expect(state.round).toBe(1);
    expect(state.driver1).toBe("VER");
    expect(state.driver2).toBe("HAM");
  });

  it("should uppercase driver codes when updated", () => {
    const { setDriver1, setDriver2 } = useTelemetryStore.getState();
    setDriver1("nor");
    setDriver2("lec");

    const state = useTelemetryStore.getState();
    expect(state.driver1).toBe("NOR");
    expect(state.driver2).toBe("LEC");
  });

  it("should update active metric", () => {
    const { setActiveMetric } = useTelemetryStore.getState();
    setActiveMetric("throttle");

    expect(useTelemetryStore.getState().activeMetric).toBe("throttle");
  });
});
