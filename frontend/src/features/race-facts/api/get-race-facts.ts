import { API_URL } from "@/lib/env";
import { RaceFacts, RaceFactsSchema } from "../types";

export async function getRaceFacts(year: number, roundNum: number): Promise<RaceFacts> {
  const url = `${API_URL}/api/v1/race/${year}/${roundNum}`;
  console.log(`[getRaceFacts] GET ${url}`);
  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    next: { revalidate: 3600, tags: [`race-${year}-${roundNum}`] },
  });

  if (!response.ok) {
    console.error(`[getRaceFacts] Error reaching ${url}: ${response.status}`);
    throw new Error(`Could not reach GET ${url}: status ${response.status}`);
  }

  const rawData = await response.json();
  return RaceFactsSchema.parse(rawData);
}
