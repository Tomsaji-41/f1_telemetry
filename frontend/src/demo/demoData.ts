export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE !== "false";
export const DEMO_LABEL = "Demo data: illustrative sample, not official results";
export const DEMO_RACE = {
  name: "Sample Grand Prix", circuit: "Demo Circuit (synthetic layout)",
  laps: 57, lengthKm: 5.0, startClock: "14:00:00", session: "Race",
};

export type Compound = "S" | "M" | "H";
export const COMPOUND_NAME: Record<Compound, string> = { S: "Soft", M: "Medium", H: "Hard" };
export const COMPOUND_COLOR: Record<Compound, string> = { S: "#E10600", M: "#FACC15", H: "#E6E8EB" };

export const TEAM_LIST = [
  { id: "red_bull", name: "Red Bull Racing", color: "#3671C6", base: "Milton Keynes, UK", note: "Entered Formula 1 in 2005 after buying Jaguar Racing." },
  { id: "mclaren", name: "McLaren", color: "#FF8000", base: "Woking, UK", note: "Founded by Bruce McLaren in 1963." },
  { id: "ferrari", name: "Ferrari", color: "#DC0000", base: "Maranello, Italy", note: "The only team to have competed in every season since 1950." },
  { id: "mercedes", name: "Mercedes", color: "#00D2BE", base: "Brackley, UK", note: "Works team since 2010, after taking over Brawn GP." },
  { id: "aston_martin", name: "Aston Martin", color: "#229971", base: "Silverstone, UK", note: "Racing under the Aston Martin name since 2021." },
] as const;
export type TeamId = (typeof TEAM_LIST)[number]["id"];
export const teamById = (id: string) => TEAM_LIST.find((t) => t.id === id)!;

// pace = seconds per lap slower than the fastest sample driver; retire = last lap completed
export const DRIVERS: {
  code: string; name: string; num: number; team: TeamId; nat: string;
  pace: number; grid: number; retire?: number;
}[] = [
  { code: "VER", name: "Max Verstappen", num: 1, team: "red_bull", nat: "Dutch", pace: 0.0, grid: 1 },
  { code: "LEC", name: "Charles Leclerc", num: 16, team: "ferrari", nat: "Monegasque", pace: 0.18, grid: 2 },
  { code: "NOR", name: "Lando Norris", num: 4, team: "mclaren", nat: "British", pace: 0.12, grid: 3 },
  { code: "PIA", name: "Oscar Piastri", num: 81, team: "mclaren", nat: "Australian", pace: 0.2, grid: 4 },
  { code: "RUS", name: "George Russell", num: 63, team: "mercedes", nat: "British", pace: 0.28, grid: 5 },
  { code: "HAM", name: "Lewis Hamilton", num: 44, team: "mercedes", nat: "British", pace: 0.3, grid: 6 },
  { code: "SAI", name: "Carlos Sainz", num: 55, team: "ferrari", nat: "Spanish", pace: 0.35, grid: 7 },
  { code: "PER", name: "Sergio Perez", num: 11, team: "red_bull", nat: "Mexican", pace: 0.45, grid: 8 },
  { code: "ALO", name: "Fernando Alonso", num: 14, team: "aston_martin", nat: "Spanish", pace: 0.55, grid: 9 },
  { code: "STR", name: "Lance Stroll", num: 18, team: "aston_martin", nat: "Canadian", pace: 0.9, grid: 10, retire: 40 },
];
export const driverByCode = (c: string) => DRIVERS.find((d) => d.code === c)!;

// ---------- deterministic random ----------
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function seedOf(s: string) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

