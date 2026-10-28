import { create } from "zustand";

export interface TelemetryState {
  season: number;
  round: number;
  driver1: string;
  driver2: string;
  activeMetric: "speed" | "throttle" | "brake";
  cursorDistance: number | null;
  setSeason: (season: number) => void;
  setRound: (round: number) => void;
  setDriver1: (code: string) => void;
  setDriver2: (code: string) => void;
  setActiveMetric: (metric: "speed" | "throttle" | "brake") => void;
  setCursorDistance: (dist: number | null) => void;
}

export const useTelemetryStore = create<TelemetryState>((set) => ({
  season: new Date().getFullYear(),
  round: 1,
  driver1: "VER",
  driver2: "HAM",
  activeMetric: "speed",
  cursorDistance: null,
  setSeason: (season: number) => set({ season }),
  setRound: (round: number) => set({ round }),
  setDriver1: (driver1: string) => set({ driver1: driver1.toUpperCase() }),
  setDriver2: (driver2: string) => set({ driver2: driver2.toUpperCase() }),
  setActiveMetric: (activeMetric) => set({ activeMetric }),
  setCursorDistance: (cursorDistance) => set({ cursorDistance }),
}));
