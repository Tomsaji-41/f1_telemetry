"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Sun, Moon, Sparkles } from "lucide-react";
import { Logo } from "@/components/Logo";
import { brand } from "@/config/brand";
import en from "@/content/en.json";

interface ScheduleRace {
  round: number;
  race_name: string;
  status: string;
  date?: string;
}

export function Navbar(): React.JSX.Element {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const currentYear = new Date().getFullYear();
  const yearParam = searchParams.get("year") || String(currentYear);
  const roundParam = searchParams.get("round");
  const sessionParam = searchParams.get("session") || "R";

  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [healthStatus, setHealthStatus] = useState<"online" | "offline">("online");
  const [fetchedAt, setFetchedAt] = useState<string>("");
  const [scrollProgress, setScrollProgress] = useState(0);

  const [schedule, setSchedule] = useState<ScheduleRace[]>([]);
  const [latestRound, setLatestRound] = useState<number>(1);
  const [latestRaceName, setLatestRaceName] = useState<string>("");
  const [availableYears, setAvailableYears] = useState<number[]>(
    Array.from({ length: 12 }, (_, i) => currentYear - i)
  );

  // Fetch available sessions & latest completed round from backend
  useEffect(() => {
    fetch("/api/sessions/available")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        if (Array.isArray(data.seasons) && data.seasons.length > 0) {
          setAvailableYears(data.seasons.slice(0, 25));
        }
        if (data.latest_completed) {
          setLatestRound(data.latest_completed.round);
          setLatestRaceName(data.latest_completed.grand_prix || "");
          if (!searchParams.get("year")) {
            const params = new URLSearchParams(searchParams.toString());
            params.set("year", String(data.latest_completed.year));
            if (!searchParams.get("round")) {
              params.set("round", String(data.latest_completed.round));
            }
            router.replace(`${pathname}?${params.toString()}`);
          }
        }
      })
      .catch(() => {});
  }, [pathname, router, searchParams]);

  // Initialize and toggle theme
  useEffect(() => {
    const raw = localStorage.getItem("telemetra_theme") || localStorage.getItem("pitboss_theme");
    const savedTheme: "dark" | "light" = raw === "light" ? "light" : "dark";
    setTheme(savedTheme);
    document.documentElement.setAttribute("data-theme", savedTheme);
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    localStorage.setItem("telemetra_theme", nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
  };

  // Scroll progress for E6
  useEffect(() => {
    const handleScroll = () => {
      const totalScroll = document.documentElement.scrollHeight - window.innerHeight;
      if (totalScroll > 0) {
        setScrollProgress((window.scrollY / totalScroll) * 100);
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Fetch schedule and determine latest completed round
  useEffect(() => {
    let isMounted = true;
    fetch(`/api/schedule?year=${yearParam}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!isMounted || !data) return;
        if (data.schedule && Array.isArray(data.schedule)) {
          setSchedule(data.schedule);
        }
        const lRnd = data.latest_completed_round || 1;
        setLatestRound(lRnd);
        if (data.latest_completed_race) {
          setLatestRaceName(data.latest_completed_race.race_name || "");
        }
        // If no round was explicitly selected in URL, default to latest completed round
        if (!roundParam && lRnd) {
          const params = new URLSearchParams(searchParams.toString());
          params.set("round", String(lRnd));
          router.replace(`${pathname}?${params.toString()}`);
        }
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, [yearParam, roundParam, pathname, router, searchParams]);

  // Check backend health and page-level fetched_at
  useEffect(() => {
    const check = () => {
      fetch("/api/health")
        .then((res) => {
          if (res.ok) {
            setHealthStatus("online");
            return res.json();
          } else {
            setHealthStatus("offline");
            return null;
          }
        })
        .then((data) => {
          if (data?.fetched_at) {
            setFetchedAt(data.fetched_at);
          }
        })
        .catch(() => setHealthStatus("offline"));
    };

    check();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, []);

  // Update global context in URL
  const updateContext = (key: string, val: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set(key, val);
    router.push(`${pathname}?${params.toString()}`);
  };

  const handleSelectLatest = () => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("round", String(latestRound));
    router.push(`${pathname}?${params.toString()}`);
  };

  const activeRound = roundParam ? parseInt(roundParam, 10) : latestRound;
  const isViewingLatest = activeRound === latestRound;

  return (
    <header className="sticky top-0 z-40 w-full h-14 bg-[var(--surface)] border-b border-[var(--border)] select-none">
      <div className="flex h-full items-center justify-between px-4 sm:px-6 max-w-[1480px] mx-auto gap-4">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2 group">
            <Logo height={28} />
            <span className="text-[16px] font-semibold tracking-tight text-[var(--text)] group-hover:text-[var(--accent)] transition-colors">
              {brand.appName}
            </span>
          </Link>

          {/* Context Selector: Season, Race, Session + Latest race chip */}
          <div className="hidden md:flex items-center gap-2 ml-4">
            <div className="flex items-center gap-1.5 px-2 py-1 bg-[var(--raised)] border border-[var(--border)] rounded text-[12px] font-mono">
              <span className="text-[var(--text-3)]">{en.topbar.seasonLabel}:</span>
              <select
                value={yearParam}
                onChange={(e) => updateContext("year", e.target.value)}
                className="bg-transparent text-[var(--text)] focus:outline-none cursor-pointer"
                aria-label="Select season"
              >
                {availableYears.map((y) => (
                  <option key={y} value={y} className="bg-[var(--surface)]">
                    {y}
                  </option>
                ))}
              </select>

              <span className="text-[var(--border)]">|</span>

              <span className="text-[var(--text-3)]">{en.topbar.raceLabel}:</span>
              <select
                value={String(activeRound)}
                onChange={(e) => updateContext("round", e.target.value)}
                className="bg-transparent text-[var(--text)] focus:outline-none cursor-pointer max-w-[160px] truncate"
                aria-label="Select race round"
              >
                {schedule.length > 0 ? (
                  schedule.map((r) => (
                    <option key={r.round} value={r.round} className="bg-[var(--surface)]">
                      R{r.round} {r.race_name ? `— ${r.race_name.replace(" Grand Prix", "")}` : ""}
                    </option>
                  ))
                ) : (
                  Array.from({ length: 24 }, (_, i) => i + 1).map((r) => (
                    <option key={r} value={r} className="bg-[var(--surface)]">
                      Round {r}
                    </option>
                  ))
                )}
              </select>

              <span className="text-[var(--border)]">|</span>

              <span className="text-[var(--text-3)]">{en.topbar.sessionLabel}:</span>
              <select
                value={sessionParam}
                onChange={(e) => updateContext("session", e.target.value)}
                className="bg-transparent text-[var(--text)] focus:outline-none cursor-pointer"
                aria-label="Select session"
              >
                <option value="R" className="bg-[var(--surface)]">Race</option>
                <option value="Q" className="bg-[var(--surface)]">Qualifying</option>
                <option value="FP3" className="bg-[var(--surface)]">FP3</option>
              </select>
            </div>

            {/* "Latest race" Chip */}
            <button
              type="button"
              onClick={handleSelectLatest}
              className={`flex items-center gap-1 px-2.5 py-1 text-[11px] font-mono rounded border transition-colors ${
                isViewingLatest
                  ? "bg-[var(--accent)] text-white border-[var(--accent)] font-semibold shadow-xs"
                  : "bg-[var(--surface-2)] text-[var(--text-2)] border-[var(--border)] hover:text-[var(--text)] hover:border-[var(--border-strong)]"
              }`}
              title={`Latest completed race: R${latestRound} ${latestRaceName}`}
            >
              <Sparkles className="w-3 h-3" />
              <span>Latest race (R{latestRound})</span>
            </button>
          </div>
        </div>

        {/* Right Tools: Page-level "Data as of", Health Badge, Theme */}
        <div className="flex items-center gap-3">
          {/* Page-level "Data as of <fetched_at>" */}
          <div
            className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono text-[var(--text-3)] bg-[var(--raised)] border border-[var(--border)] rounded"
            title="Page-level telemetry freshness — individual panels show exact per-source timing in tooltips"
          >
            <span>{fetchedAt ? `Data as of ${fetchedAt}` : "Connecting to telemetry..."}</span>
          </div>

          {/* Health Badge */}
          <div className="flex items-center gap-1.5 px-2 py-0.5 text-[11px] font-mono border border-[var(--border)] bg-[var(--raised)] rounded">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                healthStatus === "online" ? "bg-[var(--positive)]" : "bg-[var(--negative)]"
              }`}
            />
            <span className={healthStatus === "online" ? "text-[var(--text-2)]" : "text-[var(--negative)] font-medium"}>
              {healthStatus === "online" ? en.topbar.healthOnline : "Backend offline"}
            </span>
          </div>

          {/* Theme Toggle */}
          <button
            type="button"
            onClick={toggleTheme}
            className="p-1.5 text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--raised)] border border-[var(--border)] rounded transition-colors"
            aria-label={theme === "dark" ? en.topbar.themeToggleLight : en.topbar.themeToggleDark}
          >
            {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Scroll-progress line */}
      <div
        className="h-[2px] bg-[var(--accent)] transition-all duration-75"
        style={{ width: `${scrollProgress}%` }}
      />
    </header>
  );
}