// ---------- synthetic telemetry (one lap, 10 m grid) ----------
export const LAP_LENGTH_M = 5000;
const STEP = 10;
const N = LAP_LENGTH_M / STEP; // 500
export const CORNERS = [
  { n: 1, d: 450, v: 105 }, { n: 2, d: 900, v: 160 }, { n: 3, d: 1250, v: 85 },
  { n: 4, d: 1900, v: 220 }, { n: 5, d: 2300, v: 130 }, { n: 6, d: 2750, v: 95 },
  { n: 7, d: 3300, v: 250 }, { n: 8, d: 3700, v: 115 }, { n: 9, d: 4200, v: 145 },
  { n: 10, d: 4650, v: 90 },
]; // v = minimum speed in km/h for the reference driver
export const DRS_ZONES: [number, number][] = [[4780, 5000], [0, 380], [1330, 1800]];
const GEAR_THR = [0, 75, 105, 140, 175, 215, 260, 300];

export type Telemetry = {
  code: string; lapTime: number;
  dist: number[]; t: number[]; speed: number[]; throttle: number[]; brake: number[];
  gear: number[]; rpm: number[]; accelG: number[]; drs: number[]; x: number[]; y: number[];
};
const telCache = new Map<string, Telemetry>();

export function buildTelemetry(code: string): Telemetry {
  const hit = telCache.get(code);
  if (hit) return hit;
  const drv = driverByCode(code);
  const r = rng(seedOf(code));
  const vtop = 96.5 * (1 - drv.pace * 0.004);        // m/s (adjusted so top speed exceeds 300 km/h)
  const cf = 1 - drv.pace * 0.012;                    // corner speed factor
  const aMax = 9.0 * (1 - drv.pace * 0.01);           // m/s^2
  const bMax = 45;                                    // m/s^2
  const dist = Array.from({ length: N }, (_, i) => i * STEP);
  const drsOpen = dist.map((x) => DRS_ZONES.some(([a, b]) => x >= a && x <= b));
  const v = dist.map((_, i) => vtop + (drsOpen[i] ? 3.5 : 0));
  CORNERS.forEach((c) => {
    const k = Math.round(c.d / STEP);
    const vm = (c.v / 3.6) * cf;
    for (let j = -2; j <= 2; j++) { const idx = (k + j + N) % N; v[idx] = Math.min(v[idx], vm); }
  });
  for (let i = 2 * N - 1; i >= 0; i--) {                    // braking limit
    const idx = i % N, nx = (i + 1) % N;
    v[idx] = Math.min(v[idx], Math.sqrt(v[nx] * v[nx] + 2 * bMax * STEP));
  }
  for (let i = 0; i < 2 * N; i++) {                         // acceleration limit
    const idx = i % N, pv = (i - 1 + N) % N;
    const a = aMax * Math.max(0.05, 1 - (v[pv] / vtop) ** 2);
    v[idx] = Math.min(v[idx], Math.sqrt(v[pv] * v[pv] + 2 * a * STEP));
  }
  const t: number[] = [0];
  for (let i = 1; i < N; i++) t.push(t[i - 1] + STEP / ((v[i - 1] + v[i]) / 2));
  const lapTime = t[N - 1] + STEP / ((v[N - 1] + v[0]) / 2);
  const al = v.map((_, i) => { const nx = (i + 1) % N; return (v[nx] * v[nx] - v[i] * v[i]) / (2 * STEP); });
  const brake = al.map((a) => (a < -12 ? 1 : 0));
  const throttle = al.map((a, i) => {
    let th: number;
    if (brake[i]) th = 0;
    else if (a > 0.2) th = Math.min(100, 55 + a * 6);
    else th = v[i] > vtop * 0.985 ? 100 : 20;
    return Math.max(0, Math.min(100, th + (th > 0 && th < 100 ? (r() - 0.5) * 3 : 0)));
  });
  const accelG = al.map((_, i) => {
    const a = (al[(i - 1 + N) % N] + al[i] + al[(i + 1) % N]) / 3;
    return +(a / 9.81).toFixed(3);
  });
  const speed = v.map((s) => +(s * 3.6).toFixed(1));
  const gear = speed.map((s) => GEAR_THR.filter((th) => th <= s).length);
  const rpm = speed.map((s, i) => {
    const g = gear[i], lo = GEAR_THR[g - 1], hi = g < 8 ? GEAR_THR[g] : 340;
    return Math.round(8000 + ((s - lo) / (hi - lo)) * 5000);
  });
  const x = dist.map((d) => { const th = (2 * Math.PI * d) / LAP_LENGTH_M; const R = 1 + 0.28 * Math.cos(2 * th) + 0.18 * Math.sin(3 * th + 0.6); return +(1000 * R * Math.cos(th)).toFixed(1); });
  const y = dist.map((d) => { const th = (2 * Math.PI * d) / LAP_LENGTH_M; const R = 1 + 0.28 * Math.cos(2 * th) + 0.18 * Math.sin(3 * th + 0.6); return +(700 * R * Math.sin(th)).toFixed(1); });
  const out: Telemetry = {
    code, lapTime: +lapTime.toFixed(3), dist, t: t.map((s) => +s.toFixed(3)), speed,
    throttle: throttle.map((s) => +s.toFixed(1)), brake, gear, rpm, accelG,
    drs: drsOpen.map((o, i) => (o && !brake[i] ? 1 : 0)), x, y,
  };
  telCache.set(code, out);
  return out;
}

