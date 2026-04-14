import { clsx, type ClassValue } from "clsx";
import type { Tier } from "./types";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatPct(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatEdge(edge: number): string {
  return `+${(edge * 100).toFixed(2)}%`;
}

export function formatOdds(decimal: number): string {
  return decimal.toFixed(3);
}

export function formatAmerican(decimal: number): string {
  if (decimal >= 2.0) {
    return `+${Math.round((decimal - 1) * 100)}`;
  }
  return `${Math.round(-100 / (decimal - 1))}`;
}

export function formatStatType(stat: string): string {
  return stat
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function formatSport(sport: string): string {
  const map: Record<string, string> = {
    basketball_nba: "NBA",
    americanfootball_nfl: "NFL",
    baseball_mlb: "MLB",
    icehockey_nhl: "NHL",
  };
  return map[sport] ?? sport.toUpperCase();
}

export function tierColor(tier: Tier | null): string {
  switch (tier) {
    case "elite":
      return "text-elite";
    case "high":
      return "text-high";
    case "standard":
      return "text-standard";
    default:
      return "text-text-secondary";
  }
}

export function tierBg(tier: Tier | null): string {
  switch (tier) {
    case "elite":
      return "bg-elite/10 text-elite border-elite/30";
    case "high":
      return "bg-high/10 text-high border-high/30";
    case "standard":
      return "bg-ev-positive-muted text-ev-positive border-ev-positive/30";
    default:
      return "bg-surface-overlay text-text-secondary border-border";
  }
}

export function evColor(ev: number | null): string {
  if (ev === null) return "text-text-secondary";
  if (ev >= 0.10) return "text-elite";
  if (ev >= 0.05) return "text-ev-positive";
  if (ev >= 0.02) return "text-ev-neutral";
  return "text-text-secondary";
}

export function confidenceBar(score: number): string {
  if (score >= 80) return "bg-ev-positive";
  if (score >= 60) return "bg-ev-neutral";
  return "bg-text-muted";
}

export function bookmakerLabel(key: string): string {
  const map: Record<string, string> = {
    draftkings: "DraftKings",
    fanduel: "FanDuel",
    betmgm: "BetMGM",
    caesars: "Caesars",
    pinnacle: "Pinnacle",
    pointsbetus: "PointsBet",
    bovada: "Bovada",
    betonlineag: "BetOnline",
  };
  return map[key] ?? key;
}

export function defRankLabel(pct: number | null): string {
  if (pct === null) return "—";
  if (pct <= 0.1) return "Elite";
  if (pct <= 0.33) return "Good";
  if (pct <= 0.66) return "Average";
  return "Weak";
}
