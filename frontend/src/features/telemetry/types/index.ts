import { z } from "zod";

export const DriverTelemetrySchema = z.object({
  code: z.string(),
  distance: z.array(z.number()),
  speed: z.array(z.number()),
  throttle: z.array(z.number()),
  brake: z.array(z.number()),
});

export type DriverTelemetry = z.infer<typeof DriverTelemetrySchema>;

export const TelemetryComparisonSchema = z.object({
  driver1: DriverTelemetrySchema,
  driver2: DriverTelemetrySchema,
});

export type TelemetryComparison = z.infer<typeof TelemetryComparisonSchema>;

export interface TelemetryPoint {
  distance: number;
  d1_speed: number;
  d2_speed: number;
  d1_throttle: number;
  d2_throttle: number;
  d1_brake: number;
  d2_brake: number;
}
