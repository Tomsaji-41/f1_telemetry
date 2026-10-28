import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { getRaceFacts } from "./get-race-facts";
import { RaceFacts } from "../types";

export function useRaceFacts(year: number, roundNum: number): UseQueryResult<RaceFacts, Error> {
  return useQuery({
    queryKey: ["race-facts", year, roundNum],
    queryFn: () => getRaceFacts(year, roundNum),
    enabled: year >= 2018 && roundNum >= 1,
  });
}
