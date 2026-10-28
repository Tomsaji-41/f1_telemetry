import { describe, it, expect } from "vitest";
import { RaceFactsSchema, RaceResultSchema } from "../index";

describe("RaceFacts Zod Schemas", () => {
  it("should validate a correct RaceResult object", () => {
    const validResult = {
      position: 1,
      driver_number: "1",
      code: "VER",
      full_name: "Max Verstappen",
      team: "Red Bull Racing",
      grid: 1,
      status: "Finished",
      points: 25.0,
    };

    const parsed = RaceResultSchema.parse(validResult);
    expect(parsed.code).toBe("VER");
    expect(parsed.position).toBe(1);
  });

  it("should validate a full RaceFacts object", () => {
    const validFacts = {
      year: 2024,
      round: 1,
      event_name: "Bahrain Grand Prix",
      location: "Sakhir",
      official_event_date: "2024-03-02 00:00:00",
      winner: "VER",
      total_laps: 57,
      results: [
        {
          position: 1,
          driver_number: "1",
          code: "VER",
          full_name: "Max Verstappen",
          team: "Red Bull Racing",
          grid: 1,
          status: "Finished",
          points: 26.0,
        },
      ],
      lap_positions: [
        {
          driver: "VER",
          lap: 1,
          position: 1,
          lap_time_sec: 94.25,
        },
      ],
    };

    const parsed = RaceFactsSchema.parse(validFacts);
    expect(parsed.year).toBe(2024);
    expect(parsed.winner).toBe("VER");
    expect(parsed.results).toHaveLength(1);
  });

  it("should reject invalid race facts missing mandatory fields", () => {
    const invalidData = {
      year: "two-thousand-twenty-four", // wrong type
    };

    expect(() => RaceFactsSchema.parse(invalidData)).toThrow();
  });
});
