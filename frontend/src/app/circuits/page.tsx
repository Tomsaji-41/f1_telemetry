"use client";

import React, { useState, useEffect, useMemo, Suspense } from "react";
import dynamic from "next/dynamic";
import { useSearchParams, useRouter } from "next/navigation";
import { fetcher } from "@/lib/api";
import { Skeleton, ErrorState, EmptyState } from "@/components/primitives/kit";

const Track3D = dynamic(() => import("@/features/circuits/Track3D"), {
  ssr: false,
  loading: () => (
    <div className="h-[520px] bg-[#101318] rounded-lg animate-pulse flex items-center justify-center text-xs font-mono text-[var(--text-3)]">
      Loading interactive 3D track telemetry...
    </div>
  ),
});

interface CircuitCatalogItem {
  circuit_id: string;
  name?: string;
  circuit_name?: string;
  locality: string;
  country: string;
  latitude: number;
  longitude: number;
  url?: string;
  wiki_url?: string;
  has_3d?: boolean;
  has_geometry_3d?: boolean;
  first_gp_year?: number;
  total_gps_held?: number;
}

interface CircuitDetails {
  status: string;
  circuit_id: string;
  name: string;
  identity: {
    circuit_id: string;
    name: string;
    locality: string;
    country: string;
    latitude: number;
    longitude: number;
    timezone: string;
    altitude_meters: number | null;
  };
  track_facts: {
    length_km: number | null;
    corner_count: number | null;
    direction: string;
    first_gp_year: number;
    total_gps_held: number;
    longest_straight_meters: number | null;
    scheduled_laps: number | null;
    race_distance_km: number | null;
  };
  race_history: {
    total_gps_held: number;
    first_gp_year: number;
    most_wins_driver: string;
    most_wins_constructor: string;
    recent_winners: Array<{
      year: number;
      grand_prix: string;
      driver: string;
      team: string;
    }>;
    lap_record: string | null;
  };
  race_character: {
    status?: string;
    reason?: string;
    safety_car_frequency?: string;
    vsc_frequency?: string;
    red_flag_frequency?: string;
    pit_stop_average?: number;
    average_race_pace?: string;
  };
  climate: {
    status: string;
    avg_race_temp?: string;
    rainfall_probability?: string;
    precipitation_mm?: number;
    recorded_date?: string;
    weather_source?: string;
    reason?: string;
  };
  description: {
    text: string;
    source_url: string;
    attribution: string;
  };
  has_geometry_3d: boolean;
}