export function compareTelemetry(a: string, b: string) {
  const A = buildTelemetry(a), B = buildTelemetry(b);
  return { a: A, b: B, delta: A.t.map((_, i) => +(B.t[i] - A.t[i]).toFixed(3)) }; // + means B slower
}

export function brakingZones(tel: Telemetry) {
  const zones: {
    startM: number; endM: number; corner: number | null; entryKmh: number; minKmh: number;
    brakeS: number; peakG: number; exitKmh: number;
  }[] = [];
  const n = tel.dist.length;
  let i = 0;
  while (i < n) {
    if (tel.brake[i] === 1) {
      let j = i;
      while (j + 1 < n && (tel.brake[j + 1] === 1 || (j + 2 < n && tel.brake[j + 2] === 1))) j++;
      let minV = Infinity, peak = 0, dur = 0;
      for (let k = i; k <= j; k++) {
        minV = Math.min(minV, tel.speed[k]);
        peak = Math.max(peak, -tel.accelG[k]);
        dur += tel.t[Math.min(k + 1, n - 1)] - tel.t[k];
      }
      const endM = tel.dist[j];
      const corner = CORNERS.find((c) => c.d >= endM && c.d - endM <= 200)?.n ?? null;
      zones.push({
        startM: tel.dist[i], endM, corner, entryKmh: tel.speed[i], minKmh: +minV.toFixed(1),
        brakeS: +dur.toFixed(2), peakG: +peak.toFixed(2), exitKmh: tel.speed[Math.min(j + 3, n - 1)],
      });
      i = j + 1;
    } else i++;
  }
  return zones;
}

export function aeroProxies(tel: Telemetry) {
  const hs = tel.speed.filter((s) => s > 250);
  const drsSpeeds = tel.speed.filter((_, i) => tel.drs[i] === 1);
  return {
    topSpeedKmh: Math.max(...tel.speed),
    minSpeedKmh: Math.min(...tel.speed),
    highSpeedAvgKmh: hs.length ? +(hs.reduce((s, x) => s + x, 0) / hs.length).toFixed(1) : null,
    drsZoneTopKmh: drsSpeeds.length ? Math.max(...drsSpeeds) : null,
    apexKmh: CORNERS.map((c) => ({ corner: c.n, kmh: tel.speed[Math.round(c.d / STEP)] })),
    note: "Derived proxies from sample data, not measured downforce.",
  };
}

export function gearUsage(tel: Telemetry) {
  const sec = new Array(9).fill(0);
  for (let i = 0; i < tel.dist.length - 1; i++) sec[tel.gear[i]] += tel.t[i + 1] - tel.t[i];
  return sec.slice(1).map((s, k) => ({ gear: k + 1, seconds: +s.toFixed(2), share: +((s / tel.lapTime) * 100).toFixed(1) }));
}

