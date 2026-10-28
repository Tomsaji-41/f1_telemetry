import { API_URL } from "@/lib/env";
import { TelemetryComparison, TelemetryComparisonSchema } from "../types";

export async function getTelemetry(
  year: number,
  roundNum: number,
  driver1: string,
  driver2: string
): Promise<TelemetryComparison> {
  const d1 = driver1.trim().toUpperCase();
  const d2 = driver2.trim().toUpperCase();
  const url = `${API_URL}/api/v1/telemetry/${year}/${roundNum}/${d1}/${d2}`;
  console.log(`[getTelemetry] GET ${url}`);
  
  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    next: { revalidate: 3600, tags: [`telemetry-${year}-${roundNum}-${d1}-${d2}`] },
  });

  if (!response.ok) {
    console.error(`[getTelemetry] Error reaching ${url}: ${response.status}`);
    throw new Error(`Could not reach GET ${url}: status ${response.status}`);
  }

  const rawData = await response.json();
  return TelemetryComparisonSchema.parse(rawData);
}
