"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { PropFilter, Sport, Tier, Direction } from "@/lib/types";

const SPORTS: { value: Sport; label: string }[] = [
  { value: "basketball_nba", label: "NBA" },
  { value: "americanfootball_nfl", label: "NFL" },
  { value: "baseball_mlb", label: "MLB" },
  { value: "icehockey_nhl", label: "NHL" },
];

const TIERS: { value: Tier; label: string }[] = [
  { value: "elite", label: "Elite 🔥" },
  { value: "high", label: "High ⚡" },
  { value: "standard", label: "Standard" },
];

const BOOKS = [
  { value: "draftkings", label: "DraftKings" },
  { value: "fanduel", label: "FanDuel" },
  { value: "betmgm", label: "BetMGM" },
  { value: "caesars", label: "Caesars" },
];

interface FiltersBarProps {
  filter: PropFilter;
  onChange: (f: PropFilter) => void;
}

export function FiltersBar({ filter, onChange }: FiltersBarProps) {
  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Sport filter */}
      <div className="flex items-center gap-1">
        {SPORTS.map((s) => (
          <FilterChip
            key={s.value}
            active={filter.sport === s.value}
            label={s.label}
            onClick={() =>
              onChange({ ...filter, sport: filter.sport === s.value ? undefined : s.value })
            }
          />
        ))}
      </div>

      <div className="w-px h-4 bg-border" />

      {/* Tier filter */}
      <div className="flex items-center gap-1">
        {TIERS.map((t) => (
          <FilterChip
            key={t.value}
            active={filter.tier === t.value}
            label={t.label}
            onClick={() =>
              onChange({ ...filter, tier: filter.tier === t.value ? undefined : t.value })
            }
          />
        ))}
      </div>

      <div className="w-px h-4 bg-border" />

      {/* Direction */}
      <FilterChip
        active={filter.direction === "over"}
        label="Overs"
        onClick={() =>
          onChange({ ...filter, direction: filter.direction === "over" ? undefined : "over" })
        }
      />
      <FilterChip
        active={filter.direction === "under"}
        label="Unders"
        onClick={() =>
          onChange({ ...filter, direction: filter.direction === "under" ? undefined : "under" })
        }
      />

      <div className="w-px h-4 bg-border" />

      {/* Min EV */}
      <div className="flex items-center gap-2">
        <label className="text-2xs text-text-muted uppercase tracking-wide">Min EV</label>
        <select
          className="bg-surface-overlay border border-border rounded px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent"
          value={filter.min_ev ?? 0.03}
          onChange={(e) => onChange({ ...filter, min_ev: parseFloat(e.target.value) })}
        >
          <option value={0.02}>2%</option>
          <option value={0.03}>3%</option>
          <option value={0.05}>5%</option>
          <option value={0.08}>8%</option>
          <option value={0.10}>10%</option>
        </select>
      </div>

      {/* Min confidence */}
      <div className="flex items-center gap-2">
        <label className="text-2xs text-text-muted uppercase tracking-wide">Confidence</label>
        <select
          className="bg-surface-overlay border border-border rounded px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent"
          value={filter.min_confidence ?? 50}
          onChange={(e) => onChange({ ...filter, min_confidence: parseFloat(e.target.value) })}
        >
          <option value={40}>40+</option>
          <option value={50}>50+</option>
          <option value={60}>60+</option>
          <option value={70}>70+</option>
          <option value={80}>80+</option>
        </select>
      </div>

      {/* Book filter */}
      <div className="flex items-center gap-2">
        <label className="text-2xs text-text-muted uppercase tracking-wide">Book</label>
        <select
          className="bg-surface-overlay border border-border rounded px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-accent"
          value={filter.bookmaker ?? ""}
          onChange={(e) =>
            onChange({ ...filter, bookmaker: e.target.value || undefined })
          }
        >
          <option value="">All</option>
          {BOOKS.map((b) => (
            <option key={b.value} value={b.value}>{b.label}</option>
          ))}
        </select>
      </div>

      {/* Clear */}
      {Object.values(filter).some(Boolean) && (
        <button
          className="text-2xs text-text-muted hover:text-text-secondary underline underline-offset-2 transition-colors"
          onClick={() => onChange({})}
        >
          Clear
        </button>
      )}
    </div>
  );
}

function FilterChip({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2.5 py-1 rounded text-xs font-medium border transition-all",
        active
          ? "bg-accent/15 border-accent/40 text-accent"
          : "bg-surface-overlay border-border text-text-secondary hover:text-text-primary hover:border-border-strong",
      )}
    >
      {label}
    </button>
  );
}