// ---------- race simulation (57 laps, 10 cars) ----------
const TOTAL_LAPS = DEMO_RACE.laps;
const STRATS: Record<string, [Compound, number][]> = {
  VER: [["S", 16], ["M", 38], ["H", 57]], LEC: [["S", 15], ["H", 40], ["M", 57]],
  NOR: [["M", 20], ["H", 57]], PIA: [["M", 19], ["H", 57]],
  RUS: [["M", 21], ["H", 57]], HAM: [["S", 14], ["M", 36], ["H", 57]],
  SAI: [["M", 18], ["H", 57]], PER: [["S", 12], ["H", 35], ["M", 57]],
  ALO: [["M", 22], ["H", 57]], STR: [["H", 25], ["M", 57]],
};
const COMP_OFFSET: Record<Compound, number> = { S: -0.6, M: 0, H: 0.5 };
const COMP_DEG: Record<Compound, number> = { S: 0.09, M: 0.055, H: 0.035 };
const FUEL_S_PER_LAP = 0.03;
const PIT_LOSS = 21.5;
export const VSC_LAPS = [22, 23];
const POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1];

export type Stint = { driver: string; stint: number; compound: Compound; startLap: number; endLap: number; laps: number };
export type Lap = { lap: number; time: number; s1: number; s2: number; s3: number; compound: Compound; tyreAge: number; pit: boolean };

let raceCache: ReturnType<typeof buildRace> | null = null;
export const getRace = () => (raceCache ??= buildRace());

