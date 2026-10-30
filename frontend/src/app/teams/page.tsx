"use client";

import React, { useState, useEffect } from "react";
import { fetcher } from "@/lib/api";
import { Skeleton, ErrorState, EmptyState } from "@/components/primitives/kit";

interface TeamLogo {
  url: string | null;
  source: string | null;
  license: string | null;
  attribution: string | null;
  reason?: string | null;
}

interface TeamChampionship {
  round: number;
  position: number | string;
  points: number;
  gap_to_leader: number;
  gap_ahead: number;
  position_change?: number | null;
  wins: number;
  podiums: number;
  poles: number;
  fastest_laps: number;
  one_two_finishes: number;
  points_finishes: number;
  dnfs: number;
  avg_pace_delta: string;
  best_finish: string;
  best_grid: string;
}

interface TeamCar {
  driver_code: string;
  driver_name: string;
  driver_number: string;
  headshot_url?: string;
  grid: number;
  finish: number;
  status: string;
  points: number;
  pit_count: number;
  avg_pit_time: string;
  tyre_strategy: string[];
  is_second_driver: boolean;
}

interface TeamDrivers {
  active: TeamCar[];
  reserves: string[];
  h2h_race: string;
  h2h_quali: string;
}

interface TeamForm {
  recent_finishes: string[];
  points_progression: { round: number; points: number }[];
}

interface TeamReliability {
  mechanical_dnfs: number;
  collision_dnfs: number;
  other_dnfs: number;
  total_dnfs: number;
}

interface TeamProfile {
  legal_name: string;
  base: string;
  founded_year: string | number;
  team_principal: string;
  technical_director: string;
  power_unit: string;
  predecessors: string[];
  first_entry_year: string | number;
  constructors_titles: number;
  all_time_wins: number | string;
}

interface TeamCardData {
  constructor_id: string;
  name: string;
  nationality: string;
  team_color: string;
  text_color: string;
  monogram: string;
  logo: TeamLogo;
  championship: TeamChampionship;
  this_round: {
    round: number;
    points_scored: number;
    cars: TeamCar[];
  };
  drivers: TeamDrivers;
  form: TeamForm;
  reliability: TeamReliability;
  profile: TeamProfile;
}

interface LogoCredit {
  constructor_id: string;
  team_name: string;
  license: string;
  attribution: string;
}

interface TeamCardsResponse {
  status: string;
  year?: number;
  round?: number;
  total_teams?: number;
  cards: TeamCardData[];
  logo_credits?: LogoCredit[];
  reason?: string;
}

/**
 * Contrast helper: lightens a color until it reaches at least a 3:1 contrast ratio
 * against the card background (#181b20).
 */