function CircuitsContent(): React.JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialCircuit = searchParams.get("circuit") || "";

  // State
  const [scope, setScope] = useState<"season" | "all">("season");
  const [catalog, setCatalog] = useState<CircuitCatalogItem[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState<boolean>(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  const [selectedCircuitId, setSelectedCircuitId] = useState<string>(initialCircuit);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedCountry, setSelectedCountry] = useState<string>("all");
  const [activeTab, setActiveTab] = useState<"3d" | "map" | "facts" | "history">("3d");

  const [circuitDetails, setCircuitDetails] = useState<CircuitDetails | null>(null);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);
  const [detailsError, setDetailsError] = useState<string | null>(null);

  const [geometryData, setGeometryData] = useState<any | null>(null);
  const [loadingGeometry, setLoadingGeometry] = useState<boolean>(false);
  const [geometryError, setGeometryError] = useState<string | null>(null);

  const loadGeometry = React.useCallback((circuitId: string) => {
    if (!circuitId) return;
    setLoadingGeometry(true);
    setGeometryError(null);
    fetcher<any>(`/api/circuits/${circuitId}/geometry`)
      .then((geom) => {
        setGeometryData(geom);
        setLoadingGeometry(false);
      })
      .catch((err) => {
        setGeometryError(err.message || "Failed to load circuit geometry.");
        setLoadingGeometry(false);
      });
  }, []);

  // 1. Fetch catalog on scope change
  useEffect(() => {
    let mounted = true;
    setLoadingCatalog(true);
    fetcher<{ status: string; circuits: CircuitCatalogItem[]; reason?: string }>(
      `/api/circuits?scope=${scope}`
    )
      .then((res) => {
        if (!mounted) return;
        if (res.status === "ok") {
          setCatalog(res.circuits || []);
          if (!selectedCircuitId && res.circuits?.length > 0) {
            const defaultId = res.circuits[0].circuit_id;
            setSelectedCircuitId(defaultId);
            router.replace(`/circuits?circuit=${defaultId}`, { scroll: false });
          }
        } else {
          setCatalogError(res.reason || "Failed to load circuits.");
        }
        setLoadingCatalog(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setCatalogError(err.message || "Network error loading circuits.");
        setLoadingCatalog(false);
      });

    return () => {
      mounted = false;
    };
  }, [scope]);

  // Sync selectedCircuitId if query param changes externally
  useEffect(() => {
    const param = searchParams.get("circuit");
    if (param && param !== selectedCircuitId) {
      setSelectedCircuitId(param);
    }
  }, [searchParams]);

  // 2. Fetch details & geometry when selectedCircuitId changes
  useEffect(() => {
    if (!selectedCircuitId) return;

    let mounted = true;
    setLoadingDetails(true);
    setDetailsError(null);

    // Fetch details
    fetcher<CircuitDetails>(`/api/circuits/${selectedCircuitId}`)
      .then((data) => {
        if (!mounted) return;
        if (data.status === "ok") {
          setCircuitDetails(data);
        } else {
          setDetailsError(data.description?.text || "Circuit records not available.");
          setCircuitDetails(null);
        }
        setLoadingDetails(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setDetailsError(err.message || "Failed to load circuit details.");
        setLoadingDetails(false);
      });

    // Fetch 3D geometry
    loadGeometry(selectedCircuitId);

    return () => {
      mounted = false;
    };
  }, [selectedCircuitId, loadGeometry]);

  const handleSelectCircuit = (id: string) => {
    setSelectedCircuitId(id);
    router.replace(`/circuits?circuit=${id}`, { scroll: false });
  };

  // Filter catalog
  const filteredCatalog = useMemo(() => {
    return catalog.filter((item) => {
      const cName = (item.name || item.circuit_name || "").toLowerCase();
      const matchSearch =
        !searchQuery ||
        cName.includes(searchQuery.toLowerCase()) ||
        (item.locality || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
        (item.country || "").toLowerCase().includes(searchQuery.toLowerCase());
      const matchCountry =
        selectedCountry === "all" || item.country.toLowerCase() === selectedCountry.toLowerCase();
      return matchSearch && matchCountry;
    });
  }, [catalog, searchQuery, selectedCountry]);

  // Distinct countries for filter dropdown
  const countries = useMemo(() => {
    const set = new Set<string>();
    catalog.forEach((c) => {
      if (c.country) set.add(c.country);
    });
    return Array.from(set).sort();
  }, [catalog]);

  return (
    <div className="space-y-8 select-none pb-16">
      {/* Page Header */}
      <div className="pb-4 border-b border-[var(--border)] flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-bold text-[var(--text)] tracking-tight">
            Formula 1 Circuits & Tracks
          </h1>
          <p className="text-[13px] text-[var(--text-3)] mt-0.5">
            Interactive 3D track geometries, elevation gradients, historical records, and GPS coordinates
          </p>
        </div>

        {/* Scope Selector: Season vs All-Time */}
        <div className="flex items-center gap-1 p-1 rounded-lg bg-[var(--raised)] border border-[var(--border)] text-xs font-mono">
          <button
            onClick={() => setScope("season")}
            className={`px-3 py-1.5 rounded transition ${
              scope === "season"
                ? "bg-[var(--surface)] text-[var(--text)] font-bold shadow-sm"
                : "text-[var(--text-3)] hover:text-[var(--text)]"
            }`}
          >
            In 2024 Season
          </button>
          <button
            onClick={() => setScope("all")}
            className={`px-3 py-1.5 rounded transition ${
              scope === "all"
                ? "bg-[var(--surface)] text-[var(--text)] font-bold shadow-sm"
                : "text-[var(--text-3)] hover:text-[var(--text)]"
            }`}
          >
            All-Time Circuits ({catalog.length || 78})
          </button>
        </div>
      </div>

      {/* Page-Level Circuit Selector Control */}
      <div className="p-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[240px]">
          <label className="block text-[11px] font-mono uppercase text-[var(--text-3)] mb-1">
            Active Circuit
          </label>
          <select
            value={selectedCircuitId}
            onChange={(e) => handleSelectCircuit(e.target.value)}
            className="w-full px-3 py-2 rounded bg-[var(--raised)] border border-[var(--border)] text-sm font-semibold text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
          >
            {catalog.map((item) => (
              <option key={item.circuit_id} value={item.circuit_id}>
                {item.name} — {item.locality}, {item.country} {item.has_3d ? "(3D Available)" : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="w-48">
          <label className="block text-[11px] font-mono uppercase text-[var(--text-3)] mb-1">
            Country Filter
          </label>
          <select
            value={selectedCountry}
            onChange={(e) => setSelectedCountry(e.target.value)}
            className="w-full px-3 py-2 rounded bg-[var(--raised)] border border-[var(--border)] text-xs font-mono text-[var(--text)] focus:outline-none"
          >
            <option value="all">All Countries ({countries.length})</option>
            {countries.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div className="w-56">
          <label className="block text-[11px] font-mono uppercase text-[var(--text-3)] mb-1">
            Search
          </label>
          <input
            type="text"
            placeholder="Search venue or city..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3 py-2 rounded bg-[var(--raised)] border border-[var(--border)] text-xs font-mono text-[var(--text)] focus:outline-none placeholder:text-[var(--text-3)]"
          />
        </div>
      </div>

      {/* Selected Circuit Detail Panel */}
      {loadingDetails ? (
        <div className="space-y-4">
          <Skeleton className="h-16 w-full rounded-lg" />
          <Skeleton className="h-[520px] w-full rounded-lg" />
        </div>
      ) : detailsError ? (
        <div className="p-6 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-center">
          <div className="text-sm font-bold text-rose-400 mb-1">Circuit Not Available</div>
          <p className="text-xs text-[var(--text-3)] mb-4">{detailsError}</p>
          <button
            onClick={() => handleSelectCircuit(catalog[0]?.circuit_id || "silverstone")}
            className="px-4 py-2 rounded bg-[var(--raised)] border border-[var(--border)] text-xs font-mono text-[var(--text)]"
          >
            Reset to Primary Circuit
          </button>
        </div>
      ) : circuitDetails ? (
        <div className="space-y-6">
          {/* Circuit Header Hero */}
          <div className="p-6 rounded-lg border border-[var(--border)] bg-[var(--surface)] flex flex-wrap justify-between items-start gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="w-2.5 h-2.5 rounded-full bg-[#e10600]" />
                <span className="font-mono text-xs uppercase tracking-wider text-[var(--text-3)]">
                  {circuitDetails.identity.locality}, {circuitDetails.identity.country}
                </span>
                {circuitDetails.identity.altitude_meters !== null && (
                  <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[var(--raised)] border border-[var(--border)] text-[var(--text-2)]">
                    Elev: {circuitDetails.identity.altitude_meters}m
                  </span>
                )}
              </div>
              <h2 className="text-[26px] font-bold text-[var(--text)] tracking-tight">
                {circuitDetails.name}
              </h2>
            </div>

            <div className="flex items-center gap-3 text-right font-mono">
              <div className="px-3 py-1.5 rounded bg-[var(--raised)] border border-[var(--border)]">
                <div className="text-[10px] text-[var(--text-3)] uppercase">First Grand Prix</div>
                <div className="text-[14px] font-bold text-[var(--text)]">
                  {circuitDetails.track_facts.first_gp_year}
                </div>
              </div>
              <div className="px-3 py-1.5 rounded bg-[var(--raised)] border border-[var(--border)]">
                <div className="text-[10px] text-[var(--text-3)] uppercase">GPs Hosted</div>
                <div className="text-[14px] font-bold text-[var(--text)]">
                  {circuitDetails.track_facts.total_gps_held}
                </div>
              </div>
            </div>
          </div>

          {/* Visualization & Detail Tabs */}
          <div className="flex items-center gap-2 border-b border-[var(--border)] pb-2 text-xs font-mono">
            <button
              onClick={() => setActiveTab("3d")}
              className={`px-4 py-2 rounded-t font-semibold transition ${
                activeTab === "3d"
                  ? "bg-[var(--raised)] text-[var(--text)] border-b-2 border-[#e10600]"
                  : "text-[var(--text-3)] hover:text-[var(--text)]"
              }`}
            >
              3D Track Render
            </button>
            <button
              onClick={() => setActiveTab("map")}
              className={`px-4 py-2 rounded-t font-semibold transition ${
                activeTab === "map"
                  ? "bg-[var(--raised)] text-[var(--text)] border-b-2 border-[#e10600]"
                  : "text-[var(--text-3)] hover:text-[var(--text)]"
              }`}
            >
              Location GPS Map
            </button>
            <button
              onClick={() => setActiveTab("facts")}
              className={`px-4 py-2 rounded-t font-semibold transition ${
                activeTab === "facts"
                  ? "bg-[var(--raised)] text-[var(--text)] border-b-2 border-[#e10600]"
                  : "text-[var(--text-3)] hover:text-[var(--text)]"
              }`}
            >
              Track Facts & History
            </button>
            <button
              onClick={() => setActiveTab("history")}
              className={`px-4 py-2 rounded-t font-semibold transition ${
                activeTab === "history"
                  ? "bg-[var(--raised)] text-[var(--text)] border-b-2 border-[#e10600]"
                  : "text-[var(--text-3)] hover:text-[var(--text)]"
              }`}
            >
              Race Character & Climate
            </button>
          </div>

          {/* Tab 1: 3D Track Render (P5/Phase K) */}
          {activeTab === "3d" && (
            <div>
              {loadingGeometry ? (
                <div className="h-[520px] rounded-lg border border-[var(--border)] bg-[#101318] flex flex-col items-center justify-center space-y-3">
                  <div className="w-8 h-8 rounded-full border-2 border-[var(--accent)] border-t-transparent animate-spin" />
                  <span className="text-xs font-mono text-[var(--text-3)]">
                    Loading high-precision track coordinates...
                  </span>
                </div>
              ) : geometryError ? (
                <ErrorState
                  title="Failed to load track geometry"
                  message={geometryError}
                  source="FastF1 MultiViewer & OSM"
                  onRetry={() => loadGeometry(selectedCircuitId)}
                />
              ) : geometryData?.status === "not_available" ? (
                <div className="p-8 rounded-lg border border-[var(--border)] bg-[var(--raised)] text-center flex flex-col items-center justify-center min-h-[380px]">
                  <div className="text-xs font-mono text-[var(--accent)] font-bold uppercase mb-2">
                    Telemetry Track Geometry Unavailable
                  </div>
                  <p className="text-[13px] text-[var(--text-3)] max-w-md mb-4">
                    {geometryData.reason || "No recorded GPS or telemetry position stream exists for this circuit layout."}
                  </p>
                  <p className="text-[11px] font-mono text-[var(--text-3)] mb-6">
                    {geometryData.coverage_note || "3D layout requires FastF1 position telemetry stream (2018+) or verified OSM raceway geometry."}
                  </p>
                  <button
                    onClick={() => setActiveTab("map")}
                    className="px-4 py-2 rounded bg-[var(--accent)] text-white text-xs font-mono font-semibold hover:opacity-90 transition"
                  >
                    View Satellite / GPS Map
                  </button>
                </div>
              ) : geometryData ? (
                <Track3D geometry={geometryData} />
              ) : (
                <div className="h-64 rounded-lg border border-[var(--border)] bg-[var(--surface)] flex items-center justify-center text-xs font-mono text-[var(--text-3)]">
                  Select a circuit to view track layout
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Location Map */}
          {activeTab === "map" && (
            <div className="rounded-lg border border-[var(--border)] overflow-hidden bg-[#101318]">
              <div className="p-3 bg-[var(--raised)] border-b border-[var(--border)] flex justify-between items-center text-xs font-mono">
                <span>
                  Coordinates: {circuitDetails.identity.latitude.toFixed(4)}°N,{" "}
                  {circuitDetails.identity.longitude.toFixed(4)}°E
                </span>
                <span className="text-[var(--text-3)]">
                  Map data © OpenStreetMap contributors (ODbL)
                </span>
              </div>
              <iframe
                title="Circuit Location Map"
                className="w-full h-[520px] border-0"
                src={`https://www.openstreetmap.org/export/embed.html?bbox=${circuitDetails.identity.longitude - 0.035}%2C${circuitDetails.identity.latitude - 0.025}%2C${circuitDetails.identity.longitude + 0.035}%2C${circuitDetails.identity.latitude + 0.025}&layer=mapnik&marker=${circuitDetails.identity.latitude}%2C${circuitDetails.identity.longitude}`}
              />
            </div>
          )}

          {/* Tab 3: Track Facts & History */}
          {activeTab === "facts" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Technical Facts */}
              <div className="p-5 rounded-lg border border-[var(--border)] bg-[var(--surface)] space-y-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-2)] font-mono border-b border-[var(--border)] pb-2">
                  Technical Specifications
                </h3>
                <div className="grid grid-cols-2 gap-4 text-xs font-mono">
                  <div>
                    <span className="text-[var(--text-3)] block mb-0.5">Circuit Length</span>
                    <span className="text-sm font-bold text-[var(--text)]">
                      {circuitDetails.track_facts.length_km ? `${circuitDetails.track_facts.length_km} km` : "n/a"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-3)] block mb-0.5">Turns</span>
                    <span className="text-sm font-bold text-[var(--text)]">
                      {circuitDetails.track_facts.corner_count || "n/a"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-3)] block mb-0.5">Direction</span>
                    <span className="text-sm font-bold text-[var(--text)] uppercase">
                      {circuitDetails.track_facts.direction}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-3)] block mb-0.5">Longest Straight</span>
                    <span className="text-sm font-bold text-[var(--text)]">
                      {circuitDetails.track_facts.longest_straight_meters
                        ? `${circuitDetails.track_facts.longest_straight_meters} m`
                        : "n/a"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-3)] block mb-0.5">Race Distance</span>
                    <span className="text-sm font-bold text-[var(--text)]">
                      {circuitDetails.track_facts.race_distance_km
                        ? `${circuitDetails.track_facts.race_distance_km} km (${circuitDetails.track_facts.scheduled_laps} laps)`
                        : "n/a"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-3)] block mb-0.5">Official Lap Record</span>
                    <span className="text-xs font-bold text-[var(--text)]">
                      {circuitDetails.race_history.lap_record || "Unrecorded"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Historical Winners & Records */}
              <div className="p-5 rounded-lg border border-[var(--border)] bg-[var(--surface)] space-y-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-2)] font-mono border-b border-[var(--border)] pb-2">
                  Championship Records
                </h3>
                <div className="grid grid-cols-2 gap-4 text-xs font-mono mb-4">
                  <div>
                    <span className="text-[var(--text-3)] block mb-0.5">Most Driver Wins</span>
                    <span className="text-sm font-bold text-[var(--text)]">
                      {circuitDetails.race_history.most_wins_driver}
                    </span>
                  </div>
                  <div>
                    <span className="text-[var(--text-3)] block mb-0.5">Most Constructor Wins</span>
                    <span className="text-sm font-bold text-[var(--text)]">
                      {circuitDetails.race_history.most_wins_constructor}
                    </span>
                  </div>
                </div>

                <div className="text-[11px] font-mono text-[var(--text-3)] uppercase font-bold mb-2">
                  Recent Grand Prix Winners
                </div>
                <div className="space-y-1.5">
                  {circuitDetails.race_history.recent_winners?.length > 0 ? (
                    circuitDetails.race_history.recent_winners.slice(-5).map((w, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2 rounded bg-[var(--raised)] border border-[var(--border)] text-xs font-mono"
                      >
                        <span className="font-bold text-[var(--text-2)]">{w.year}</span>
                        <span className="font-semibold text-[var(--text)]">{w.driver}</span>
                        <span className="text-[var(--text-3)]">{w.team}</span>
                      </div>
                    ))
                  ) : (
                    <div className="text-xs font-mono text-[var(--text-3)]">
                      No historical winners on record
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Tab 4: Race Character & Climate */}
          {activeTab === "history" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Climate & Weather */}
              <div className="p-5 rounded-lg border border-[var(--border)] bg-[var(--surface)] space-y-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-2)] font-mono border-b border-[var(--border)] pb-2">
                  Historical Climate & Weather
                </h3>
                {circuitDetails.climate?.status === "ok" ? (
                  <div className="grid grid-cols-2 gap-4 text-xs font-mono">
                    <div>
                      <span className="text-[var(--text-3)] block mb-0.5">Typical Race Temp</span>
                      <span className="text-sm font-bold text-[var(--text)]">
                        {circuitDetails.climate.avg_race_temp}
                      </span>
                    </div>
                    <div>
                      <span className="text-[var(--text-3)] block mb-0.5">Precipitation Status</span>
                      <span className="text-sm font-bold text-[var(--text)]">
                        {circuitDetails.climate.rainfall_probability}
                      </span>
                    </div>
                    <div className="col-span-2 text-[11px] text-[var(--text-3)]">
                      Archived observation date: {circuitDetails.climate.recorded_date || "Race weekend"} • Source:{" "}
                      {circuitDetails.climate.weather_source}
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded bg-[var(--raised)] border border-[var(--border)] text-xs font-mono text-[var(--text-3)]">
                    {circuitDetails.climate?.reason || "Historical weather archive unavailable for circuit coordinates."}
                  </div>
                )}
              </div>

              {/* Race Character */}
              <div className="p-5 rounded-lg border border-[var(--border)] bg-[var(--surface)] space-y-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-2)] font-mono border-b border-[var(--border)] pb-2">
                  Session Race Character
                </h3>
                <div className="p-4 rounded bg-[var(--raised)] border border-[var(--border)] text-xs font-mono text-[var(--text-3)] space-y-2">
                  <p>{circuitDetails.race_character?.reason || "Safety car and pit stop telemetry requires session telemetry logs (FastF1 2018+)."}</p>
                  <p className="text-[10px] text-[var(--text-3)]">
                    Per Honest Limits: synthetic safety car frequencies are never fabricated.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Wikipedia Architectural Summary */}
          {circuitDetails.description && (
            <div className="p-5 rounded-lg border border-[var(--border)] bg-[var(--surface)] space-y-2">
              <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--text-3)] font-bold">
                Venue Background & History
              </h3>
              <p className="text-xs text-[var(--text-2)] leading-relaxed">
                {circuitDetails.description.text}
              </p>
              <div className="pt-2 text-[11px] font-mono text-[var(--text-3)] flex items-center justify-between border-t border-[var(--border)]">
                <span>Attribution: {circuitDetails.description.attribution}</span>
                {circuitDetails.description.source_url && (
                  <a
                    href={circuitDetails.description.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[var(--accent)] hover:underline"
                  >
                    Wikipedia Article →
                  </a>
                )}
              </div>
            </div>
          )}
        </div>
      ) : null}

      {/* Catalog Cards Section (Strictly Static Rule) */}
      <div className="space-y-4 pt-6 border-t border-[var(--border)]">
        <div className="flex items-baseline justify-between">
          <h3 className="text-[18px] font-bold text-[var(--text)]">
            {scope === "season" ? "Season 2024 Circuits" : "All-Time Championship Venues"} ({filteredCatalog.length})
          </h3>
          <span className="text-xs font-mono text-[var(--text-3)]">
            Selection driven solely via active circuit selector above
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filteredCatalog.map((c) => {
            const isCurrent = c.circuit_id === selectedCircuitId;
            return (
              <div
                key={c.circuit_id}
                data-testid="circuit-card"
                className={`p-4 rounded-lg border bg-[var(--surface)] flex flex-col justify-between ${
                  isCurrent ? "border-[#e10600] ring-1 ring-[#e10600]" : "border-[var(--border)]"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-mono text-[var(--text-3)] uppercase">
                      {c.country}
                    </span>
                    {c.has_3d && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                        3D Ready
                      </span>
                    )}
                  </div>
                  <h4 className="text-sm font-bold text-[var(--text)] line-clamp-1 mb-0.5">
                    {c.name}
                  </h4>
                  <p className="text-[11px] font-mono text-[var(--text-3)]">{c.locality}</p>
                </div>

                <div className="mt-3 pt-2 border-t border-[var(--border)] text-[11px] font-mono text-[var(--text-3)] flex justify-between">
                  <span>GPS: {c.latitude.toFixed(2)}°, {c.longitude.toFixed(2)}°</span>
                  {isCurrent && <span className="font-bold text-[#e10600]">Viewing</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function CircuitsPage(): React.JSX.Element {
  return (
    <Suspense
      fallback={
        <div className="p-8 space-y-4">
          <Skeleton className="h-16 w-full rounded" />
          <Skeleton className="h-96 w-full rounded" />
        </div>
      }
    >
      <CircuitsContent />
    </Suspense>
  );
}