function buildRace() {
  const laps: Record<string, Lap[]> = {};
  const cum: Record<string, number[]> = {};
  const stints: Stint[] = [];
  const pits: { driver: string; stop: number; lap: number; pitLaneS: number; stationaryS: number }[] = [];
  DRIVERS.forEach((d) => {
    const r = rng(seedOf("race" + d.code));
    const ref = buildTelemetry(d.code).lapTime;
    const plan = STRATS[d.code];
    let start = 1;
    const rows: Lap[] = [];
    const last = d.retire ?? TOTAL_LAPS;
    plan.forEach(([c, end], si) => {
      const realEnd = Math.min(end, last);
      if (start <= realEnd) stints.push({ driver: d.code, stint: si + 1, compound: c, startLap: start, endLap: realEnd, laps: realEnd - start + 1 });
      for (let n = start; n <= realEnd; n++) {
        const age = n - start + 1;
        const pit = n === end && end < TOTAL_LAPS && n <= last;
        let lt = ref + FUEL_S_PER_LAP * (TOTAL_LAPS - n) + COMP_OFFSET[c] + COMP_DEG[c] * age + (r() - 0.5) * 0.24;
        if (pit) lt += PIT_LOSS + r() * 0.8;
        if (n === 1) lt += 4.0;
        if (n === VSC_LAPS[0]) lt *= 1.35;
        if (n === VSC_LAPS[1]) lt *= 1.2;
        const d1 = (r() - 0.5) * 0.004, d2 = (r() - 0.5) * 0.004;
        const s1 = lt * (0.28 + d1), s2 = lt * (0.4 + d2);
        rows.push({ lap: n, time: +lt.toFixed(3), s1: +s1.toFixed(3), s2: +s2.toFixed(3), s3: +(lt - s1 - s2).toFixed(3), compound: c, tyreAge: age, pit });
        if (pit) pits.push({ driver: d.code, stop: si + 1, lap: n, pitLaneS: +(21.8 + r() * 1.2).toFixed(1), stationaryS: +(2.1 + r() * 1.2).toFixed(1) });
      }
      start = realEnd + 1;
    });
    laps[d.code] = rows;
    let acc = (d.grid - 1) * 0.35;
    cum[d.code] = rows.map((l) => (acc += l.time));
  });

  const order = (n: number) => DRIVERS.filter((d) => cum[d.code][n - 1] !== undefined)
    .sort((a, b) => cum[a.code][n - 1] - cum[b.code][n - 1]).map((d) => d.code);
  const positionsByLap = Array.from({ length: TOTAL_LAPS }, (_, i) => {
    const ord = order(i + 1);
    const row: Record<string, number | null> = { lap: i + 1 };
    DRIVERS.forEach((d) => (row[d.code] = ord.indexOf(d.code) >= 0 ? ord.indexOf(d.code) + 1 : null));
    return row;
  });
  const gapByLap = Array.from({ length: TOTAL_LAPS }, (_, i) => {
    const ord = order(i + 1), lead = cum[ord[0]][i];
    const row: Record<string, number | null> = { lap: i + 1 };
    DRIVERS.forEach((d) => (row[d.code] = cum[d.code][i] !== undefined ? +(cum[d.code][i] - lead).toFixed(3) : null));
    return row;
  });
  const finishers = order(TOTAL_LAPS);
  const retired = DRIVERS.filter((d) => d.retire).sort((a, b) => b.retire! - a.retire!).map((d) => d.code);
  const winnerTime = cum[finishers[0]][TOTAL_LAPS - 1];
  const classification = [...finishers, ...retired].map((code, i) => {
    const d = driverByCode(code), fin = finishers.includes(code);
    return {
      pos: i + 1, code, name: d.name, team: teamById(d.team).name, teamColor: teamById(d.team).color,
      grid: d.grid, placesGained: fin ? d.grid - (i + 1) : null,
      status: fin ? "Finished" : "Retired (sample)", lapsCompleted: fin ? TOTAL_LAPS : d.retire!,
      timeOrGap: fin ? (i === 0 ? fmtRace(winnerTime) : "+" + (cum[code][TOTAL_LAPS - 1] - winnerTime).toFixed(3)) : "DNF",
      points: fin ? POINTS[i] ?? 0 : 0,
      bestLap: Math.min(...laps[code].filter((l) => !l.pit && l.lap > 1 && !VSC_LAPS.includes(l.lap)).map((l) => l.time)),
    };
  });
  const clock = (sec: number) => {
    const [h, m, s] = DEMO_RACE.startClock.split(":").map(Number);
    const tot = Math.round(h * 3600 + m * 60 + s + sec);
    return [Math.floor(tot / 3600) % 24, Math.floor(tot / 60) % 60, tot % 60].map((n) => String(n).padStart(2, "0")).join(":");
  };
  const lead = (lap: number) => cum[finishers[0]][lap - 1];
  const raceControl = [
    { lap: 1, category: "Flag", flag: "GREEN", message: "GREEN LIGHT - RACE START (sample message)" },
    { lap: 9, category: "Flag", flag: "YELLOW", message: "YELLOW IN TRACK SECTOR 2 (sample message)" },
    { lap: 10, category: "Flag", flag: "CLEAR", message: "CLEAR IN TRACK SECTOR 2 (sample message)" },
    { lap: 22, category: "SafetyCar", flag: "YELLOW", message: "VIRTUAL SAFETY CAR DEPLOYED (sample message)" },
    { lap: 23, category: "SafetyCar", flag: "GREEN", message: "VIRTUAL SAFETY CAR ENDING (sample message)" },
    { lap: 31, category: "Other", flag: "", message: "NOTED - CAR 11 (PER) LEAVING THE TRACK (sample message)" },
    { lap: 40, category: "Other", flag: "", message: "CAR 18 (STR) STOPPED ON TRACK, RETIRED (sample message)" },
    { lap: 57, category: "Flag", flag: "CHEQUERED", message: "CHEQUERED FLAG (sample message)" },
  ].map((m) => ({ ...m, time: clock(lead(m.lap)) }));
  return { laps, stints, pits, positionsByLap, gapByLap, classification, raceControl, clock };
}
function fmtRace(sec: number) {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return `${h}:${String(m).padStart(2, "0")}:${s.toFixed(3).padStart(6, "0")}`;
}
export const fmtLap = (sec: number) => `${Math.floor(sec / 60)}:${(sec % 60).toFixed(3).padStart(6, "0")}`;

