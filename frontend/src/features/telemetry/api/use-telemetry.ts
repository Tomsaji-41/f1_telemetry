import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { getTelemetry } from "./get-telemetry";
import { TelemetryComparison } from "../types";

export function useTelemetry(
  year: number,
  roundNum: number,
  driver1: string,
  driver2: string
): UseQueryResult<TelemetryComparison, Error> {
  return useQuery({
    queryKey: ["telemetry", year, roundNum, driver1, driver2],
    queryFn: () => getTelemetry(year, roundNum, driver1, driver2),
    enabled: Boolean(year && roundNum && driver1 && driver2 && driver1 !== driver2),
    staleTime: 1000 * 60 * 15,
  });
}
