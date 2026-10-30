/**
 * useIdentity.ts — Universal Identity & Colours Hook (Phase 2.3b)
 * Exposes driver and team metadata, unique driverIds, WCAG-compliant text colors,
 * and teammate styling (dashed stroke for driver 2).
 */
import useSWR from "swr";
import { fetcher } from "./api";

export interface DriverIdentity {
  driverId: string;
  code: string;
  number: string;
  name: string;
  givenName?: string;
  familyName?: string;
  nationality?: string;
  dob?: string;
  team: string;
  teamId: string;
  teamColor: string;
  textColor: string;
  tintColor?: string;
  headshotUrl?: string | null;
  isSecondDriver?: boolean;
  dash?: string | null;
  strokeDash?: string | null;
}

export interface TeamIdentity {
  teamId: string;
  name: string;
  teamColor: string;
  textColor: string;
  drivers: string[];
}

export interface IdentityResponse {
  status: string;
  source: string;
  year: number;
  drivers: Record<string, DriverIdentity>;
  teams: Record<string, TeamIdentity>;
}

export function useIdentity(year?: number) {
  const url = year ? `/api/identity?year=${year}` : "/api/identity";
  const { data, error, isLoading } = useSWR<IdentityResponse>(url, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60000,
  });

  const getDriver = (idOrCode: string): DriverIdentity | undefined => {
    if (!data?.drivers || !idOrCode) return undefined;
    const clean = idOrCode.toLowerCase();
    // Lookup by driverId
    if (data.drivers[clean]) return data.drivers[clean];
    // Lookup by 3-letter code
    const found = Object.values(data.drivers).find(
      (d) => d.code.toLowerCase() === clean
    );
    if (found) return found;
    // Lookup by name
    return Object.values(data.drivers).find(
      (d) => d.name.toLowerCase().includes(clean) || clean.includes(d.name.toLowerCase())
    );
  };

  const getTeam = (teamIdOrName: string): TeamIdentity | undefined => {
    if (!data?.teams || !teamIdOrName) return undefined;
    const clean = teamIdOrName.toLowerCase().replace(/[\s-]/g, "_");
    if (data.teams[clean]) return data.teams[clean];
    return Object.values(data.teams).find(
      (t) => t.name.toLowerCase().includes(clean) || clean.includes(t.name.toLowerCase())
    );
  };

  const getDriverColor = (idOrCode: string): string => {
    const d = getDriver(idOrCode);
    return d?.teamColor || "var(--accent)";
  };

  const getDriverStrokeDash = (idOrCode: string): string | undefined => {
    const d = getDriver(idOrCode);
    return d?.strokeDash || undefined;
  };

  return {
    identity: data,
    drivers: data?.drivers || {},
    teams: data?.teams || {},
    getDriver,
    getTeam,
    getDriverColor,
    getDriverStrokeDash,
    isLoading,
    error,
  };
}