export function sectorTable() {
  const race = getRace();
  const clean = (code: string) => race.laps[code].filter((l) => !l.pit && l.lap > 1 && !VSC_LAPS.includes(l.lap));
  const rows = DRIVERS.map((d) => {
    const L = clean(d.code), avg = (k: "s1" | "s2" | "s3") => L.reduce((s, l) => s + l[k], 0) / L.length;
    const best = (k: "s1" | "s2" | "s3") => Math.min(...L.map((l) => l[k]));
    return { code: d.code, name: d.name, bestS1: best("s1"), bestS2: best("s2"), bestS3: best("s3"),
      avgS1: avg("s1"), avgS2: avg("s2"), avgS3: avg("s3"), bestLap: Math.min(...L.map((l) => l.time)),
      ideal: best("s1") + best("s2") + best("s3") };
  });
  const sb = { s1: Math.min(...rows.map((r) => r.bestS1)), s2: Math.min(...rows.map((r) => r.bestS2)), s3: Math.min(...rows.map((r) => r.bestS3)) };
  return { rows, sessionBest: sb, holders: {
    s1: rows.find((r) => r.bestS1 === sb.s1)!.code, s2: rows.find((r) => r.bestS2 === sb.s2)!.code, s3: rows.find((r) => r.bestS3 === sb.s3)!.code } };
}

export function degradation(code: string) {
  const race = getRace();
  return race.stints.filter((s) => s.driver === code).map((s) => {
    const pts = race.laps[code].filter((l) => l.lap >= s.startLap + 1 && l.lap < s.endLap && l.lap > 1 && !VSC_LAPS.includes(l.lap))
      .map((l) => ({ x: l.tyreAge, y: l.time - FUEL_S_PER_LAP * (TOTAL_LAPS - l.lap) }));
    const n = pts.length;
    if (n < 4) return { stint: s.stint, compound: s.compound, slope: null, r2: null, n, confidence: "low" };
    const mx = pts.reduce((a, p) => a + p.x, 0) / n, my = pts.reduce((a, p) => a + p.y, 0) / n;
    const sxx = pts.reduce((a, p) => a + (p.x - mx) ** 2, 0), sxy = pts.reduce((a, p) => a + (p.x - mx) * (p.y - my), 0);
    const slope = sxy / sxx, syy = pts.reduce((a, p) => a + (p.y - my) ** 2, 0);
    const r2 = syy === 0 ? 0 : (sxy * sxy) / (sxx * syy);
    return { stint: s.stint, compound: s.compound, slope: +slope.toFixed(3), r2: +r2.toFixed(2), n,
      confidence: r2 >= 0.5 && n >= 10 ? "high" : r2 >= 0.3 && n >= 8 ? "medium" : "low" };
  });
}

export const WEATHER = [
  { lap: 1, airC: 24.2, trackC: 38.5, humidity: 45, windMs: 3.2, rain: false },
  { lap: 10, airC: 24.0, trackC: 38.1, humidity: 45, windMs: 3.4, rain: false },
  { lap: 20, airC: 23.8, trackC: 37.4, humidity: 46, windMs: 3.0, rain: false },
  { lap: 30, airC: 23.6, trackC: 36.8, humidity: 46, windMs: 2.9, rain: false },
  { lap: 40, airC: 23.4, trackC: 36.0, humidity: 47, windMs: 3.1, rain: false },
  { lap: 50, airC: 23.2, trackC: 35.4, humidity: 48, windMs: 2.8, rain: false },
  { lap: 57, airC: 23.1, trackC: 35.2, humidity: 48, windMs: 2.8, rain: false },
];
export const weatherAt = (lap: number) => [...WEATHER].reverse().find((w) => w.lap <= lap) ?? WEATHER[0];

