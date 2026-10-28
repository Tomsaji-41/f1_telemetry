import { z } from "zod";

export const RaceResultSchema = z.object({
  position: z.number().nullable(),
  driver_number: z.string(),
  code: z.string(),
  full_name: z.string(),
  team: z.string(),
  grid: z.number(),
  status: z.string(),
  points: z.number(),
});

export type RaceResult = z.infer<typeof RaceResultSchema>;

export const LapPositionSchema = z.object({
  driver: z.string(),
  lap: z.number(),
  position: z.number(),
  lap_time_sec: z.number().nullable().optional(),
});

export type LapPosition = z.infer<typeof LapPositionSchema>;

export const RaceFactsSchema = z.object({
  year: z.number(),
  round: z.number(),
  event_name: z.string(),
  location: z.string(),
  official_event_date: z.string(),
  winner: z.string(),
  total_laps: z.number(),
  results: z.array(RaceResultSchema),
  lap_positions: z.array(LapPositionSchema),
});

export type RaceFacts = z.infer<typeof RaceFactsSchema>;
