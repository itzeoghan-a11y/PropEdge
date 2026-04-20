import type {
  AnalyticsPerformance,
  BacktestResult,
  BetHistory,
  PlayerDetail,
  PropDetail,
  PropFilter,
  PropSummary,
  SteamAlert,
  User,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class APIError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { params?: Record<string, string | number | boolean | undefined> } = {},
): Promise<T> {
  const { params, ...init } = options;
  let url = `${BASE}${path}`;

  if (params) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) qs.set(k, String(v));
    }
    const str = qs.toString();
    if (str) url += `?${str}`;
  }

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(init.headers as Record<string, string>),
  };

  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new APIError(res.status, body.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<string> {
  const form = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!res.ok) throw new APIError(res.status, "Invalid credentials");
  const data = await res.json();
  return data.access_token as string;
}

export function register(email: string, password: string, fullName?: string) {
  return request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
}

export function getMe() {
  return request<User>("/auth/me");
}

export function updateMe(payload: Partial<Pick<User, "alert_min_ev" | "alert_min_confidence" | "alert_steam" | "discord_webhook" | "phone_number" | "full_name">>) {
  return request<User>("/auth/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getCheckoutUrl(tier: "pro" | "elite") {
  return request<{ checkout_url: string }>(`/auth/checkout/${tier}`, {
    method: "POST",
  });
}

// ── Props ─────────────────────────────────────────────────────────────────────

export function getProps(filter: PropFilter & { limit?: number; offset?: number } = {}) {
  return request<PropSummary[]>("/props", {
    params: {
      sport: filter.sport,
      stat_type: filter.stat_type,
      min_ev: filter.min_ev,
      min_confidence: filter.min_confidence,
      bookmaker: filter.bookmaker,
      tier: filter.tier,
      direction: filter.direction,
      best_available_only: filter.best_available_only,
      has_steam: filter.has_steam,
      limit: filter.limit,
      offset: filter.offset,
    },
  });
}

export function getTopProps() {
  return request<PropSummary[]>("/props/top");
}

export function getPropDetail(id: number) {
  return request<PropDetail>(`/props/${id}`);
}

export function getSteamAlerts(hoursBack = 6) {
  return request<SteamAlert[]>("/props/steam", { params: { hours_back: hoursBack } });
}

export function getLineShop(params: {
  sport?: string;
  min_dispersion?: number;
  min_soft_books?: number;
  limit?: number;
} = {}) {
  return request<PropSummary[]>("/props/line-shop", { params });
}

// ── Players ───────────────────────────────────────────────────────────────────

export function getPlayerDetail(id: number) {
  return request<PlayerDetail>(`/players/${id}`);
}

export function searchPlayers(query?: string, sport?: string) {
  return request<PlayerDetail[]>("/players", {
    params: { search: query, sport },
  });
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export function getPerformance() {
  return request<AnalyticsPerformance>("/analytics/performance");
}

export function getBetHistory(params: {
  date_from?: string;
  date_to?: string;
  sport?: string;
  tier?: string;
  bookmaker?: string;
  resolved_only?: boolean;
  limit?: number;
  offset?: number;
} = {}) {
  return request<BetHistory>("/analytics/history", { params });
}

export function runBacktest(params: {
  date_from: string;
  date_to: string;
  sport?: string;
  min_edge?: number;
  min_confidence?: number;
}) {
  return request<BacktestResult>("/analytics/backtest", { params });
}

export function getBacktestHistory() {
  return request<unknown[]>("/analytics/backtest/history");
}

// ── SWR keys ──────────────────────────────────────────────────────────────────

export const swrKeys = {
  props: (f: PropFilter) => ["props", JSON.stringify(f)],
  topProps: () => ["props", "top"],
  propDetail: (id: number) => ["prop", id],
  steam: (h: number) => ["steam", h],
  lineShop: (p: object) => ["line-shop", JSON.stringify(p)],
  player: (id: number) => ["player", id],
  players: (q?: string, s?: string) => ["players", q, s],
  me: () => ["me"],
  performance: () => ["analytics", "performance"],
  history: (p: object) => ["history", JSON.stringify(p)],
  backtest: (p: object) => ["backtest", JSON.stringify(p)],
} as const;