// ---------- season sample (after round 12 of 24, illustrative) ----------
export const SEASON_LABEL = "After round 12 of 24 (sample)";
export const STANDINGS_DRIVERS = [
  { pos: 1, code: "VER", points: 258, wins: 5 }, { pos: 2, code: "NOR", points: 241, wins: 3 },
  { pos: 3, code: "LEC", points: 226, wins: 2 }, { pos: 4, code: "PIA", points: 198, wins: 1 },
  { pos: 5, code: "HAM", points: 176, wins: 1 }, { pos: 6, code: "RUS", points: 169, wins: 0 },
  { pos: 7, code: "SAI", points: 143, wins: 0 }, { pos: 8, code: "PER", points: 98, wins: 0 },
  { pos: 9, code: "ALO", points: 74, wins: 0 }, { pos: 10, code: "STR", points: 31, wins: 0 },
].map((r) => ({ ...r, name: driverByCode(r.code).name, team: teamById(driverByCode(r.code).team).name, teamColor: teamById(driverByCode(r.code).team).color }));
export const STANDINGS_CONSTRUCTORS = [
  { pos: 1, id: "mclaren", points: 439 }, { pos: 2, id: "ferrari", points: 369 }, { pos: 3, id: "red_bull", points: 356 },
  { pos: 4, id: "mercedes", points: 345 }, { pos: 5, id: "aston_martin", points: 105 },
].map((r) => ({ ...r, name: teamById(r.id).name, color: teamById(r.id).color }));
export const POINTS_PROGRESSION: Record<string, number[]> = {
  VER: [25, 43, 68, 86, 111, 129, 154, 172, 197, 215, 240, 258],
  NOR: [18, 36, 54, 79, 97, 122, 140, 165, 183, 208, 223, 241],
  LEC: [15, 40, 58, 73, 98, 116, 134, 159, 177, 195, 211, 226],
  PIA: [12, 27, 45, 58, 76, 94, 112, 130, 148, 165, 181, 198],
  HAM: [10, 22, 40, 55, 73, 91, 109, 122, 138, 150, 163, 176],
};
export const SAMPLE_CALENDAR = Array.from({ length: 24 }, (_, i) => ({
  round: i + 1, name: i === 11 ? DEMO_RACE.name : `Sample round ${i + 1}`, status: i < 12 ? "completed" : "upcoming",
}));