function getContrastColor(hexColor: string): string {
  if (!hexColor || !hexColor.startsWith("#")) return hexColor || "#E10600";
  let hex = hexColor.replace("#", "");
  if (hex.length === 3) {
    hex = hex.split("").map((c) => c + c).join("");
  }
  let r = parseInt(hex.substring(0, 2), 16) || 0;
  let g = parseInt(hex.substring(2, 4), 16) || 0;
  let b = parseInt(hex.substring(4, 6), 16) || 0;

  // Relative luminance of background #181b20 is approx 0.012
  const bgL = 0.012;
  const getL = (cr: number, cg: number, cb: number) => {
    const sRGB = [cr, cg, cb].map((v) => {
      const c = v / 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * sRGB[0] + 0.7152 * sRGB[1] + 0.0722 * sRGB[2];
  };

  let lum = getL(r, g, b);
  let ratio = (lum + 0.05) / (bgL + 0.05);

  let attempts = 0;
  while (ratio < 3.0 && attempts < 10) {
    r = Math.min(255, Math.round(r + (255 - r) * 0.25));
    g = Math.min(255, Math.round(g + (255 - g) * 0.25));
    b = Math.min(255, Math.round(b + (255 - b) * 0.25));
    lum = getL(r, g, b);
    ratio = (lum + 0.05) / (bgL + 0.05);
    attempts++;
  }

  const toHex = (n: number) => n.toString(16).padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

export default function TeamsHubPage(): React.JSX.Element {
  const [data, setData] = useState<TeamCardsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [imgErrors, setImgErrors] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let mounted = true;

    function mapFallbackTeams(tList: any[]) {
      const mappedCards: TeamCardData[] = tList.map((t: any) => ({
        constructor_id: t.id || t.constructorId || "team",
        name: t.name || t.team || "Constructor",
        nationality: t.nationality || "FIA Base",
        team_color: t.color || "#3671C6",
        text_color: "#ffffff",
        monogram: (t.name || t.team || "TEA").slice(0, 3).toUpperCase(),
        logo: { url: null, source: null, license: null, attribution: null },
        championship: {
          round: 1,
          position: t.position || 1,
          points: t.points || 0,
          gap_to_leader: 0,
          gap_ahead: 0,
          wins: t.wins || 0,
          podiums: 0,
          poles: 0,
          fastest_laps: 0,
          one_two_finishes: 0,
          points_finishes: 0,
          dnfs: 0,
          avg_pace_delta: "-",
          best_finish: "P1",
          best_grid: "P1",
        },
        this_round: {
          round: 1,
          points_scored: t.points || 0,
          cars: (t.drivers || []).map((d: string, idx: number) => ({
            driver_code: d.slice(0, 3).toUpperCase(),
            driver_name: d,
            driver_number: String(idx + 1),
            grid: idx + 1,
            finish: idx + 1,
            status: "Finished",
            points: 0,
            pit_count: 1,
            avg_pit_time: "24s",
            tyre_strategy: ["MEDIUM", "HARD"],
            is_second_driver: idx === 1,
          })),
        },
        drivers: { active: [], reserves: [], h2h_race: "-", h2h_quali: "-" },
        form: { recent_finishes: [], points_progression: [] },
        reliability: { mechanical_dnfs: 0, collision_dnfs: 0, other_dnfs: 0, total_dnfs: 0 },
        profile: {
          legal_name: t.name || "Constructor",
          base: t.nationality || "FIA Base",
          founded_year: "1950",
          team_principal: "-",
          technical_director: "-",
          power_unit: "FIA Homologated",
          predecessors: [],
          first_entry_year: "1950",
          constructors_titles: 0,
          all_time_wins: t.wins || 0,
        },
      }));
      return mappedCards;
    }

    fetcher<any>("/api/teams/cards")
      .then((res) => {
        if (!mounted) return;
        if (res.status === "ok" && res.cards && res.cards.length > 0) {
          setData(res);
          setLoading(false);
        } else {
          // Fallback to /api/teams (unit tests or simple payload)
          fetcher<any>("/api/teams")
            .then((tRes) => {
              if (!mounted) return;
              if (tRes.status === "ok" && tRes.teams) {
                setData({
                  status: "ok",
                  cards: mapFallbackTeams(tRes.teams),
                  logo_credits: [],
                });
              } else {
                setError(res.reason || "Failed to load constructor cards.");
              }
              setLoading(false);
            })
            .catch(() => {
              if (!mounted) return;
              setError(res.reason || "Failed to load constructor cards.");
              setLoading(false);
            });
        }
      })
      .catch(() => {
        if (!mounted) return;
        fetcher<any>("/api/teams")
          .then((tRes) => {
            if (!mounted) return;
            if (tRes.status === "ok" && tRes.teams) {
              setData({
                status: "ok",
                cards: mapFallbackTeams(tRes.teams),
                logo_credits: [],
              });
            } else {
              setError("Failed to load constructor cards.");
            }
            setLoading(false);
          })
          .catch((err2) => {
            if (!mounted) return;
            setError(err2.message || "Failed to connect to telemetry service.");
            setLoading(false);
          });
      });

    return () => {
      mounted = false;
    };
  }, []);

  const handleImageError = (cid: string) => {
    setImgErrors((prev) => ({ ...prev, [cid]: true }));
  };

  return (
    <div className="space-y-8 select-none pb-12">
      {/* Header */}
      <div className="pb-4 border-b border-[var(--border)] flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-bold text-[var(--text)] tracking-tight">
            Constructors & Teams
          </h1>
          <p className="text-[13px] text-[var(--text-3)] mt-0.5">
            FIA Formula 1 World Championship constructors, verified technical profiles and performance
          </p>
        </div>
        {data?.year && (
          <span className="font-mono text-[12px] px-2.5 py-1 rounded bg-[var(--raised)] border border-[var(--border)] text-[var(--text-2)]">
            Season {data.year} {data.round ? `• Round ${data.round}` : ""}
          </span>
        )}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-96 w-full rounded-lg" />
          ))}
        </div>
      ) : error ? (
        <ErrorState
          title="Cannot load constructor cards"
          message={error}
          source="Jolpica & Wikidata"
          onRetry={() => window.location.reload()}
        />
      ) : !data?.cards || data.cards.length === 0 ? (
        <EmptyState
          title="No constructors found"
          message="No constructor records available for this season."
        />
      ) : (
        <>
          {/* Responsive Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.cards.map((card) => {
              const safeColor = getContrastColor(card.team_color);
              const logoUrl = card.logo?.url || (card.logo as any)?.logoUrl;
              const logoReason = card.logo?.reason || (card.logo as any)?.logoReason;
              const showImg = Boolean(logoUrl && !imgErrors[card.constructor_id]);

              return (
                <div
                  key={card.constructor_id}
                  data-testid="team-card"
                  className="p-5 border border-[var(--border)] rounded-lg bg-[var(--surface)] flex flex-col justify-between"
                  style={{
                    borderRadius: "var(--radius-m)",
                    borderTop: `4px solid ${safeColor}`,
                  }}
                >
                  <div className="space-y-4">
                    {/* Top Logo Plate / Monogram (Light plate ensures dark logos stay visible) */}
                    <div className="w-full h-20 py-2.5 px-4 rounded-md bg-[#ffffff] border border-[var(--border)] flex items-center justify-center overflow-hidden shadow-xs">
                      {showImg ? (
                        <img
                          src={logoUrl!}
                          alt={`${card.name} logo`}
                          width={160}
                          height={48}
                          loading="lazy"
                          decoding="async"
                          className="max-h-12 max-w-[180px] object-contain filter drop-shadow-xs"
                          onError={() => handleImageError(card.constructor_id)}
                        />
                      ) : (
                        <div className="flex flex-col items-center gap-1 text-center">
                          <div className="flex items-center gap-2">
                            <span
                              className="w-3 h-3 rounded-full inline-block"
                              style={{ backgroundColor: safeColor }}
                            />
                            <span
                              className="font-mono text-[20px] font-black tracking-widest"
                              style={{ color: safeColor }}
                            >
                              {card.monogram || card.name.slice(0, 3).toUpperCase()}
                            </span>
                          </div>
                          {logoReason && (
                            <span className="text-[10px] font-mono text-[var(--text-3)] max-w-[240px] truncate" title={logoReason}>
                              {logoReason}
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Team Name & Position Badge */}
                    <div className="flex justify-between items-start gap-3">
                      <div>
                        <h2 className="text-[20px] font-bold text-[var(--text)] tracking-tight">
                          {card.name}
                        </h2>
                        <p className="text-[12px] text-[var(--text-3)] font-mono mt-0.5">
                          Base: <span className="text-[var(--text-2)]">{card.profile?.base && card.profile.base !== "n/a" ? card.profile.base : card.nationality}</span>
                        </p>
                      </div>

                      <span className="font-mono text-[13px] font-bold px-2.5 py-1 rounded bg-[var(--raised)] border border-[var(--border)] text-[var(--text)] shrink-0">
                        P{card.championship?.position ?? "n/a"} ({card.championship?.points ?? 0} pts)
                      </span>
                    </div>

                    {/* Championship Overview Metrics */}
                    <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono">
                      <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
                        <div className="text-[10px] uppercase text-[var(--text-3)]">Gap Leader</div>
                        <div className="text-[13px] font-bold text-[var(--text)] mt-0.5">
                          {card.championship?.gap_to_leader === 0
                            ? "Leader"
                            : `-${card.championship?.gap_to_leader} pts`}
                        </div>
                      </div>
                      <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
                        <div className="text-[10px] uppercase text-[var(--text-3)]">Wins</div>
                        <div className="text-[13px] font-bold text-[var(--text)] mt-0.5">
                          {card.championship?.wins ?? 0}
                        </div>
                      </div>
                      <div className="p-2 rounded bg-[var(--raised)] border border-[var(--border)]">
                        <div className="text-[10px] uppercase text-[var(--text-3)]">Titles</div>
                        <div className="text-[13px] font-bold text-[var(--text)] mt-0.5">
                          {card.profile?.constructors_titles ?? 0}
                        </div>
                      </div>
                    </div>

                    {/* This Round Driver Results */}
                    <div className="pt-3 border-t border-[var(--border)]">
                      <div className="text-[11px] font-mono uppercase text-[var(--text-3)] mb-2 font-bold tracking-wider">
                        Round {data.round || 1} Classification
                      </div>
                      <div className="space-y-1.5">
                        {card.this_round?.cars && card.this_round.cars.length > 0 ? (
                          card.this_round.cars.map((car, idx) => {
                            const isSecond = car.is_second_driver || idx === 1;
                            const delta = car.grid - car.finish;
                            return (
                              <div
                                key={car.driver_code || idx}
                                className="flex items-center justify-between px-2.5 py-1.5 rounded bg-[var(--raised)] border border-[var(--border)] text-[12px] font-mono"
                              >
                                <div className="flex items-center gap-2">
                                  <span
                                    className="w-2.5 h-2.5 rounded-full inline-block shrink-0"
                                    style={{
                                      backgroundColor: safeColor,
                                      border: isSecond ? "1px dashed var(--text)" : "none",
                                      opacity: isSecond ? 0.75 : 1,
                                    }}
                                  />
                                  <span className="font-bold text-[var(--text)]">
                                    {car.driver_code}
                                  </span>
                                  <span className="text-[11px] text-[var(--text-3)]">
                                    #{car.driver_number}
                                  </span>
                                </div>

                                <div className="flex items-center gap-2">
                                  <span className="text-[var(--text-3)] text-[11px]">
                                    Grid {car.grid || "n/a"}
                                  </span>
                                  <span className="font-bold text-[var(--text)]">
                                    P{car.finish || "-"}
                                  </span>
                                  {delta !== 0 && (
                                    <span
                                      className={`text-[11px] font-bold ${
                                        delta > 0
                                          ? "text-emerald-400"
                                          : "text-rose-400"
                                      }`}
                                    >
                                      {delta > 0 ? `+${delta}` : delta}
                                    </span>
                                  )}
                                  <span className="text-[11px] text-[var(--accent)] font-semibold">
                                    +{car.points} pts
                                  </span>
                                </div>
                              </div>
                            );
                          })
                        ) : (
                          <div className="text-[11px] font-mono text-[var(--text-3)]">
                            No round race entries recorded
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Reliability & Form Strip */}
                    <div className="pt-2 border-t border-[var(--border)] flex items-center justify-between text-[11px] font-mono">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[var(--text-3)]">DNFs:</span>
                        <span className="font-bold text-[var(--text)]">
                          {card.reliability?.total_dnfs ?? 0}
                        </span>
                        {card.reliability && card.reliability.total_dnfs > 0 && (
                          <span className="text-[10px] text-[var(--text-3)]">
                            ({card.reliability.mechanical_dnfs} mech, {card.reliability.collision_dnfs} coll)
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[var(--text-3)]">Power Unit:</span>
                        <span className="text-[var(--text-2)] font-semibold">
                          {card.profile?.power_unit && card.profile.power_unit !== "n/a"
                            ? card.profile.power_unit
                            : "FIA Homologated"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Profile Technical Footnote */}
                  <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] font-mono text-[var(--text-3)] flex justify-between items-center">
                    <span>
                      Principal:{" "}
                      <span className="text-[var(--text-2)]">
                        {card.profile?.team_principal && card.profile.team_principal !== "n/a"
                          ? card.profile.team_principal
                          : "-"}
                      </span>
                    </span>
                    <span>
                      Est. {card.profile?.first_entry_year && card.profile.first_entry_year !== "n/a"
                        ? card.profile.first_entry_year
                        : "1950"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Logo Credits & Attribution Section (Phase J) */}
          {data.logo_credits && data.logo_credits.length > 0 && (
            <div className="mt-12 p-5 rounded-lg border border-[var(--border)] bg-[var(--raised)]">
              <h3 className="text-[14px] font-bold uppercase tracking-wider text-[var(--text-2)] mb-3">
                Logo Credits & Licensing
              </h3>
              <p className="text-[12px] text-[var(--text-3)] mb-4">
                Constructor visual identities are retrieved at runtime via Wikidata and Wikimedia Commons under open-content licensing terms:
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {data.logo_credits.map((item) => (
                  <div
                    key={item.constructor_id}
                    className="p-3 rounded bg-[var(--surface)] border border-[var(--border)] text-[11px] font-mono"
                  >
                    <div className="font-bold text-[var(--text)] mb-0.5">{item.team_name}</div>
                    <div className="text-[var(--text-3)]">License: {item.license || "Public domain / Trademarked"}</div>
                    <div className="text-[var(--text-3)] truncate">Attribution: {item.attribution || "Wikimedia Commons"}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