// ---------- legends and eras (retired champions; career totals do not change) ----------
export const LEGENDS = [
  { id: "schumacher", name: "Michael Schumacher", titles: 7, titleYears: [1994, 1995, 2000, 2001, 2002, 2003, 2004], wins: 91, active: "1991-2012", teams: "Jordan, Benetton, Ferrari, Mercedes" },
  { id: "fangio", name: "Juan Manuel Fangio", titles: 5, titleYears: [1951, 1954, 1955, 1956, 1957], wins: 24, active: "1950-1958", teams: "Alfa Romeo, Maserati, Mercedes, Ferrari" },
  { id: "prost", name: "Alain Prost", titles: 4, titleYears: [1985, 1986, 1989, 1993], wins: 51, active: "1980-1993", teams: "McLaren, Renault, Ferrari, Williams" },
  { id: "vettel", name: "Sebastian Vettel", titles: 4, titleYears: [2010, 2011, 2012, 2013], wins: 53, active: "2007-2022", teams: "Toro Rosso, Red Bull, Ferrari, Aston Martin" },
  { id: "senna", name: "Ayrton Senna", titles: 3, titleYears: [1988, 1990, 1991], wins: 41, active: "1984-1994", teams: "Toleman, Lotus, McLaren, Williams" },
  { id: "lauda", name: "Niki Lauda", titles: 3, titleYears: [1975, 1977, 1984], wins: 25, active: "1971-1985", teams: "March, BRM, Ferrari, Brabham, McLaren" },
  { id: "stewart", name: "Jackie Stewart", titles: 3, titleYears: [1969, 1971, 1973], wins: 27, active: "1965-1973", teams: "BRM, Matra, Tyrrell" },
  { id: "brabham", name: "Jack Brabham", titles: 3, titleYears: [1959, 1960, 1966], wins: 14, active: "1955-1970", teams: "Cooper, Brabham" },
  { id: "piquet", name: "Nelson Piquet", titles: 3, titleYears: [1981, 1983, 1987], wins: 23, active: "1978-1991", teams: "Brabham, Williams, Lotus, Benetton" },
  { id: "clark", name: "Jim Clark", titles: 2, titleYears: [1963, 1965], wins: 25, active: "1960-1968", teams: "Lotus" },
  { id: "fittipaldi", name: "Emerson Fittipaldi", titles: 2, titleYears: [1972, 1974], wins: 14, active: "1970-1980", teams: "Lotus, McLaren, Copersucar" },
  { id: "hakkinen", name: "Mika Hakkinen", titles: 2, titleYears: [1998, 1999], wins: 20, active: "1991-2001", teams: "Lotus, McLaren" },
  { id: "hunt", name: "James Hunt", titles: 1, titleYears: [1976], wins: 10, active: "1973-1979", teams: "Hesketh, McLaren, Wolf" },
  { id: "hill", name: "Damon Hill", titles: 1, titleYears: [1996], wins: 22, active: "1992-1999", teams: "Brabham, Williams, Arrows, Jordan" },
  { id: "raikkonen", name: "Kimi Raikkonen", titles: 1, titleYears: [2007], wins: 21, active: "2001-2021", teams: "Sauber, McLaren, Ferrari, Lotus, Alfa Romeo" },
  { id: "button", name: "Jenson Button", titles: 1, titleYears: [2009], wins: 15, active: "2000-2017", teams: "Williams, Benetton, BAR, Honda, Brawn, McLaren" },
  { id: "rosberg", name: "Nico Rosberg", titles: 1, titleYears: [2016], wins: 23, active: "2006-2016", teams: "Williams, Mercedes" },
];
export const LEGENDS_NOTE = "Retired champions only. Verify career totals against an official source before publishing.";

export const ERAS = [
  { id: "early", from: 1950, to: 1957, name: "The Championship Begins", text: "Front-engined cars, narrow tyres, and the first world championship in 1950." },
  { id: "rear", from: 1958, to: 1976, name: "Rear Engines and Wings", text: "Rear-engined cars arrive, followed by wings, slick tyres and safety campaigns." },
  { id: "ge1", from: 1977, to: 1982, name: "First Ground Effect Era", text: "Underbody aerodynamics and the first turbo engines." },
  { id: "turbo", from: 1983, to: 1988, name: "Turbo Era", text: "Turbocharged engines with very high power outputs." },
  { id: "na", from: 1989, to: 2005, name: "Naturally Aspirated Era", text: "V10 engines, electronic driver aids in the 1990s, refuelling stops in some seasons." },
  { id: "v8", from: 2006, to: 2013, name: "V8 Era", text: "2.4 litre V8 engines, KERS from 2009 and exhaust-blown diffusers." },
  { id: "hybrid", from: 2014, to: 2021, name: "Turbo-Hybrid Era", text: "1.6 litre V6 turbo-hybrid power units with MGU-K and MGU-H energy recovery." },
  { id: "ge2", from: 2022, to: 2025, name: "Modern Ground Effect Era", text: "Venturi tunnel floors, 18-inch wheels and a cost cap." },
].map((e) => ({ ...e, champions: LEGENDS.filter((l) => l.titleYears.some((y) => y >= e.from && y <= e.to)).map((l) => l.name) }));
